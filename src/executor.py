import dataclasses
from collections import defaultdict
from typing import Tuple, Union, Optional

import requests

from rest import ContentType
from src.rest import Method


@dataclasses.dataclass(frozen=True)
class HeaderAuth:
    key: str
    token: str


@dataclasses.dataclass(frozen=True)
class QueryAuth:
    key: str
    token: str


class Auth:
    def __init__(self, header_auth: Optional[HeaderAuth] = None,
                 query_auth: Optional[QueryAuth] = None):
        self.header_auth = header_auth
        self.query_auth = query_auth

    def __call__(self, r):
        if self.header_auth is not None:
            r.headers[self.header_auth.key] = self.header_auth.token
        if self.query_auth is not None:
            r.params[self.query_auth.key] = self.query_auth.token
        return r


class RestRequest:
    UNEXPECTED = 700

    def __init__(self, auth: Auth):
        self.info = defaultdict(list)
        self.auth: Auth = auth

    @staticmethod
    def validate(verb: Method, url: str, headers: dict, **kwargs):
        """
        验证请求是否合法
        1）post和put需要验证body参数是否存在
        """
        if url is None or url == "":
            raise ValueError("Url cannot be null")
        if verb in [Method.POST, Method.PUT] and "body" not in kwargs:
            raise ValueError(f"{verb}: body cannot be null")
        if "body" in kwargs and "files" in kwargs:
            raise ValueError("body and files cannot be set at the same time")

    def send(self, verb: Method, url: str, headers: dict, **kwargs) -> Tuple[int, Union[str, dict]]:
        self.validate(verb, url, headers, **kwargs)

        # header_auths = kwargs.get("header_auths", None)
        # query_auths = kwargs.get("query_auths", None)
        #
        # auth = None
        # if header_auths is not None or query_auths is not None:
        #     auth = Auth(header_auths, query_auths)

        if verb in [Method.POST, Method.PUT]:
            status_code, response_content = self.send_request_with_content(verb, url, headers, self.auth, **kwargs)

        elif verb in [Method.GET, Method.DELETE]:
            status_code, response_content = self.send_request(url, headers, self.auth, **kwargs)
        else:
            raise TypeError(f"Do not support the http method {verb} now")

        self._record(verb, url, status_code, response_content)
        print(f"{verb.value}:{url} {status_code}, {response_content}")
        return status_code, response_content

    def _record(self, verb: Method, url: str, status_code: int, response_content: Union[str, dict]):
        op_id: str = f"{verb.value}:{url}"
        self.info[op_id].append(status_code)

    @staticmethod
    def send_request_with_content(method: Method, url: str, headers: dict, auth: Optional[Auth], **kwargs) \
            -> Tuple[int, Union[str, dict]]:
        content_type = kwargs.get("Content-Type", None)
        if content_type is None:
            content_type = ContentType.JSON

        if "json" in content_type.value.lower():
            response = requests.request(method=method.value, url=url, headers=headers, params=kwargs.get("query", None),
                                        json=kwargs.get("body", None), files=kwargs.get("files", None), timeout=10,
                                        auth=auth)
        else:
            response = requests.request(method=method.value, url=url, headers=headers, params=kwargs.get("query", None),
                                        data=kwargs.get("body", None), files=kwargs.get("files", None), timeout=10,
                                        auth=auth)

        return RestRequest.get_response_info(response)

    @staticmethod
    def send_request(url, headers, auth, **kwargs) -> Tuple[int, Union[str, dict]]:
        feedback = requests.delete(url=url, headers=headers, params=kwargs.get("query", None), timeout=10, auth=auth)
        return RestRequest.get_response_info(feedback)

    @staticmethod
    def get_response_info(feedback: requests.Response) -> Tuple[int, Union[str, dict]]:
        status_code = feedback.status_code
        try:
            response = feedback.json()
        except requests.exceptions.JSONDecodeError:
            response = feedback.text
        return status_code, response
