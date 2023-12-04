import abc
from typing import Any


class AbstractEquivalence(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def check(self, value) -> bool: pass

    @abc.abstractmethod
    def generate(self) -> Any: pass


class Null(AbstractEquivalence):
    NULL_STRING = "__null__"

    def check(self, value) -> bool:
        if value == Null.NULL_STRING:
            return True
        return False

    def generate(self) -> str:
        return Null.NULL_STRING

    def __str__(self):
        return f"E: NULL"
