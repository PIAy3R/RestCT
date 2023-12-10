import dataclasses
from typing import Tuple, Union, Optional, Iterable

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
    def __init__(self, header_auths: Optional[Iterable[HeaderAuth]] = None,
                 query_auths: Optional[Iterable[QueryAuth]] = None):
        self.header_auths = header_auths if header_auths is not None else []
        self.query_auths = query_auths if query_auths is not None else []

    def __call__(self, r):
        for a in self.header_auths:
            r.headers[a.key] = a.token
        for a in self.query_auths:
            r.params[a.key] = a.token
        return r


class RestRequest:
    UNEXPECTED = 700

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

        header_auths = kwargs.get("header_auths", None)
        query_auths = kwargs.get("query_auths", None)

        auth = None
        if header_auths is not None or query_auths is not None:
            auth = Auth(header_auths, query_auths)

        if verb in [Method.POST, Method.PUT]:
            status_code, response_content = self.send_request_with_content(verb, url, headers, auth, **kwargs)

        elif verb in [Method.GET, Method.DELETE]:
            status_code, response_content = self.send_request(url, headers, auth, **kwargs)
        else:
            raise TypeError(f"Do not support the http method {verb} now")
        return status_code, response_content

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
