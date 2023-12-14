import json
import os
import time
from pathlib import Path
from typing import List, Dict

import tiktoken
from loguru import logger
from openai import OpenAI

from src.Dto.keywords import Template, TaskTemplate, URL, Loc
from src.Dto.operation import Operation
from src.Dto.parameter import AbstractParam, ObjectParam, ArrayParam
from src.languagemodel.OutputFixer import ValueOutputFixer, CodeGenerationFixer


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
        self._data_path = Path(data_path) / "prompt_response.json"

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
        prompt = Template.EXPLANATION + Template.TEXT.format(self._operation, pInfo, self._operation.constraints,
                                                             param_to_ask) + TaskTemplate.SPECIAL_VALUE
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

    def real_param(self):
        param_list = []
        for param in self._target_param:
            if isinstance(param, ObjectParam) or isinstance(param, ArrayParam):
                for p in param.seeAllParameters():
                    param_list.append(p.getGlobalName())
            else:
                param_list.append(param.name)
        return param_list


class CodeCompleteModel(BasicLanguageModel):
    def __init__(self, operation: Operation, target_param: List[AbstractParam], manager, data_path,
                 temperature: float = 0.7):
        super().__init__(operation, manager, data_path, temperature)

        self._target_param: List[AbstractParam] = target_param
        self._fixer = CodeGenerationFixer(self._manager, self._operation)
        self._complete_model = "gpt-3.5-turbo-instruct"

        logger.debug(f"Use generation model to generate code")

    def build_prompt(self) -> str:
        prompt = "import unittest\nimport requests\n\nclass APITestCase(unittest.TestCase):\n    def test_send_request(self):\n        #This is a test case for a RESTful API\n        #The base url is \"https://127.0.0.1:31080/api/v4\"\n        #The url of the api is \"/projects/50/repository/commits\"\n        #The http method of this request is post\n        #This test case is to create a commit in a branch in a created gitlab project\n        #This request contians 3 parameters. Parameter branch is a string type parameter, it is name of the branch to commit into. Parameter commit_message is a string type parameter, it means Commit message. Parameter actions is a  body type parameter, it is an array of action hashes to commit as a batch, the format of it is 'application/x-www-form-urlencoded'\n        #The items in the array of actions must have 2 required patameters. Parameter action is a string type parameter, it has enum value \"create\", \"delete\", \"move\", \"update\" and \"chmod\". Parameter file_path is a string type parameter, it means the full path to the file.\n        #This request need a Bearer token, the token is \"8b5bfc9f6c6a47c430c03cf2ea6a693972654ffa94b7483d5ded5300ff395689\"\n\n    import unittest\nimport requests\n\nclass APITestCase(unittest.TestCase):\n    def test_send_request(self):\n        #This is a test case for a RESTful API\n        #The base url is \"https://127.0.0.1:31080/api/v4\"\n        #The url of the api is \"/projects/50/repository/commits\"\n        #The http method of this request is post\n        #This test case is to create a commit in a branch in a created gitlab project\n        #This request contians 3 parameters. Parameter branch is a string type parameter, it is name of the branch to commit into. Parameter commit_message is a string type parameter, it means Commit message. Parameter actions is a  body type parameter, it is an array of action hashes to commit as a batch, the format of it is 'application/x-www-form-urlencoded'\n        #The items in the array of actions must have 2 required patameters. Parameter action is a string type parameter, it has enum value \"create\", \"delete\", \"move\", \"update\" and \"chmod\". Parameter file_path is a string type parameter, it means the full path to the file.\n        #This request need a Bearer token, the token is \"8b5bfc9f6c6a47c430c03cf2ea6a693972654ffa94b7483d5ded5300ff395689\"\n\n        #Define the base host\n        self.base_host = \"https://127.0.0.1:31080/api/v4\"\n\n        #Define the rquest url\n        self.url = self.base_host + \"/projects/50/repository/commits\"\n\n        #Define the http request method\n        self.method = \"POST\"\n\n        #Define the request payload\n        self.data = {\"commit_message\": \"commit message\", \"actions\": '[ { \"action\" : \"create\" , \"file_path\": \"app/app.js\", \"content\" : \"puts \\\"Hello, world!\\\" }, { \"action\" : \"delete\", \"file_path\": \"app/views.py\" }, { \"action\" : \"move\", \"file_path\": \"doc/api/index.md\", \"previous_path\": \"docs/api/README.md\" }, { \"action\" : \"update\", \"file_path\": \"app/models/model.py\", \"content\" : \"class Bag(object)\\n def __init__(self):\\n \"\"\"Create bag.\\n See how you can use this API easily now?\\n By the way, we changed the file description that can be seen in a commit.\\n\"\"\"} ]', \"branch\": \"my_branch\"}\n\n        #Define the http request header. It needs authentication info\n        self.header = {\"Content-Type\": \"application/x-www-form-urlencoded\", \"Authorization\": \"Bearer 8b5bfc9f6c6a47c430c03cf2ea6a693972654ffa94b7483d5ded5300ff395689\"}\n\n        #Send the request\n        req = requests.request(method=self.method, url = self.url,data = self.data, headers=self.header)\n\n        #Validate the response status code is 201\n        self.assertEqual(req.status_code, 201,msg='test case failed')\n\n",
        stop_word_list = ["unittest.main()", "if __name__ == '__main__':"]
        return prompt, stop_word_list

    def call(self):
        prompt, stop_list = self.build_prompt()
        response = self._client.completions.create(
            model="gpt-3.5-turbo-instruct",
            prompt=prompt,
            temperature=1,
            max_tokens=2048,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
            stop=["unittest.main()", "if __name__ == '__main__':"]
        )
