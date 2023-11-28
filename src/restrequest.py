import json
from typing import Tuple, Union

import requests
from loguru import logger

from src.Dto.keywords import Method


class RestRequest:
    def __init__(self):
        pass

    def send_request(self, verb, url: str, headers: dict, **kwargs) -> Tuple[int, Union[str, dict]]:
        if url is None or "":
            logger.warning("Url cannot be null")
            return 700, dict()
        else:
            self.url = url
        self.headers = headers
        self.query = kwargs.get("query", None)
        self.file = kwargs.get("file", None)
        if verb == Method.POST:
            self.body = kwargs.get("body") if kwargs.get("body") is not None else None
            status_code, response_content = self.send_post_request()
        elif verb == Method.GET:
            status_code, response_content = self.send_get_request()
        elif verb == Method.PUT:
            self.body = kwargs.get("body") if kwargs.get("body") is not None else None
            status_code, response_content = self.send_put_request()
        elif verb == Method.DELETE:
            status_code, response_content = self.send_delete_request()
        else:
            raise TypeError(f"Do not support the http method {verb} now")

        return status_code, response_content

    @staticmethod
    def send_post_request(self) -> Tuple[int, Union[str, dict]]:
        if self.body is None:
            feedback = requests.post(url=self.url, headers=self.headers, params=self.query)
        elif self.get_content_type() == "applications/json":
            feedback = requests.post(url=self.url, headers=self.headers, params=self.query, json=json.dumps(self.body))
        else:
            feedback = requests.post(url=self.url, headers=self.headers, params=self.query, data=self.body)
        return RestRequest.get_response_info(feedback)

    @staticmethod
    def send_get_request(self) -> Tuple[int, Union[str, dict]]:
        feedback = requests.get(url=self.url, headers=self.headers, params=self.query)
        return RestRequest.get_response_info(feedback)

    @staticmethod
    def send_put_request(self) -> Tuple[int, Union[str, dict]]:
        if self.body is None:
            feedback = requests.post(url=self.url, headers=self.headers, params=self.query)
        elif self.get_content_type() == "applications/json":
            feedback = requests.post(url=self.url, headers=self.headers, params=self.query, json=json.dumps(self.body))
        else:
            feedback = requests.post(url=self.url, headers=self.headers, params=self.query, data=self.body)
        return RestRequest.get_response_info(feedback)

    @staticmethod
    def send_delete_request(self) -> Tuple[int, Union[str, dict]]:
        feedback = requests.delete(url=self.url, headers=self.headers, params=self.query)
        return RestRequest.get_response_info(feedback)

    @staticmethod
    def get_response_info(feedback) -> Tuple[int, Union[str, dict]]:
        status_code = feedback.status_code
        try:
            response = feedback.json()
        except:
            response = feedback.text
        return status_code, response

    @staticmethod
    def get_content_type(self):
        return "applications/json" if self.headers.get("Content-Type") is None else self.headers.get("Content-Type")
