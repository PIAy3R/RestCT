import abc
from typing import List


class AbstractParam(metaclass=abc.ABCMeta):
    # Abstract class for parameters
    def __init__(self, name: str):
        # Initialize the name and description of the parameter
        self.name = name
        self._description = None

        # Set the required flag to true
        self.required = True
        self.parent: AbstractParam = None

        self.value_generators: List[AbstractValueGenerator] = None
        self._value = None
        self._generator_index = -1

    @property
    def description(self):
        return self._description

    @description.setter
    def description(self, text: str):
        # todo: format text with nlp
        if text is None or len(text) == 0:
            raise ValueError("Description cannot be empty")
        self._description = text

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = value

    @property
    def generator_index(self):
        return self._generator_index

    @generator_index.setter
    def generator_index(self, index):
        self._generator_index = index

    def flat_view(self) -> tuple:
        return self,

    @property
    def global_name(self):
        if self.parent is not None:
            return f"{self.parent.global_name}.{self.name}"
        else:
            return self.name

    def printable_value(self):
        if self._value is None or self._generator_index == -1:
            raise ValueError(f"{self.global_name} has not been assigned yet")

        return self.value


class AbstractValueGenerator(metaclass=abc.ABCMeta):
    def __init__(self):
        self.unique = True

    @abc.abstractmethod
    def generate(self): pass

    @abc.abstractmethod
    def has_instance(self, value) -> bool: pass


class NullGenerator(AbstractValueGenerator):
    def generate(self):
        return "__null__"

    def has_instance(self, value) -> bool:
        return value == "__null__"
