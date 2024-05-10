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
from src.template import SystemRole, Explanation, Task


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
        encoding = tiktoken.encoding_for_model(model)
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
        self._constraint: list = operation.constraints
        self._llm_save_path = Path(config.data_path) / "prompt_response.csv"
        self._max_query_len: int = 3900

        self._model = config.language_model
        api_key = config.language_model_key

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
        if num_tokens > self._max_query_len:
            logger.warning("Query length exceeds the maximum limit, please reduce the number of tokens")
            return "", messages
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
            except:
                print("Call failed, retrying...")
        return response.choices[0].message.content, messages

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

        self._model = "gpt-4-1106-preview"

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
        param_list = [f.get_global_name for f in self._operation.get_leaf_factors()]
        prompt = Explanation.EXPLANATION_RESPONSE + Explanation.TEXT_RESPONSE.format(self._operation, param_list,
                                                                                     response_str_set) + Task.GROUP
        return prompt

    def build_messages(self) -> List[Dict[str, str]]:
        messages = []
        prompt = self.build_prompt()
        if prompt == "":
            return []
        messages.append({"role": "system", "content": SystemRole.SYS_ROLE_RESPONSE})
        messages.append({"role": "user", "content": prompt})
        return messages

    def execute(self, message=None):
        logger.debug(f"Call language model to parse response for operation {self._operation}")
        messages = self.build_messages()
        response, messages = self.call(messages)
        formatted_output, is_success = self._fixer.handle_res(response, self._data_path)
        logger.info(f"Language model answer: {formatted_output}")
        if is_success:
            messages.append({"role": "user", "content": response})
        return messages, formatted_output, is_success


class ValueModel(BasicLanguageModel):
    def __init__(self, operation: RestOp, manager, config: Config, param_to_ask, temperature: float = 0.9):
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
        prompt = Explanation.EXPLANATION_VALUE + Explanation.TEXT_VALUE.format(self._operation, info,
                                                                               self._operation.constraints,
                                                                               self._param_to_ask) + Task.SPECIAL_VALUE
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
    def __init__(self, operation: RestOp, manager, config: Config, param_to_ask, temperature: float = 0.2):
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
        messages.append({"role": "system", "content": SystemRole.SYS_ROLE_RESPONSE})
        messages.append({"role": "user", "content": prompt})
        return messages

    def build_prompt(self) -> str:
        info = []
        for f in self._param_to_ask:
            info.append(
                {
                    "name": f.get_global_name,
                    "type": get_type(f),
                    "description": f.description,
                }
            )
        prompt = Explanation.TEXT_RES_RESPONSE.format(info)
        return prompt
