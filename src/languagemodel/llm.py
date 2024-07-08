import csv
import time
from pathlib import Path
from typing import Dict, Set

import tiktoken
from loguru import logger
from openai import OpenAI
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.config import Config
from src.factor import *
from src.languagemodel.fixer import *
from src.languagemodel.template import SystemRole, INFO, Task


def get_type(factor):
    if isinstance(factor, StringFactor):
        return "string"
    elif isinstance(factor, NumberFactor):
        return "number"
    elif isinstance(factor, BooleanFactor):
        return "boolean"
    elif isinstance(factor, IntegerFactor):
        return "integer"
    elif isinstance(factor, ArrayFactor):
        return "array"
    elif isinstance(factor, ObjectFactor):
        return "body"


def count_tokens(messages: List[Dict[str, str]], model: str) -> int:
    token_num = 0
    for message in messages:
        string_to_count = message.get("content")
        encoding = tiktoken.encoding_for_model("gpt-4-turbo")
        num_tokens = len(encoding.encode(string_to_count))
        token_num += num_tokens
    logger.info(f"token nums: {token_num}")
    return token_num


class BasicLanguageModel:
    def __init__(self, operation: RestOp, manager, config: Config, temperature: float = 0.7):
        self._operation = operation
        self._manager = manager
        self._temperature: float = temperature
        self._config = config
        self._data_path = Path(config.data_path)
        self._llm_save_path = Path(config.data_path) / "prompt_response.csv"
        # self._max_query_len: int = 3900

        self._model = config.language_model
        api_key = config.language_model_key

        if config.base_url is not None:
            self._client = OpenAI(api_key=api_key, base_url=config.base_url)
        else:
            self._client = OpenAI(api_key=api_key)

    @property
    def temperature(self) -> float:
        return self._temperature

    @temperature.setter
    def temperature(self, temperature: float):
        self._temperature = temperature

    def build_prompt(self) -> str:
        pass

    def build_messages(self) -> List[Dict[str, str]]:
        pass

    def call(self, messages) -> [str, List[Dict[str, str]]]:
        if len(messages) == 0:
            return None, None
        num_tokens = count_tokens(messages, self._model)
        # if num_tokens > self._max_query_len:
        #     logger.warning("Query length exceeds the maximum limit, please reduce the number of tokens")
        #     return "", messages
        count = 0
        while count < 3:
            try:
                start_time = time.time()
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=self._temperature,
                    top_p=0.99,
                    frequency_penalty=0,
                    presence_penalty=0,
                    max_tokens=4096,
                    response_format={"type": "json_object"}
                )
                end_time = time.time()
                logger.info(f"Time taken for response: {end_time - start_time}")
                return response.choices[0].message.content, messages
            except Exception as e:
                logger.error(f"Error in calling language model: {e}")
                logger.error("Retrying...")
                count += 1
        return "", messages

    def execute(self, message=None):
        pass

    def save_message_response(self, message, response):
        if not self._llm_save_path.exists():
            with open(self._llm_save_path, "w") as fp:
                writer = csv.writer(fp, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                # Write the header row
                header = ["operation", "model", "temperature", "messages", "answer"]
                writer.writerow(header)
        with self._llm_save_path.open("a+") as fp:
            writer = csv.writer(fp, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            row_data = [self._operation.__repr__(), self._model, self._temperature, message, response]
            writer.writerow(row_data)


class ResponseModel(BasicLanguageModel):
    def __init__(self, operation: RestOp, manager, config: Config, temperature: float = 0.2,
                 response_list: list = None):
        super().__init__(operation, manager, config, temperature)

        self._response_list: List[(int, object)] = response_list
        self._fixer = ResponseFixer(manager, operation)

        self._model = "gpt-4o"

    @staticmethod
    def calculate_cosine_similarity(string1, string2):
        documents = [string1, string2]
        count_vectorizer = CountVectorizer()
        try:
            sparse_matrix = count_vectorizer.fit_transform(documents)
        except:
            return 1
        cosine_sim = cosine_similarity(sparse_matrix, sparse_matrix)
        similarity_value = cosine_sim[0][1]
        return similarity_value

    def _extract_response_str(self) -> Set[str]:
        response_str_set = set()
        for status_code, response in self._response_list:
            response_str = json.dumps(response)
            if len(response_str) == 0 or response_str in ["''", '""', " ", "", "{}", "[]", "null", "None"]:
                continue
            add = True
            if status_code < 400:
                add = False
            elif len(response_str_set) == 0:
                response_str_set.add(response_str)
                continue
            for added in response_str_set:
                if self.calculate_cosine_similarity(added, response_str) >= 0.7:
                    add = False
                    break
            if add:
                response_str_set.add(response_str)
        return response_str_set

    def build_prompt(self) -> str:
        response_str_set = self._extract_response_str()
        if len(response_str_set) == 0:
            logger.info("No useful response to analyze")
            return ""
        self._manager.save_response_to_file()
        param_list = [f.get_global_name for f in self._operation.get_leaf_factors()]
        prompt = INFO.EXTRACTION.format(self._operation, param_list, response_str_set) + Task.EXTRACTION
        return prompt

    def build_messages(self) -> List[Dict[str, str]]:
        messages = []
        prompt = self.build_prompt()
        if prompt == "":
            return []
        messages.append({"role": "system", "content": SystemRole.SYS_ROLE_EXTRACTION})
        messages.append({"role": "user", "content": prompt})
        return messages

    def execute(self, message=None):
        logger.debug(f"Call language model to parse response for operation {self._operation}")
        messages = self.build_messages()
        if len(messages) == 0:
            return [], "", True
        response, messages = self.call(messages)
        formatted_output, is_success = self._fixer.handle_res(response)
        logger.info(f"Language model answer: {formatted_output}")
        if is_success:
            messages.append({"role": "user", "content": response})
        return messages, formatted_output, is_success


class ValueModel(BasicLanguageModel):
    def __init__(self, operation: RestOp, manager, config: Config, param_to_ask, temperature: float = 0.3):
        super().__init__(operation, manager, config, temperature)

        self._param_to_ask: List[AbstractFactor] = param_to_ask
        self._fixer = ValueFixer(manager, operation, param_to_ask)

    def build_prompt(self) -> str:
        info = list()
        for p in self._param_to_ask:
            info.append(
                {
                    "name": p.get_global_name,
                    "type": get_type(p),
                    "description": p.description,
                    "required": p.required,
                }
            )
        prompt = INFO.VALUE.format(self._operation, info, self._manager.get_pict(self._operation),
                                   self._param_to_ask) + Task.VALUE
        return prompt

    def build_messages(self) -> List[Dict[str, str]]:
        messages = []
        prompt = self.build_prompt()
        messages.append({"role": "system", "content": SystemRole.SYS_ROLE_VALUE})
        messages.append({"role": "user", "content": prompt})
        return messages

    def execute(self, message=None):
        logger.debug(f"Call language model to ask value for operation {self._operation}")
        logger.debug(f"Param to ask: {self._param_to_ask}")
        messages = self.build_messages()
        response, messages = self.call(messages)
        formatted_output, is_success = self._fixer.handle(response, self._param_to_ask)
        logger.info(f"Language model answer: {formatted_output}")
        if is_success:
            messages.append({"role": "user", "content": response})
        return messages, formatted_output, is_success


class IDLModel(BasicLanguageModel):
    def __init__(self, operation: RestOp, manager, config: Config, param_to_ask, temperature: float = 0.1):
        super().__init__(operation, manager, config, temperature)

        self._param_to_ask = param_to_ask
        self._fixer = IDLFixer(manager, operation, param_to_ask)

    def execute(self, message=None):
        logger.debug(f"Call language model to extract idl for operation {self._operation}")
        logger.debug(f"Param to ask: {self._param_to_ask}")
        messages = self.build_messages()
        response, messages = self.call(messages)
        formatted_output, is_success = self._fixer.handle(response)
        logger.info(f"Language model answer: {formatted_output}")
        if is_success:
            messages.append({"role": "user", "content": response})
        return messages, formatted_output, is_success

    def build_messages(self):
        messages = []
        prompt = self.build_prompt()
        messages.append({"role": "system", "content": SystemRole.SYS_ROLE_IDL})
        messages.append({"role": "user", "content": prompt})
        return messages

    def build_prompt(self) -> str:
        info = []
        leaves = [f.get_global_name for f in self._operation.get_leaf_factors()]
        for f in self._param_to_ask:
            info.append(
                {
                    "name": f.get_global_name,
                    "type": get_type(f),
                    "description": f.description,
                }
            )
        prompt = INFO.CONSTRAINT.format(leaves, info)
        prompt += Task.IDL
        return prompt


class PICTModel(BasicLanguageModel):
    def __init__(self, operation: RestOp, manager, config: Config, param_to_ask, temperature: float = 0.1):
        super().__init__(operation, manager, config, temperature)

        self._param_to_ask = param_to_ask
        self._fixer = PICTFixer(manager, operation, param_to_ask)

    def execute(self, message=None):
        logger.debug(f"Call language model to extract pict for operation {self._operation}")
        logger.debug(f"Param to ask: {self._param_to_ask}")
        messages = self.build_messages()
        response, messages = self.call(messages)
        formatted_output, is_success = self._fixer.handle(response)
        logger.info(f"Language model answer: {formatted_output}")
        if is_success:
            messages.append({"role": "user", "content": response})
        return messages, formatted_output, is_success

    def build_messages(self):
        messages = []
        prompt = self.build_prompt()
        messages.append({"role": "system", "content": SystemRole.SYS_ROLE_PICT})
        messages.append({"role": "user", "content": prompt})
        return messages

    def build_prompt(self) -> str:
        info = []
        leaves = [f.get_global_name for f in self._operation.get_leaf_factors()]
        for f in self._param_to_ask:
            info.append(
                {
                    "name": f.get_global_name,
                    "type": get_type(f),
                    "description": f.description,
                }
            )
        prompt = INFO.CONSTRAINT.format(leaves, info)
        prompt += Task.PICT
        return prompt


class SequenceModel:
    def __init__(self, operations: List[RestOp], manager, config: Config, temperature: float = 0.5):
        self._operations = operations
        self._manager = manager
        self._config = config
        self._temperature = temperature

        self._fixer = SequenceFixer(manager, operations)

        self._model = config.language_model
        api_key = config.language_model_key

        if config.base_url is not None:
            self._client = OpenAI(api_key=api_key, base_url=config.base_url)
        else:
            self._client = OpenAI(api_key=api_key)

    def build_messages(self):
        messages = []
        prompt = self.build_prompt()
        prompt = prompt + Task.SEQUENCE
        messages.append({"role": "system", "content": SystemRole.SYS_ROLE_SEQUENCE})
        messages.append({"role": "user", "content": prompt})
        return messages

    def build_error_messages(self):
        messages = []
        prompt = self.build_prompt()
        prompt = prompt + Task.SEQ_ERROR
        messages.append({"role": "system", "content": SystemRole.SYS_ROLE_SEQ_ERROR})
        messages.append({"role": "user", "content": prompt})
        return messages

    def build_prompt(self) -> str:
        info = []
        for operation in self._operations:
            info.append(
                {
                    "name": operation.__repr__(),
                    "description": operation.description,
                }
            )
        prompt = INFO.SEQUENCE.format(info)
        return prompt

    def execute(self):
        logger.debug(f"Call language model to build sequence")
        messages = self.build_messages()
        response, messages = self.call(messages)
        formatted_output, is_success = self._fixer.handle(response)
        logger.info(f"Language model sequence: {formatted_output}")
        return formatted_output, True

    def execute_error(self, operations: List[RestOp]):
        self._operations = operations
        logger.debug(f"Call language model to build error sequence")
        messages = self.build_error_messages()
        response, messages = self.call(messages)
        formatted_output, is_success = self._fixer.handle(response)
        logger.info(f"Language model sequence: {formatted_output}")
        return formatted_output, True

    def call(self, messages) -> [str, List[Dict[str, str]]]:
        if len(messages) == 0:
            return None, None
        count_tokens(messages, self._model)
        while True:
            try:
                start_time = time.time()
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=self._temperature,
                    top_p=0.99,
                    frequency_penalty=0,
                    presence_penalty=0,
                    max_tokens=4096,
                    response_format={"type": "json_object"}
                )
                end_time = time.time()
                logger.info(f"Time taken for response: {end_time - start_time}")
                break
            except Exception as e:
                logger.error(f"Error in calling language model: {e}")
                logger.error("Retrying...")
        return response.choices[0].message.content, messages


class PathModel(BasicLanguageModel):
    def __init__(self, operation: RestOp, manager, config: Config, param_to_ask, operations, temperature: float = 0.2):
        super().__init__(operation, manager, config, temperature)

        self._param_to_ask = param_to_ask
        self._operations = operations
        self._fixer = PathFixer(manager, operation, operations, param_to_ask)

    def execute(self, message=None):
        logger.debug(
            f"Call language model to bind path parameter to the parameter of response of previous operation for the operation {self._operation}")
        logger.debug(f"Param to ask: {self._param_to_ask}")
        logger.info(f"Step 1: Confirm the operations")
        messages = self.build_messages()
        response, messages = self.call(messages)
        self._fixer.handle_operation(response)
        logger.info(f"Step 2: Confirm the parameter")
        messages = self.build_messages(messages)
        if len(messages) == 0:
            return [], "", False
        response, messages = self.call(messages)
        formatted_output, is_success = self._fixer.handle_param(response)
        if is_success:
            logger.info(f"Language model answer: {formatted_output}")
            messages.append({"role": "user", "content": response})
        return messages, formatted_output, is_success

    def build_messages(self, messages=None):
        if messages is None:
            messages = []
            prompt = self.build_prompt()
            messages.append({"role": "system", "content": SystemRole.SYS_ROLE_PATHBINDING})
            messages.append({"role": "user", "content": prompt})
        else:
            prompt = self.build_response_prompt()
            if prompt == "":
                return []
            messages.append({"role": "user", "content": prompt})
        return messages

    def build_prompt(self) -> str:
        info = []
        operations = self._manager.get_success_responses().keys()
        for f in self._param_to_ask:
            info.append(
                {
                    "name": f.get_global_name,
                    "type": get_type(f),
                    "description": f.description,
                }
            )
        prompt = INFO.BINDING.format(self._operation, info, operations)
        prompt += Task.BINDING
        return prompt

    def build_response_prompt(self):
        info = dict()
        factor_operations_dict = self._manager.get_path_binding(self._operation)
        try:
            for f in self._param_to_ask:
                operation = factor_operations_dict.get(f)
                response = self._manager.get_success_responses(operation)
                if operation.responses[0].contents[0][1].__class__.__name__ == "ArrayFactor":
                    example_response = sorted(response, key=lambda x: len(x), reverse=True)[0][0]
                elif operation.responses[0].contents[0][1].__class__.__name__ == "ObjectFactor":
                    example_response = response[0]
                else:
                    example_response = response[0]
                info[operation.__repr__()] = example_response
            prompt = INFO.FIND_PARAMS.format(info) + Task.FIND_PARAMS
            return prompt
        except:
            return ""


class ErrorValueModel(BasicLanguageModel):
    def __init__(self, operation: RestOp, manager, config: Config, temperature: float = 0.3):
        super().__init__(operation, manager, config, temperature)

        self._fixer = ErrorValueFixer(manager, operation, operation.get_leaf_factors())

    def execute(self, message=None):
        logger.debug(f"Call language model to try to find bugs for operation {self._operation}")
        messages = self.build_messages()
        response, messages = self.call(messages)
        formatted_output, is_success = self._fixer.handle(response)
        logger.info(f"Language model answer: {formatted_output}")
        if is_success:
            messages.append({"role": "user", "content": response})
        return messages, formatted_output, is_success
