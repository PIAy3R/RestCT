import re
import string
from random import choice, randint
from typing import Any

from src.factor.equivalence import AbstractEquivalence


class Empty(AbstractEquivalence):
    def check(self, value) -> bool:
        return isinstance(value, str) and value == ""

    def generate(self) -> Any:
        return ""

    def __str__(self):
        return "E: Empty"

    def __repr__(self):
        return "E: Empty"


class FixedLength(AbstractEquivalence):
    def __init__(self, length: int):
        self.length = length

    def check(self, value) -> bool:
        return isinstance(value, str) and len(value) == self.length

    def generate(self) -> Any:
        letters = string.ascii_letters + string.digits
        return ''.join(choice(letters) for _ in range(self.length))

    def __str__(self):
        return f"E: FixedLength({self.length})"

    def __repr__(self):
        return f"E: FixedLength({self.length})"


class VariableLength(AbstractEquivalence):
    def __init__(self, minimum: int, maximum: int):
        self.min = minimum
        self.max = maximum

    def check(self, value) -> bool:
        return isinstance(value, str) and self.min <= len(value) <= self.max

    def generate(self) -> Any:
        letters = string.ascii_letters + string.digits
        length = randint(self.min, self.max)
        return ''.join(choice(letters) for _ in range(length))

    def __str__(self):
        return f"E: VariableLength({self.min}, {self.max})"

    def __repr__(self):
        return f"E: VariableLength({self.min}, {self.max})"


class Regex(AbstractEquivalence):
    def __init__(self, regex: str):
        self.regex = regex

    def check(self, value) -> bool:
        return isinstance(value, str) and re.match(self.regex, value)

    def generate(self) -> Any:
        """generate a string that matches regex pattern"""
        raise ValueError("Not implemented")

    def __str__(self):
        return f"E: Regex({self.regex})"

    def __repr__(self):
        return f"E: Regex({self.regex})"
