from __future__ import annotations

import abc
from typing import Any, Optional

from src.factor.equivalence import *


class AbstractBindings(AbstractEquivalence, metaclass=abc.ABCMeta):
    def __init__(self, target_op: str, target_param: str, **kwargs):
        self.target_op: str = target_op
        self.target_param: str = target_param

        self._compared_to: Optional[Any] = None
        self.generator: Optional[AbstractEquivalence] = None


class EqualTo(AbstractBindings):
    def __init__(self, target_op: str, target_param: str):
        super().__init__(target_op, target_param)

    def check(self, value) -> bool:
        if self._compared_to is None:
            raise ValueError("Value is not set")
        return value == self._compared_to

    def generate(self) -> Any:
        return self._compared_to

    def __str__(self):
        return f"E: EqualTo {self.target_op}:{self.target_param} = {self._compared_to}"

    def __repr__(self):
        return f"E: EqualTo {self.target_op}:{self.target_param} = {self._compared_to}"


class GreaterThan(AbstractBindings):
    def __init__(self, target_op: str, target_param: str):
        super().__init__(target_op, target_param)

    def check(self, value) -> bool:
        return self.generator.check(value)

    def generate(self) -> Any:
        return self.generator.generate()

    def __str__(self):
        return f"E: GreaterThan {self.target_op}:{self.target_param} = {self._compared_to}"

    def __repr__(self):
        return f"E: GreaterThan {self.target_op}:{self.target_param} = {self._compared_to}"


class LessThan(AbstractBindings):
    def __init__(self, target_op: str, target_param: str):
        super().__init__(target_op, target_param)

    def check(self, value) -> bool:
        return self.generator.check(value)

    def generate(self) -> Any:
        return self.generator.generate()

    def __str__(self):
        return f"E: LessThan {self.target_op}:{self.target_param} = {self._compared_to}"

    def __repr__(self):
        return f"E: LessThan {self.target_op}:{self.target_param} = {self._compared_to}"
