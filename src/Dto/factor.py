import abc
import base64
import datetime
import os
import random
import re
import string
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Any, List, Union

from src.Dto.keywords import DataType


class ValueType(Enum):
    Enum = "enum"
    Default = "default"
    Example = "example"
    Random = "random"
    Dynamic = "dynamic"
    Reused = "Reused"
    NULL = "Null"


@dataclass(frozen=True)
class Value:
    val: object = None
    generator: ValueType = ValueType.NULL
    type: DataType = DataType.NULL


class AbstractFactor(metaclass=abc.ABCMeta):
    value_nums = 2
    """
    Abstract class for Factoreters
    """

    def __init__(self, name: str):
        self.name: str = name
        self.description: Optional[str] = None

        # Set the required flag to true
        self.required: bool = False
        self.parent: Optional[AbstractFactor] = None

        self._examples: list = []
        self._default: Optional[Any] = None
        self.format = None
        self.is_constraint = False
        self.domain: list[Value] = list()
        self.isReuse: bool = False

    @staticmethod
    def getRef(ref: str, definitions: dict):
        """get definition with the ref name"""
        return definitions.get(ref.split("/")[-1], {})

    @property
    def is_essential(self):
        return self.is_constraint or self.required

    def see_all_factors(self) -> List:
        """get factors itself and its children"""
        if self.name is None or self.name == "":
            return list()
        else:
            return [self]

    def gen_domain(self):
        pass

    def gen_path(self, op, chain):
        dynamic_values = list()
        response_value = list()
        op_set = chain.keys()
        high_weight, low_weight = AbstractFactor._analyseUrlRelation(op, op_set, self.name)
        for predecessor in high_weight:
            response = chain.get(predecessor)
            similarity_max = 0
            path_depth_minimum = 10
            right_path = None
            right_value = None
            for path, similarity, value in AbstractFactor.findDynamic(self.name, response):
                if similarity > similarity_max:
                    right_path = path
                    path_depth_minimum = len(path)
                    similarity_max = similarity
                    right_value = value
                elif similarity == similarity_max:
                    if len(path) < path_depth_minimum:
                        right_path = path
                        path_depth_minimum = len(path)
                        right_value = value
            if similarity_max > 0 and right_value not in response_value:
                dynamic_values.append((predecessor, right_path))
        if len(dynamic_values) > 0:
            return [Value(v, ValueType.Dynamic, DataType.NULL) for v in dynamic_values]
        else:
            return list()

    @staticmethod
    def _analyseUrlRelation(op, op_set, param_name):
        high_weight = list()
        low_weight = list()
        url = op.path
        for candidate in op_set:
            other_url = candidate.path
            if other_url.strip("/") == url.split("{" + param_name + "}")[0].strip("/"):
                high_weight.append(candidate)
            elif other_url.strip("/") == url.split("{" + param_name + "}")[0].strip("/") + "/{" + param_name + "}":
                high_weight.append(candidate)
            else:
                low_weight.insert(0, candidate)
        return high_weight, low_weight

    @staticmethod
    def findDynamic(paramName, response, path=None):
        if re.search(r"[-_]?id[-_]?", paramName) is not None:
            name = "id"
        if path is None:
            path = []
        if isinstance(response, list):
            local_path = path[:]
            if response:
                for result in AbstractFactor.findDynamic(paramName, response[0], local_path):
                    yield result
        elif isinstance(response, dict):
            for k, v in response.items():
                local_path = path[:]
                similarity = AbstractFactor.match(paramName, k)
                if similarity > 0.9:
                    local_path.append(k)
                    yield local_path, similarity, v
                elif isinstance(v, (list, dict)):
                    local_path.append(k)
                    for result in AbstractFactor.findDynamic(paramName, v, local_path[:]):
                        yield result
        else:
            pass

    @staticmethod
    def match(str_a, str_b):
        str_a = "".join(c for c in str_a if c.isalnum())
        str_b = "".join(c for c in str_b if c.isalnum())
        distance = Levenshtein.distance(str_a.lower(), str_b.lower())
        length_total = len(str_a) + len(str_b)
        return round((length_total - distance) / length_total, 2)

    def __repr__(self):
        return self.get_global_name()

    def get_global_name(self):
        if self.parent is not None:
            return f"{self.parent.get_global_name()}@{self.name}"
        else:
            return self.name

    def __hash__(self):
        return hash(self.get_global_name())

    def __eq__(self, other):
        if isinstance(other, self.__class__) and self.get_global_name() == other.get_global_name():
            return True
        else:
            return False

    def set_description(self, text: str):
        if text is None:
            return
        if text.startswith("'"):
            text = text[1:]
        if text.endswith("'"):
            text = text[:-1]
        if text.startswith('"'):
            text = text[1:]
        if text.endswith('"'):
            text = text[:-1]
        text = text.strip()
        if len(text) == 0:
            return
        self.description = text

    def set_example(self, example):
        parsed_example = self._spilt_example(example)
        if parsed_example is not None:
            for e in parsed_example:
                if e not in self._examples:
                    self._examples.append(e)

    @staticmethod
    def _spilt_example(example) -> Union[list, None]:
        if example is None:
            return None
        if isinstance(example, list):
            return example
        if isinstance(example, dict):
            raise ValueError("Example cannot be a dict")
        return [example]

    def set_default(self, default_value):
        if default_value is not None:
            self._default = default_value


class StringFactor(AbstractFactor):
    def __init__(self, name: str, format: str = None, min_length: int = 0, max_length: int = 100):
        super().__init__(name)
        self.type = DataType.String
        self.format = format
        self.minLength = min_length
        self.maxLength = max_length

    def gen_domain(self):
        self.domain.clear()
        if self._default is not None:
            self.domain.append(Value(self._default, ValueType.Default, DataType.String))
        if len(self._examples) > 0:
            for example in self._examples:
                self.domain.append(Value(example, ValueType.Example, DataType.String))
        if len(self.domain) < self.value_nums:
            while len(self.domain) < self.value_nums:
                if self.format == "date":
                    random_date = datetime.date.fromtimestamp(
                        random.randint(0, int(datetime.datetime.now().timestamp()))).strftime('%Y-%m-%d')
                    self.domain.append(Value(random_date, ValueType.Random, DataType.String))
                elif self.format == "date-time":
                    random_datetime = datetime.datetime.fromtimestamp(
                        random.randint(0, int(datetime.datetime.now().timestamp())))
                    self.domain.append(Value(random_datetime, ValueType.Random, DataType.String))
                elif self.format == "password":
                    random_password_length = random.randint(5, 10)
                    characters = string.ascii_letters + string.digits + string.punctuation
                    password = ''.join(random.choice(characters) for _ in range(random_password_length))
                    self.domain.append(Value(password, ValueType.Random, DataType.String))
                elif self.format == "byte":
                    random_byte_length = random.randint(1, 10)
                    byte_str = base64.b64encode(os.urandom(random_byte_length)).decode('utf-8')
                    self.domain.append(Value(byte_str, ValueType.Random, DataType.String))
                elif self.format == "binary":
                    random_binary_length = random.randint(1, 10)
                    binary_str = ''.join(random.choice(['0', '1']) for _ in range(random_binary_length))
                    self.domain.append(Value(binary_str, ValueType.Random, DataType.String))
                else:
                    characters = string.ascii_letters + string.digits + string.punctuation
                    length = random.randint(self.minLength, self.maxLength)
                    random_string = ''.join(random.choice(characters) for _ in range(length))
                    self.domain.append(Value(random_string, ValueType.Random, DataType.String))

        if not self.required:
            self.domain.append(Value(None, ValueType.NULL, DataType.String))


class IntegerFactor(AbstractFactor):
    def __init__(self, name: str, minimum: int = None, maximum: int = None):
        super().__init__(name)
        self.type = DataType.Integer
        self.minimum = minimum
        self.maximum = maximum

    def gen_domain(self):
        self.domain.clear()
        if self._default is not None:
            self.domain.append(Value(self._default, ValueType.Default, DataType.Integer))
        if len(self._examples) > 0:
            for example in self._examples:
                self.domain.append(Value(example, ValueType.Example, DataType.Integer))
        if len(self.domain) < self.value_nums:
            while len(self.domain) < self.value_nums:
                if self.minimum is not None and self.maximum is not None:
                    random_int = random.randint(self.minimum, self.maximum)
                    self.domain.append(Value(random_int, ValueType.Random, DataType.Integer))
                elif self.minimum is not None:
                    random_int = random.randint(self.minimum, self.minimum + 10000)
                    self.domain.append(Value(random_int, ValueType.Random, DataType.Integer))
                elif self.maximum is not None:
                    random_int = random.randint(self.maximum - 10000, self.maximum)
                    self.domain.append(Value(random_int, ValueType.Random, DataType.Integer))
                else:
                    random_int = random.randint(-10000, 10000)
                    self.domain.append(Value(random_int, ValueType.Random, DataType.Integer))
        if not self.required:
            self.domain.append(Value(None, ValueType.NULL, DataType.Integer))


class NumberFactor(AbstractFactor):
    def __init__(self, name: str, minimum: int = None, maximum: int = None):
        super().__init__(name)
        self.type = DataType.Number
        self.minimum = minimum
        self.maximum = maximum

    def gen_domain(self):
        self.domain.clear()
        if self._default is not None:
            self.domain.append(Value(self._default, ValueType.Default, DataType.Number))
        if len(self._examples) > 0:
            for example in self._examples:
                self.domain.append(Value(example, ValueType.Example, DataType.Number))
        if len(self.domain) < self.value_nums:
            while len(self.domain) < self.value_nums:
                if self.minimum is not None and self.maximum is not None:
                    random_int = random.uniform(self.minimum, self.maximum)
                    self.domain.append(Value(random_int, ValueType.Random, DataType.Number))
                elif self.minimum is not None:
                    random_int = random.uniform(self.minimum, self.minimum + 10000)
                    self.domain.append(Value(random_int, ValueType.Random, DataType.Number))
                elif self.maximum is not None:
                    random_int = random.uniform(self.maximum - 10000, self.maximum)
                    self.domain.append(Value(random_int, ValueType.Random, DataType.Number))
                else:
                    random_int = random.uniform(-1000, 1000)
                    self.domain.append(Value(random_int, ValueType.Random, DataType.Number))
        if not self.required:
            self.domain.append(Value(None, ValueType.NULL, DataType.Number))


class BooleanFactor(AbstractFactor):
    def __init__(self, name: str):
        super().__init__(name)
        self.type = DataType.Bool

    def gen_domain(self):
        self.domain.clear()
        self.domain.append(Value(True, ValueType.Enum, DataType.Bool))
        self.domain.append(Value(False, ValueType.Enum, DataType.Bool))
        if not self.required:
            self.domain.append(Value(None, ValueType.Enum, DataType.Bool))


class ObjectFactor(AbstractFactor):
    def __init__(self, name: str):
        super().__init__(name)
        self.type = DataType.Object

        self.properties: List[AbstractFactor] = []

    def add_property(self, p: AbstractFactor):
        self.properties.append(p)
        p.parent = self

    def gen_domain(self):
        self.domain.clear()
        for p in self.properties:
            p.gen_domain()


class ArrayFactor(AbstractFactor):
    def __init__(self, name: str):
        super().__init__(name)
        self.type = DataType.Array
        self.item: Optional[AbstractFactor] = None

    def set_item(self, item: AbstractFactor):
        self.item = item
        self.item.parent = self

    def gen_domain(self):
        self.domain.clear()
        if self.item is not None:
            self.item.gen_domain()


class EnumFactor(AbstractFactor):
    def __init__(self, name: str, enum_value: list):
        super().__init__(name)
        self.enum_value = enum_value

    def gen_domain(self):
        self.domain.clear()
        for e in self.enum_value:
            self.domain.append(Value(e, ValueType.Enum, DataType.NULL))
        if not self.required:
            self.domain.append(Value(None, ValueType.NULL, DataType.String))
