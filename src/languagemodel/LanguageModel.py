import csv
import json
import os
import time
from pathlib import Path
from typing import List, Dict, Set

import tiktoken
from loguru import logger
from openai import OpenAI

from lib.Template import Template, TaskTemplate
from src.Dto.keywords import URL, Loc
from src.Dto.operation import Operation
from src.Dto.parameter import AbstractParam, ObjectParam, ArrayParam
from src.languagemodel.OutputFixer import ValueOutputFixer, ResponseFixer


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


def get_info(param, definition, def_dict, body):
    for split_name in param.getGlobalName().split("@"):
        if split_name == body.name:
            continue
        elif split_name == "_item":
            if def_dict.get("items").get("$ref") is not None:
                ref = def_dict.get("items").get("$ref").split("/")[-1]
                def_dict = definition.get(ref)
            else:
                def_dict = def_dict.get("items")
        else:
            if def_dict.get("properties") is not None:
                info = def_dict.get("properties").get(split_name)
            elif def_dict.get("$ref") is not None:
                ref = def_dict.get("$ref").split("/")[-1]
                def_dict = definition.get(ref)
                info = def_dict.get("properties").get(split_name)
            else:
                info = def_dict
            def_dict = info
    return info


class BasicLanguageModel:
    def __init__(self, operation: Operation, manager, data_path, temperature: float = 0.7):
        self._temperature: float = temperature

        self._operation = operation
        self._manager = manager
        self._constraint: list = operation.constraints
        self._data_path = Path(data_path)
        self._llm_data_path = Path(data_path) / "prompt_response.csv"
        self._max_query_len: int = 3900

        swagger = Path(os.getenv("swagger"))
        with swagger.open("r") as fp:
            self._spec = json.load(fp)

        self._complete_model: str = os.environ.get("model")
        api_key = os.environ.get("language_model_key")
        self._client = OpenAI(api_key=api_key)
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

    def call_without_res(self):
        message = self.build_message()
        num_tokens = num_tokens_from_string(message, self._complete_model)
        if num_tokens > self._max_query_len:
            self._complete_model = "gpt-3.5-turbo-16k"
            recount_tokens = num_tokens_from_string(message)
            if recount_tokens > 16384:
                logger.warning("Exceeding the maximum token limit")
                return
        start_time = time.time()
        response = self._client.chat.completions.create(
            model=self._complete_model,
            messages=message,
            temperature=self._temperature,
            response_format={"type": "json_object"}
        )
        end_time = time.time()
        self._manager.update_llm_data((self._complete_model, response.usage.total_tokens, num_tokens),
                                      end_time - start_time)
        logger.info(f"call time: {end_time - start_time} s")
        return response.choices[0].message.content, message

    def execute(self, message_res):
        pass

    def save_message_and_response(self, message, response):
        if not self._llm_data_path.exists():
            with self._llm_data_path.open("a+") as fp:
                writer = csv.writer(fp, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                # Write the header row
                header = ["operation", "model", "temperature", "messages", "llm_response"]
                writer.writerow(header)
        with self._llm_data_path.open("a+") as fp:
            writer = csv.writer(fp, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            row_data = [self._operation.__repr__(), self._complete_model, self._temperature, message, response]
            writer.writerow(row_data)


class ParamValueModel(BasicLanguageModel):
    def __init__(self, operation: Operation, target_param: List[AbstractParam], manager, data_path,
                 temperature: float = 0.7):
        super().__init__(operation, manager, data_path, temperature)

        self._target_param: List[AbstractParam] = target_param
        self._fixer = ValueOutputFixer(self._manager, self._operation)

        logger.debug(f"target parameter list: {self._target_param}")

    def build_prompt(self) -> str:
        pInfo, param_to_ask = self.get_param_info()
        prompt = Template.EXPLANATION_VALUE + Template.TEXT_VALUE.format(self._operation, pInfo,
                                                                         self._operation.constraints,
                                                                         param_to_ask) + TaskTemplate.SPECIAL_VALUE
        return prompt

    def build_message(self) -> List[Dict[str, str]]:
        message = []
        prompt = self.build_prompt()
        message.append({"role": "system", "content": Template.SYS_ROLE_VALUE})
        message.append({"role": "user", "content": prompt})
        return message

    def execute(self, message_res=None):
        if message_res is None:
            response_str, message = self.call_without_res()
        else:
            response_str, message = self.call_with_res(message_res)
        parameters = self._spec.get("paths").get(self._operation.url.replace(URL.baseurl, "")).get(
            self._operation.method.value).get("parameters")
        formatted_output = self._fixer.handle(response_str, parameters)
        logger.info(f"Language model answer: {formatted_output}")
        self.save_message_and_response(message, formatted_output)

    def real_param(self):
        param_list = []
        for param in self._target_param:
            if isinstance(param, ObjectParam) or isinstance(param, ArrayParam):
                for p in param.seeAllParameters():
                    param_list.append(p.getGlobalName())
            else:
                param_list.append(param.name)
        return param_list

    def get_param_info(self):
        pInfo = []
        param_to_ask = []
        parameters = self._spec.get("paths").get(self._operation.url.replace(URL.baseurl, "")).get(
            self._operation.method.value).get("parameters")
        definitions = self._spec.get("definitions")
        for p in self._target_param:
            for info in parameters:
                if info.get("name") == p.name:
                    if p.loc is not Loc.Body:
                        pInfo.append(info)
                        param_to_ask.append(p.getGlobalName())
                    else:
                        all_param = p.seeAllParameters()
                        if len(all_param) > 0:
                            ref = info["schema"].get("$ref").split("/")[-1]
                            def_dict = definitions[ref]
                            for ap in all_param:
                                add_info = get_info(ap, definitions, def_dict, p)
                                if add_info.get('enum') is None and add_info.get('type') != "boolean":
                                    add_info.update({"name": ap.getGlobalName()})
                                    pInfo.append(add_info)
                                    param_to_ask.append(ap.getGlobalName())
                        else:
                            pInfo.append(info)
                            param_to_ask.append(p.getGlobalName())
        return pInfo, param_to_ask

    def call_with_res(self, message_res):
        self._complete_model = "gpt-4-1106-preview"
        self.temperature = 0.9
        message = message_res
        pInfo, param_to_ask = self.get_param_info()
        prompt = Template.TEXT_RES_VALUE.format(pInfo, param_to_ask) + TaskTemplate.RES_VALUE
        message.append({"role": "user", "content": prompt})
        num_tokens = num_tokens_from_string(message, self._complete_model)
        # if num_tokens > self._max_query_len:
        #     self._complete_model = "gpt-3.5-turbo-16k"
        #     recount_tokens = num_tokens_from_string(message)
        #     if recount_tokens > 16384:
        #         logger.warning("Exceeding the maximum token limit")
        #         return
        start_time = time.time()
        response = self._client.chat.completions.create(
            model=self._complete_model,
            messages=message,
            temperature=self._temperature,
            top_p=0.99,
            frequency_penalty=0,
            presence_penalty=0,
            max_tokens=4096,
            response_format={"type": "json_object"}
        )
        end_time = time.time()
        self._manager.update_llm_data((self._complete_model, response.usage.total_tokens, num_tokens),
                                      end_time - start_time)
        logger.info(f"call time: {end_time - start_time} s")
        return response.choices[0].message.content, message


class ResponseModel(BasicLanguageModel):
    def __init__(self, operation: Operation, manager, data_path, response_list: list = None, temperature: float = 0.9):
        super().__init__(operation, manager, data_path, temperature)

        self._response_list: List[(int, object)] = response_list

        self._fixer = ResponseFixer(self._manager, self._operation)

        self._complete_model = "gpt-4-1106-preview"

        logger.debug(f"Use llm to handel test cases responses")

    def _extract_response_str(self) -> Set[str]:
        response_str_set = set()
        for status_code, response_str in self._response_list:
            response_str_set.add(json.dumps(response_str))
        return response_str_set

    def _get_all_param(self):
        param_list = []
        for param in self.operation.parameterList:
            if isinstance(param, ObjectParam) or isinstance(param, ArrayParam):
                for p in param.seeAllParameters():
                    param_list.append(p.getGlobalName())
            else:
                param_list.append(param.name)
        return param_list

    def build_extract_prompt(self) -> str:
        response_str_set = self._extract_response_str()
        param_list = self._get_all_param()
        prompt = (Template.EXPLANATION_RESPONSE + Template.TEXT_RESPONSE.format(self._operation, param_list,
                                                                                response_str_set)
                  + TaskTemplate.EXTRACT_PARAM)
        return prompt

    def build_messages(self, message, task) -> List[Dict[str, str]]:
        messages = message
        if task == "extract":
            prompt = self.build_extract_prompt()
            messages.append({"role": "system", "content": Template.SYS_ROLE_RESPONSE})
            messages.append({"role": "user", "content": prompt})
        elif task == "classify":
            messages.append({"role": "user", "content": TaskTemplate.CLASSIFY})
        elif task == "group":
            messages.append({"role": "user", "content": TaskTemplate.GROUP})
        return messages

    def execute(self, message_res=None):
        (extract_output, extract_message, classify_output, classify_message,
         group_output, group_message, group_response_str) = self.call_without_res()
        final_message = group_message.copy()
        final_message.append({"role": "user", "content": group_response_str})
        logger.info(f"Call language model to parse response complete")
        return final_message
        # return extract_output, extract_message, classify_output, classify_message, group_output, group_message

    def _call_model(self, message):
        num_tokens = num_tokens_from_string(message, self._complete_model)
        if num_tokens > 16000:
            return
        start_time = time.time()
        response = self._client.chat.completions.create(
            model=self._complete_model,
            messages=message,
            temperature=self._temperature,
            top_p=0.99,
            frequency_penalty=0,
            presence_penalty=0,
            max_tokens=4096,
            response_format={"type": "json_object"}
        )
        end_time = time.time()
        logger.info(f"call time: {end_time - start_time} s")
        return response

    def call_extract_parameter(self):
        logger.debug(f"call language model for to extract parameters from response")
        extract_message = self.build_messages([], "extract")
        response = self._call_model(extract_message)
        formatted_output_extract = self._fixer.handle_parameter(response.choices[0].message.content)
        logger.info(f"Language model answer: {formatted_output_extract}")
        self.save_message_and_response(extract_message, formatted_output_extract)
        return extract_message, formatted_output_extract, response.choices[0].message.content

    def call_classify(self, extract_message, extract_response_str):
        logger.debug(f"call language model for to classify error cause")
        classify_message = extract_message.copy()
        classify_message.append({"role": "user", "content": extract_response_str})
        classify_message = self.build_messages(classify_message, "classify")
        response = self._call_model(classify_message)
        formatted_output_classify = self._fixer.handle_cause(response.choices[0].message.content)
        logger.info(f"Language model answer: {formatted_output_classify}")
        self.save_message_and_response(classify_message, formatted_output_classify)
        return classify_message, formatted_output_classify, response.choices[0].message.content

    def call_group(self, classify_message, classify_response_str):
        logger.debug(f"call language model to group error cause")
        group_message = classify_message.copy()
        group_message.append({"role": "user", "content": classify_response_str})
        group_message = self.build_messages(group_message, "group")
        response = self._call_model(group_message)
        formatted_output_group = self._fixer.handle_group(response.choices[0].message.content, self._data_path)
        logger.info(f"Language model answer: {formatted_output_group}")
        self.save_message_and_response(group_message, formatted_output_group)
        return group_message, formatted_output_group, response.choices[0].message.content

    def call_without_res(self):
        extract_message, formatted_output_extract, extract_response_str = self.call_extract_parameter()
        if len(formatted_output_extract) == 0:
            logger.info("No parameter extracted")
            return formatted_output_extract, extract_message, None, None, None, None
        else:
            classify_message, formatted_output_classify, classify_response = self.call_classify(extract_message,
                                                                                                extract_response_str)
            flag = False
            for p, rl in formatted_output_classify.items():
                if 2 in rl:
                    flag = True
                    break
            if not flag:
                logger.info("No constraint found")
                return formatted_output_extract, extract_message, formatted_output_classify, classify_message, None, None
            else:
                group_message, formatted_output_group, group_response = self.call_group(classify_message,
                                                                                        classify_response)
                return (formatted_output_extract, extract_message, formatted_output_classify, classify_message,
                        formatted_output_group, group_message, group_response)
