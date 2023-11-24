import abc
import math
import random
import sys
from typing import Union, Optional

from src.parameter.meta import ComparableParam, Equivalence


# Abstract class for numeric parameters
class AbstractNumericParam(ComparableParam):
    # Initialize the parent class
    """
    self.value_equivalence中的元素只有两种情况：
    1） 数值：表示这个等价类只能取这个值
    2） tuple (a, b): 表示这个等价类可以取a, b之间的任意值x, a < x < b
    """

    def __init__(self, name, min_value, max_value, exclusive_min_value, exclusive_max_value):
        super().__init__(name)

        # Set the min and max values
        self._min_value = min_value
        self._max_value = max_value

        # Set the exclusive min and max values
        self._exclusive_min_value = exclusive_min_value
        self._exclusive_max_value = exclusive_max_value

        self._multiple_of: Optional[Union[int, float]] = None

    def set_multiple_of(self, num: Union[int, float]):
        self._multiple_of = num

    @property
    def boundary_min(self):
        """左边界值：无论包不包含"""
        if math.isinf(self._min_value):
            return -1000
        return self._min_value

    @property
    def boundary_max(self):
        """右边界值：无论包不包含"""
        if math.isinf(self._max_value):
            return 1000
        return self._max_value

    @staticmethod
    def _value_zero():
        return 0

    @staticmethod
    def _is_value_zero(v):
        return v == 0

    @staticmethod
    @abc.abstractmethod
    def _value_between_a_b(a, b):
        pass

    @staticmethod
    def _is_value_between_a_b(a, b, v):
        return a < v < b

    def _value_boundary_max(self):
        return self.boundary_max

    def _value_boundary_min(self):
        return self.boundary_min

    def _is_value_boundary_min(self, v):
        return self.boundary_min == v

    def _is_value_boundary_max(self, v):
        return self.boundary_max == v

    def init_equivalence(self):
        super().init_equivalence()
        self.value_equivalence.append(Equivalence(self._value_boundary_min, self._is_value_boundary_min))
        self.value_equivalence.append(Equivalence(self._value_boundary_max, self._is_value_boundary_max))

        if self.boundary_min < 0 < self.boundary_max:
            self.value_equivalence.append(Equivalence(self._value_zero, self._is_value_zero))
            self.value_equivalence.append(
                Equivalence(self._value_between_a_b, self._is_value_between_a_b, (self.boundary_min, 0),
                            (self.boundary_min, 0)))
            self.value_equivalence.append(
                Equivalence(self._value_between_a_b, self._is_value_between_a_b, (0, self.boundary_max),
                            (0, self.boundary_max)))

        else:
            self.value_equivalence.append(
                Equivalence(self._value_between_a_b, self._is_value_between_a_b, (self.boundary_min, self.boundary_max),
                            (self.boundary_min, self.boundary_max)))


# Integer parameter class
class IntegerParam(AbstractNumericParam):
    # 32-bit signed integer
    INT_32_MAX = 2 ** 31 - 1
    INT_32_MIN = -2 ** 31

    # 64-bit signed integer
    INT_64_MAX = 2 ** 63 - 1
    INT_64_MIN = -2 ** 63

    # Initialize the parent class
    def __init__(self, name, min_value, max_value, exclusive_min_value=True, exclusive_max_value=True):
        super().__init__(name, min_value, max_value, exclusive_min_value, exclusive_max_value)

    @staticmethod
    def _value_between_a_b(a, b):
        return random.randint(a + 1, b - 1)

    def init_equivalence(self):
        if self.boundary_max - self.boundary_min > 1:  # between (self.boundary_min, self.boundary_max) 必须得有值才行
            super().init_equivalence()
        else:
            if not self.required:
                self.value_equivalence.append(Equivalence(self._value_null, self._is_value_null))

            self.value_equivalence.append(Equivalence(self._value_boundary_min, self._is_value_boundary_min))
            self.value_equivalence.append(Equivalence(self._value_boundary_max, self._is_value_boundary_max))


# Float parameter class
class FloatParam(AbstractNumericParam):
    # Float
    FLOAT_MAX = sys.float_info.max
    FLOAT_MIN = sys.float_info.min

    # Initialize the parent class
    def __init__(self, name, min_value, max_value, exclusive_min_value=True, exclusive_max_value=True,
                 precision=2):
        super().__init__(name, min_value, max_value, exclusive_min_value, exclusive_max_value)

        if min_value >= max_value:
            raise ValueError(f"{self.global_name}, min_value {min_value} must be less than max_value {max_value}")
        # Set the precision
        self.precision = precision

    @staticmethod
    def _value_between_a_b(a, b):
        MAX_TRIES = 5
        while MAX_TRIES > 0:
            value = random.uniform(a, b)
            if value != a and value != b:
                return value
            else:
                MAX_TRIES -= 1

    def init_equivalence(self):
        if round(self.boundary_max - self.boundary_min, self.precision) > 0.1 / 10 ** (
                self.precision - 1):  # between (self.boundary_min, self.boundary_max) 必须得有值才行
            super().init_equivalence()
        else:
            if not self.required:
                self.value_equivalence.append(Equivalence(self._value_null, self._is_value_null))

            self.value_equivalence.append(Equivalence(self._value_boundary_min, self._is_value_boundary_min))
            self.value_equivalence.append(Equivalence(self._value_boundary_max, self._is_value_boundary_max))

    @property
    def printable_value(self):
        if self._value is None or self._index == -1:
            raise ValueError(f"{self.global_name} has not been assigned yet")
        return round(self._value, self.precision)
