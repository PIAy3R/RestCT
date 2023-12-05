import math
import sys
from abc import ABC
from typing import Union, Optional

from src.factor import *
from src.factor.equivalence import *


# Abstract class for numeric parameters
class AbstractNumericFactor(ComparableFactor, ABC):
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

        if min_value >= max_value:
            raise ValueError(f"{self.global_name}, min_value {min_value} must be less than max_value {max_value}")

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


# Integer factor class
class IntegerFactor(AbstractNumericFactor):
    # 32-bit signed integer
    INT_32_MAX = 2 ** 31 - 1
    INT_32_MIN = -2 ** 31

    # 64-bit signed integer
    INT_64_MAX = 2 ** 63 - 1
    INT_64_MIN = -2 ** 63

    # Initialize the parent class
    def __init__(self, name, min_value, max_value, exclusive_min_value=True, exclusive_max_value=True):
        super().__init__(name, min_value, max_value, exclusive_min_value, exclusive_max_value)

    def init_equivalences(self):
        super().init_equivalences()

        if self.boundary_min < 0 < self.boundary_max:
            self.equivalences.append(IntBetween(self.boundary_min, 0))
            self.equivalences.append(Zero())
            self.equivalences.append(IntBetween(0, self.boundary_max))

        else:
            self.equivalences.append(IntBetween(self.boundary_min, self.boundary_max))

        self.equivalences.append(Enumerated(self.boundary_min))
        self.equivalences.append(Enumerated(self.boundary_max))


# Float factor class
class FloatFactor(AbstractNumericFactor):
    # Float
    FLOAT_MAX = sys.float_info.max
    FLOAT_MIN = sys.float_info.min

    # Initialize the parent class
    def __init__(self, name, min_value, max_value, exclusive_min_value=True, exclusive_max_value=True,
                 precision=2):
        super().__init__(name, min_value, max_value, exclusive_min_value, exclusive_max_value)

        # Set the precision
        self.precision = precision

    def init_equivalences(self):
        super().init_equivalences()

        if self.boundary_min < 0 < self.boundary_max:
            self.equivalences.append(FloatBetween(self.boundary_min, 0))
            self.equivalences.append(Zero())
            self.equivalences.append(FloatBetween(0, self.boundary_max))

        else:
            self.equivalences.append(FloatBetween(self.boundary_min, self.boundary_max))

        self.equivalences.append(Enumerated(self.boundary_min))
        self.equivalences.append(Enumerated(self.boundary_max))

    @property
    def printable_value(self):
        if not self.is_active:
            raise ValueError(f"{self.global_name} has not been assigned yet")
        return round(self.value, self.precision)
