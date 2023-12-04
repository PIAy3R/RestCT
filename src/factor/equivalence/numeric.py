import random
from typing import Any, Union

from src.factor.equivalence import AbstractEquivalence


class Zero(AbstractEquivalence):
    def check(self, value: Union[int, float]) -> bool:
        return value == 0

    def generate(self) -> Any:
        return 0

    def __str__(self):
        return "E: Zero"

    def __repr__(self):
        return "E: Zero"


class IntBetween(AbstractEquivalence):
    def __init__(self, minimum: int, maximum: int):
        self.min = minimum
        self.max = maximum

    def check(self, value: Union[int, float]) -> bool:
        return self.min < value < self.max

    def generate(self) -> Any:
        return random.randint(self.min, self.max)

    def __str__(self):
        return f"E: Int({self.min},{self.max})"

    def __repr__(self):
        return f"E: Int({self.min},{self.max})"


class FloatBetween(AbstractEquivalence):
    def __init__(self, minimum: float, maximum: float):
        self.min = minimum
        self.max = maximum

    def check(self, value: Union[int, float]) -> bool:
        return self.min < value < self.max

    def generate(self) -> Any:
        return random.uniform(self.min, self.max)

    def __str__(self):
        return f"E: Float({self.min},{self.max})"

    def __repr__(self):
        return f"E: Float({self.min},{self.max})"


class IntPositive(AbstractEquivalence):
    def check(self, value: Union[int, float]) -> bool:
        return value > 0

    def generate(self) -> Any:
        return random.randint(1, 1000)

    def __str__(self):
        return "E: IntPositive"

    def __repr__(self):
        return "E: IntPositive"


class IntNegative(AbstractEquivalence):
    def check(self, value: Union[int, float]) -> bool:
        return value < 0

    def generate(self) -> Any:
        return random.randint(-1000, -1)

    def __str__(self):
        return "E: IntNegative"

    def __repr__(self):
        return "E: IntNegative"


class FloatPositive(AbstractEquivalence):
    def check(self, value: Union[int, float]) -> bool:
        return value > 0

    def generate(self) -> Any:
        return random.uniform(0.1, 1000)

    def __str__(self):
        return "E: FloatPositive"

    def __repr__(self):
        return "E: FloatPositive"


class FloatNegative(AbstractEquivalence):
    def check(self, value: Union[int, float]) -> bool:
        return value < 0

    def generate(self) -> Any:
        return random.uniform(-1000, -0.1)

    def __str__(self):
        return "E: FloatNegative"

    def __repr__(self):
        return "E: FloatNegative"


class Boundary(AbstractEquivalence):
    def __init__(self, boundary: Union[int, float]):
        self.boundary = boundary

    def check(self, value: Union[int, float]) -> bool:
        return value == self.boundary

    def generate(self) -> Any:
        return self.boundary

    def __str__(self):
        return f"E: {self.boundary}"

    def __repr__(self):
        return f"E: {self.boundary}"
