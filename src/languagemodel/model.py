import os

import openai
import time
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple
from loguru import logger
from src.Dto.keywords import Template, TaskTemplate, Method
from src.Dto.operation import Operation
from src.Dto.parameter import AbstractParam
from src.languagemodel.outputprocessor import OutputProcessor
from src.parseJson import _compile_url
import tiktoken
import json



def num_tokens_from_string(string: str, encoding_name: str) -> int:
    """Returns the number of tokens in a text string."""
    logger.debug("                check token nums")
    encoding = tiktoken.encoding_for_model(encoding_name)
    num_tokens = len(encoding.encode(string))
    logger.info("                token nums: {}".format(num_tokens))
    return num_tokens


class _OpenAILanguageModel:
    exampleValueDict: Dict[Operation, Dict[str, List]] = defaultdict(dict)
    combinationDict: Dict[Operation, Dict[Tuple[str], Tuple[Dict[str, str]]]] = defaultdict(dict)

    def __init__(self, spec: dict, constraint: str, task: str, operation: Operation,
                 target_param: list = List[AbstractParam], temperature: float = 0.5):
        self._temperature: float = temperature

        self._target_param: list = target_param
        self._constraint: str = constraint
        self._task: str = task
        self._operation = operation
        swagger = Path(os.environ.get("swagger"))
        with swagger.open("r") as fp:
            spec = json.load(fp)
        self._spec: dict = spec
        if self._operation is not None:
            self._method: Method = operation.method
            self._url: str = operation.url.replace(_compile_url(self._spec), "")
            self._opera_info: dict = self._spec["paths"][self._url][self._method.value]

        self._max_query_len: int = 3900
        self.num_calls: int = 0
        self.calling_time: float = 0

        self.prompt = str()
        self.message = list()

        self._complete_model: str = os.getenv("model")
        openai.api_key = os.getenv("openApiKey")

    @property
    def target_param(self) -> list:
        return self._target_param

    @target_param.setter
    def target_param(self, target_param: list):
        self._target_param = target_param

    @property
    def temperature(self) -> float:
        return self._temperature

    @temperature.setter
    def temperature(self, temperature: float):
        self._temperature = temperature

    @property
    def model(self) -> str:
        return self._complete_model

    @model.setter
    def model(self, model: str):
        self._complete_model = model

    @property
    def url(self) -> str:
        return self._url

    @url.setter
    def url(self, url: str):
        self._url = url

    @property
    def method(self) -> str:
        return self._method

    @method.setter
    def method(self, method: str):
        self._method = method

    @property
    def task(self) -> str:
        return self._task

    @task.setter
    def task(self, task: str):
        self._task = task

    @property
    def constraint(self) -> str:
        return self._constraint

    @constraint.setter
    def constraint(self, constraint: str):
        self._constraint = constraint

    # def build_combination(self, request_name, param_info):
    #     prompt = Template.EXPLANATION + Template.TEXT.format(request_name, param_info, self._constraint) + \
    #              TaskTemplate.COMBINATION.format(f"[{', '.join(self._target_param)}]")
    #     return prompt
    #
    # def build_example_value(self, request_name, param_info):
    #     prompt = Template.EXPLANATION + Template.TEXT.format(request_name, param_info, self._constraint) + \
    #              TaskTemplate.SPECIAL_VALUE.format(f"[{', '.join(self._target_param)}]")
    #     return prompt

    def get_param_name_in_list(self):
        param_name_list = [p.name for p in self.target_param]
        return param_name_list

    def build_prompt(self):
        definition = self._spec["definitions"]
        def get_def(definition_dict: dict):
            final_dict = dict()
            required_param_list = definition_dict["required"]
            # required_param_list = [p for p in definition_dict["properties"]]
            properties = dict()
            for param, info in definition_dict["properties"].items():
                if param in required_param_list:
                    properties.update({param: info})
                    if properties[param].get("$ref") != None:
                        new_def_dict = definition[properties[param].get("$ref").split("/")[-1]]
                        new_def_dict_return = get_def(new_def_dict)
                        properties[param] = new_def_dict_return
                    elif properties[param].get("type") == "array" and properties[param].get("items").\
                            get("$ref") is not None:
                        new_def_dict = definition[properties[param].get("items").get("$ref").split("/")[-1]]
                        new_def_dict_return = get_def(new_def_dict)
                        properties[param]["items"] = new_def_dict_return
                final_dict.update(properties)
            return final_dict

        request_name = str(self._method.value) + " " + self._url + " " + self._opera_info.get("description")
        param_info = self._opera_info.get("parameters")
        param_list = self.get_param_name_in_list()
        final_param_info = list()
        for pd in param_info:
            if pd["name"] in param_list:
                final_param_info.append(pd)
        prompt = Template.EXPLANATION + Template.TEXT.format(request_name, final_param_info, self._constraint,
                                                             f"[{', '.join(param_list)}]")
        if self._task == "body":
            body_dict = dict()
            body_ref = ""
            for paramdict in param_info:
                if paramdict.get("in") == "body":
                    body_ref = paramdict["schema"]["$ref"].split("/")[-1]
            body_dict["body"] = get_def(definition[body_ref])
            prompt += Template.BODY_EXPLANATION.format(body_dict) + TaskTemplate.BODY
            return prompt
        else:
            if self._task == "value":
                prompt += TaskTemplate.SPECIAL_VALUE
            elif self._task == "combination":
                prompt += TaskTemplate.COMBINATION
            return prompt


    def save_model_response(self, model_response: dict):
        if self._task == "body":
            value_list = list()
            value_list.append(model_response)
            _OpenAILanguageModel.exampleValueDict[self._operation].update({"body": value_list})
        if self._task == "value":
            _OpenAILanguageModel.exampleValueDict[self._operation].update(model_response)
        if self._task == "combination":
            combination_list = list()
            for k, v in model_response.items():
                combination_list.append(v)
            combination_dict = {tuple(self._target_param): tuple(combination_list)}
            _OpenAILanguageModel.combinationDict.update({self._operation: combination_dict})

    def get_completion(self):
        self.prompt = self.build_prompt()
        num_tokens = num_tokens_from_string(self.prompt, self.model)
        if num_tokens > 3900:
            self.model = "gpt-3.5-turbo-16k-0613"
            if num_tokens_from_string(self.prompt, self.model) > self._max_query_len:
                logger.error("Exceeding the maximum token limit")
        else:
            pass
        self.message.append({"role": "system", "content": Template.SYS_ROLE})
        self.message.append({"role": "user", "content": self.prompt})

        logger.debug("                call language model for operation {}".format(self._operation))
        logger.info("                parameter list to ask: {}".format(self.get_param_name_in_list()))
        start_time = time.time()
        response = openai.ChatCompletion.create(
            model=self.model,
            messages=self.message,
            temperature=0,
        )
        end_time = time.time()
        self.calling_time = end_time - start_time
        logger.info("                Call Complete. Total time: {}".format(self.calling_time))
        self.num_calls += 1
        output_processor = OutputProcessor(task=self._task,
                                           output_to_process=response.choices[0].message["content"],
                                           param_list=self._target_param,
                                           opera_info=self._opera_info)
        message_to_return = output_processor.main()
        self.save_model_response(message_to_return)
        # return response.choices[0].message["content"]
        return message_to_return
