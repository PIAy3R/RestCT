import abc
from typing import Any


class AbstractEquivalence(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def check(self, value) -> bool: pass

    @abc.abstractmethod
    def generate(self) -> Any: pass

    def __deepcopy__(self, memo):
        return self.__class__()


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

    def __repr__(self):
        return f"E: NULL"


class Enumerated(AbstractEquivalence):
    def __init__(self, value: Any):
        self.value = value

    def check(self, value) -> bool:
        return self.value == value

    def generate(self) -> float:
        return self.value

    def __str__(self):
        return f"E: Enumerated {self.value}"

    def __repr__(self):
        return f"E: Enumerated {self.value}"

    def __deepcopy__(self, memo):
        ins = super().__deepcopy__(memo)
        ins.value = self.value
        return ins
