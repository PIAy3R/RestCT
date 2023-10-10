import abc
import os
import openai
import time
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple
from loguru import logger
from src.Dto.keywords import Template, TaskTemplate, Method, URL
from src.Dto.operation import Operation
from src.Dto.parameter import AbstractParam
from src.languagemodel.OutputFixer import ValueOutputFixer, BodyOutputFixer
import tiktoken
import json


def num_tokens_from_string(messages: List[Dict[str, str]], encoding_name: str = "gpt-3.5-turbo") -> int:
    """
    :param messages: the messages string_to_count to be counted
    :param encoding_name: the model to call, different models have different ways to count tokens
    :return: the token num of the prompt
    """
    string_to_count = ""
    for role_message in messages:
        string_to_count += role_message.get("content")
    encoding = tiktoken.encoding_for_model(encoding_name)
    num_tokens = len(encoding.encode(string_to_count))
    logger.info("token nums: {}".format(num_tokens))
    return num_tokens


class BasicLanguageModel:

    def __init__(self, operation: Operation, manager, data_path, temperature: float = 0.7):
        self._temperature: float = temperature

        self._operation = operation
        self._manager = manager
        self._constraint: list = operation.constraints
        self._data_path = Path(data_path) / "prompt_response.json"

        self._max_query_len: int = 3900

        swagger = Path(os.getenv("swagger"))
        with swagger.open("r") as fp:
            self._spec = json.load(fp)

        self._complete_model: str = os.environ.get("model")
        openai.api_key = os.environ.get("language_model_key")
        logger.debug(f"call language model for operation: {self._operation}")

    @property
    def operation(self) -> Operation:
        return self._operation

    @operation.setter
    def operation(self, operation: Operation):
        self._operation = operation

    @property
    def temperature(self) -> float:
        return self._temperature

    @temperature.setter
    def temperature(self, temperature: float):
        self._temperature = temperature

    @property
    def max_query_len(self) -> int:
        return self._max_query_len

    @max_query_len.setter
    def max_query_len(self, max_query_len: int):
        self._max_query_len = max_query_len

    def build_prompt(self) -> str:
        pass

    def build_message(self) -> List[Dict[str, str]]:
        pass

    def call(self):
        message = self.build_message()
        num_tokens = num_tokens_from_string(message, self._complete_model)
        if num_tokens > self._max_query_len:
            self._complete_model = "gpt-3.5-turbo-16k"
            recount_tokens = num_tokens_from_string(message)
            if recount_tokens > 16384:
                logger.warning("Exceeding the maximum token limit")
                return
        start_time = time.time()
        response = openai.ChatCompletion.create(
            model=self._complete_model,
            messages=message,
            temperature=self._temperature,
        )
        self._manager.register_llm_call()
        end_time = time.time()
        logger.info(f"call time: {end_time - start_time} s")
        return response.choices[0].message["content"], message

    def execute(self):
        pass

    def save_message_and_response(self, prompt, response):
        pr_info = {
            "operation": self.operation.__repr__(),
            "temperature": self.temperature,
            "prompt": prompt,
            "llm_response": response
        }
        with self._data_path.open("a+") as fp:
            json.dump(pr_info, fp)


class ParamValueModel(BasicLanguageModel):
    def __init__(self, operation: Operation, target_param: List[AbstractParam], manager, data_path,
                 temperature: float = 0.7):
        super().__init__(operation, manager, data_path, temperature)

        self._target_param: List[AbstractParam] = target_param
        self._fixer = ValueOutputFixer(self._manager, self._operation)

        logger.debug(f"target parameter list: {self._target_param}")

    def build_prompt(self) -> str:
        pInfo = []
        parameters = self._spec.get("paths").get(self._operation.url.replace(URL.baseurl, "")).get(
            self._operation.method.value).get("parameters")
        for p in self._target_param:
            for info in parameters:
                if info.get("name") == p.name:
                    pInfo.append(info)
        prompt = Template.EXPLANATION + Template.TEXT.format(self._operation, pInfo, self._operation.constraints,
                                                             self._target_param) + TaskTemplate.SPECIAL_VALUE
        return prompt

    def build_message(self) -> List[Dict[str, str]]:
        message = []
        prompt = self.build_prompt()
        message.append({"role": "system", "content": Template.SYS_ROLE})
        message.append({"role": "user", "content": prompt})
        return message

    def execute(self):
        response_str, message = self.call()
        parameters = self._spec.get("paths").get(self._operation.url.replace(URL.baseurl, "")).get(
            self._operation.method.value).get("parameters")
        formatted_output = self._fixer.handle(response_str, parameters)
        logger.info(f"Language model answer: {formatted_output}")
        self.save_message_and_response(message, formatted_output)


class FakerMethodModel(BasicLanguageModel):
    def __init__(self, operation: Operation, target_param: List[AbstractParam], manager, data_path,
                 temperature: float = 0.7):
        super().__init__(operation, manager, data_path, temperature)

        self._target_param: List[AbstractParam] = target_param

    def build_prompt(self) -> str:
        pInfo = []
        for p in self._target_param:
            info = {
                "name": p.name,
                "type": p.type.value,
                "description": p.description
            }
            pInfo.append(info)
        prompt = Template.PARAMETER.format(pInfo) + TaskTemplate.FAKER
        return prompt

    def build_message(self) -> List[Dict[str, str]]:
        message = []
        prompt = self.build_prompt()
        message.append({"role": "system", "content": Template.FAKER})
        message.append({"role": "user", "content": prompt})
        return message


class BodyParamModel(BasicLanguageModel):
    def __init__(self, operation: Operation, target_param: List[AbstractParam], manager, data_path,
                 temperature: float = 0.7):
        super().__init__(operation, manager, data_path, temperature)

        self._target_param: List[AbstractParam] = target_param
        self._fixer = BodyOutputFixer(self._manager, self._operation)

        logger.debug(f"target parameter list: {self._target_param}")

    def build_prompt(self) -> str:

        definition = self._spec["definitions"]

        pInfo = []
        parameters = self._spec.get("paths").get(self._operation.url.replace(URL.baseurl, "")).get(
            self._operation.method.value).get("parameters")
        for p in self._target_param:
            for info in parameters:
                if info.get("name") == p.name:
                    pInfo.append(info)
        prompt = Template.EXPLANATION + Template.TEXT.format(self.operation, pInfo, self._constraint,
                                                             f"[{', '.join([p.name for p in self._target_param])}]")

        def get_def(definition_dict: dict):
            final_dict = dict()
            # required_param_list = definition_dict["required"]
            if definition_dict.get("properties") is not None:
                required_param_list = [p for p in definition_dict["properties"]]
                properties = dict()
                for param, info in definition_dict["properties"].items():
                    if param in required_param_list:
                        properties.update({param: info})
                        if properties[param].get("$ref") != None:
                            new_def_dict = definition[properties[param].get("$ref").split("/")[-1]]
                            new_def_dict_return = get_def(new_def_dict)
                            properties[param] = new_def_dict_return
                        elif properties[param].get("type") == "array" and properties[param].get("items"). \
                                get("$ref") is not None:
                            new_def_dict = definition[properties[param].get("items").get("$ref").split("/")[-1]]
                            new_def_dict_return = get_def(new_def_dict)
                            properties[param]["items"] = new_def_dict_return
                    final_dict.update(properties)
                return final_dict
            elif definition_dict.get("items") is not None:
                new_ref = definition_dict.get("items").get("$ref").split("/")[-1]
                new_def_dict = definition[new_ref]
                definition_dict["items"] = get_def(new_def_dict)
                final_dict.update(definition_dict)
                return final_dict

        param_info = self._spec["paths"][self.operation.url.replace(URL.baseurl, '')][self.operation.method.value].get(
            "parameters")
        body_dict = dict()
        body_ref = ""
        for paramdict in param_info:
            if paramdict.get("in") == "body":
                body_ref = paramdict["schema"]["$ref"].split("/")[-1]
        body_dict["body"] = get_def(definition[body_ref])
        prompt += Template.BODY_EXPLANATION.format(body_dict) + TaskTemplate.BODY
        return prompt

    def build_message(self) -> List[Dict[str, str]]:
        message = []
        prompt = self.build_prompt()
        message.append({"role": "system", "content": Template.SYS_ROLE})
        message.append({"role": "user", "content": prompt})
        return message

    def execute(self):
        response_str, message = self.call()
        # parameters = self._spec.get("paths").get(self._operation.url.replace(URL.baseurl, "")).get(
        #     self._operation.method.value).get("parameters")
        formatted_output = self._fixer.handle(response_str, self._target_param)
        self.save_message_and_response(message, formatted_output)
