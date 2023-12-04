import os
import string
from random import choice, randint

from src.factor.meta import AbstractFactor, Equivalence


class StringFactor(AbstractFactor):

    def __init__(self, name: str, min_length=1, max_length=100):
        super().__init__(name)

        self.min_length = min_length if min_length > 0 else 1
        self.max_length = max_length if max_length > 0 else 100

    def init_equivalence(self):
        super().init_equivalence()

        # 初始化等价关系
        self.value_equivalence.append(Equivalence(self._value_empty, self._is_value_empty))
        self.value_equivalence.append(Equivalence(self._value_min_length, self._is_value_min_length))
        self.value_equivalence.append(Equivalence(self._value_max_length, self._is_value_max_length))

        if self.max_length - self.min_length > 1:
            self.value_equivalence.append(Equivalence(self._value_length_between_a_b, self._is_value_length_between_a_b,
                                                      (self.min_length + 1, self.max_length - 1),
                                                      (self.min_length + 1, self.max_length - 1)))

    # 生成空字符串
    @staticmethod
    def _value_empty():
        return ""

    # 判断字符串是否为空
    @staticmethod
    def _is_value_empty(v):
        return v == ""

    # 生成指定长度的字符串
    def _value_max_length(self):
        return self.generate_string(self.max_length)

    # 判断字符串长度是否为指定长度
    def _is_value_max_length(self, v):
        return isinstance(v, str) and len(v) == self.max_length

    # 生成指定长度的字符串
    def _value_min_length(self):
        return self.generate_string(self.min_length)

    # 判断字符串长度是否为指定长度
    def _is_value_min_length(self, v):
        return isinstance(v, str) and len(v) == self.min_length

    # 生成指定长度的字符串
    @staticmethod
    def generate_string(length):
        letters = string.ascii_letters + string.digits  # 包括字母和数字
        return ''.join(choice(letters) for _ in range(length))

    # 判断字符串长度是否在指定范围内
    def _value_length_between_a_b(self, a, b):
        length = randint(a, b)
        return self.generate_string(length)

    # 判断字符串长度是否在指定范围内
    @staticmethod
    def _is_value_length_between_a_b(a, b, v):
        if not isinstance(v, str):
            return False
        length = len(v)
        return a < length < b


class BinaryFactor(StringFactor):
    @staticmethod
    def generate_string(length):
        return os.urandom(length)
