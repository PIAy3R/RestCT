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
from src.languagemodel.outputprocessor import OutputProcessor
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

    def __init__(self, operation: Operation, manager, temperature: float = 0.7):
        self._temperature: float = temperature

        self._operation = operation
        self._manager = manager
        self._constraint: list = operation.constraints

        self._max_query_len: int = 3900

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
        return response.choices[0].message["content"]

    def execute(self):
        pass


class ParamValueModel(BasicLanguageModel):
    def __init__(self, operation: Operation, target_param: List[AbstractParam], manager, temperature: float = 0.7):
        super().__init__(operation, manager, temperature)

        self._target_param: List[AbstractParam] = target_param
        self._fixer = ValueOutputFixer(self._manager, self._operation)

        swagger = Path(os.getenv("swagger"))
        with swagger.open("r") as fp:
            self._spec = json.load(fp)

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
        response_str = self.call()
        formatted_output = self._fixer.handle(response_str)
        logger.info(f"Language model answer: {formatted_output}")


class FakerMethodModel(BasicLanguageModel):
    def __init__(self, operation: Operation, target_param: List[AbstractParam], manager, temperature: float = 0.7):
        super().__init__(operation, manager, temperature)

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


class ParamContainBodyModel(BasicLanguageModel):
    def __init__(self, operation: Operation, target_param: List[AbstractParam], manager, temperature: float = 0.7):
        super().__init__(operation, manager, temperature)

        self._target_param: List[AbstractParam] = target_param
        self._fixer = BodyOutputFixer(self._manager, self._operation)

        logger.debug(f"target parameter list: {self._target_param}")
