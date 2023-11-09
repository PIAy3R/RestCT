import abc
from typing import List

from src.generator.meta import AbstractValueGenerator


class AbstractParam(metaclass=abc.ABCMeta):
    # Abstract class for parameters
    def __init__(self, name: str, description: str):
        # Initialize the name and description of the parameter
        self.name = name
        self.description = description

        # Set the required flag to true
        self.required = True
        self.parent: AbstractParam = None

        self.value_generators: List[AbstractValueGenerator] = None
        self._value = None
        self._generator_index = -1

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

        return self._value
