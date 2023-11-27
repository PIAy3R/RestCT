import json
from typing import Tuple, Union

import requests

from src.Dto.keywords import Method


class RestRequest:
    def __init__(self):
        self.url = None
        self.headers = None
        self.query = None
        self.body = None

    def send_request(self, verb, url: str, headers: dict, query: dict = None, body: dict = None) -> Tuple[int, Union[str, dict]]:
        self.url = url
        self.headers = headers
        self.query = query
        self.body = body
        if verb == Method.POST:
            status_code, response_content = self.send_post_request()
        elif verb == Method.GET:
            status_code, response_content = self.send_get_request()
        elif verb == Method.PUT:
            status_code, response_content = self.send_put_request()
        elif verb == Method.DELETE:
            status_code, response_content = self.send_delete_request()
        else:
            raise TypeError(f"Do not support the http method {verb} now")

        return status_code, response_content

    def send_post_request(self) -> Tuple[int, Union[str, dict]]:
        content_type = RestRequest.get_content_type(self.headers)
        if content_type == "applications/json":
            feedback = requests.post(url=self.url, headers=self.headers, data=self.query, json=json.dumps(self.body))
        else:
            feedback = requests.post(url=self.url, headers=self.headers, params=self.query, data=self.body)
        return RestRequest.get_response_info(feedback)

    def send_get_request(self) -> Tuple[int, Union[str, dict]]:
        feedback = requests.get(url=self.url, headers=self.headers, params=self.query)
        return RestRequest.get_response_info(feedback)

    def send_put_request(self) -> Tuple[int, Union[str, dict]]:
        feedback = requests.put(url=self.url, headers=self.headers, params=self.query, data=self.body)
        return RestRequest.get_response_info(feedback)

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
    def get_content_type(headers):
        return "applications/json" if headers.get("Content-Type") is None else headers.get("Content-Type")
