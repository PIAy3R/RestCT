from enum import Enum
from typing import Tuple, Union
import requests
from loguru import logger
from rest import ContentType
from src.Dto.keywords import Method


class StatusCode(Enum):
    NONEURL = 700


class RestRequest:
    def __init__(self, header_auth, query_auth):
        self._auth = Auth(header_auth, query_auth)

    def send_request(self, verb, url: str, headers: dict, **kwargs) -> Tuple[int, Union[str, dict]]:
        if url is None or "":
            logger.warning("Url cannot be null")
            return StatusCode.NONEURL.value, dict()
        if verb == Method.POST:
            status_code, response_content = self.send_post_request(url, headers, self._auth, **kwargs)
        elif verb == Method.GET:
            status_code, response_content = self.send_get_request(url, headers, self._auth, **kwargs)
        elif verb == Method.PUT:
            status_code, response_content = self.send_put_request(url, headers, self._auth, **kwargs)
        elif verb == Method.DELETE:
            status_code, response_content = self.send_delete_request(url, headers, self._auth, **kwargs)
        else:
            raise TypeError(f"Do not support the http method {verb} now")
        return status_code, response_content

    @staticmethod
    def send_post_request(url, headers, auth, **kwargs) -> Tuple[int, Union[str, dict]]:
        if headers.get("Content-Type", None) == ContentType.JSON.value:
            feedback = requests.post(url=url, headers=headers, params=kwargs.get("query", None),
                                     data=kwargs.get("body", None), files=kwargs.get("files", None), timeout=10,
                                     auth=auth)
        else:
            feedback = requests.post(url=url, headers=headers, params=kwargs.get("query", None),
                                     json=kwargs.get("body", None), files=kwargs.get("files", None), timeout=10,
                                     auth=auth)
        return RestRequest.get_response_info(feedback)

    @staticmethod
    def send_get_request(url, headers, auth, **kwargs) -> Tuple[int, Union[str, dict]]:
        feedback = requests.get(url=url, headers=headers, params=kwargs.get("query", None), timeout=10, auth=auth)
        return RestRequest.get_response_info(feedback)

    @staticmethod
    def send_put_request(url, headers, auth, **kwargs) -> Tuple[int, Union[str, dict]]:
        if headers.get("Content-Type", None) == ContentType.JSON.value:
            feedback = requests.post(url=url, headers=headers, params=kwargs.get("query", None),
                                     data=kwargs.get("body", None), files=kwargs.get("files", None), timeout=10,
                                     auth=auth)
        else:
            feedback = requests.post(url=url, headers=headers, params=kwargs.get("query", None),
                                     json=kwargs.get("body", None), files=kwargs.get("files", None), timeout=10,
                                     auth=auth)
        return RestRequest.get_response_info(feedback)

    @staticmethod
    def send_delete_request(url, headers, auth, **kwargs) -> Tuple[int, Union[str, dict]]:
        feedback = requests.delete(url=url, headers=headers, params=kwargs.get("query", None), timeout=10, auth=auth)
        return RestRequest.get_response_info(feedback)

    @staticmethod
    def get_response_info(feedback) -> Tuple[int, Union[str, dict]]:
        status_code = feedback.status_code
        try:
            response = feedback.json()
        except:
            response = feedback.text
        return status_code, response


class Auth:
    def __init__(self, header_auth, query_auth):
        self.header_auth = header_auth
        self.query_auth = query_auth

    def __call__(self, r):
        for key, token in self.header_auth.items():
            r.headers[key] = token
        for key, token in self.query_auth.items():
            r.params[key] = token
        return r
