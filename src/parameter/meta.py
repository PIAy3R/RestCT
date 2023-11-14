import abc
import dataclasses
from typing import List, Callable


@dataclasses.dataclass(frozen=True)
class Equivalence:
    generate: Callable
    check: Callable
    g_args: tuple = ()
    c_args: tuple = ()


class AbstractParam(metaclass=abc.ABCMeta):
    # Abstract class for parameters
    def __init__(self, name: str):
        # Initialize the name and description of the parameter
        self.name = name
        self._description = None

        # Set the required flag to true
        self.required = True
        self.parent: AbstractParam = None

        # 参数值等价类
        self.value_equivalence: List[Equivalence] = []
        # 当前选择的是第几个等价类
        self._index = -1
        # 当前等价类生成的值
        self._value = None

    def init_equivalence(self):
        if not self.required:
            self.value_equivalence.append(Equivalence(self._value_null, self._is_value_null))

    @staticmethod
    def _value_null():
        return "__null__"

    @staticmethod
    def _is_value_null(v):
        return v == "__null__"

    @property
    def description(self):
        return self._description

    @description.setter
    def description(self, text: str):
        # todo: format text with nlp
        if text is None or len(text) == 0:
            raise ValueError("Description cannot be empty")
        self._description = text

    def flat_view(self) -> tuple:
        return self,

    @property
    def global_name(self):
        if self.parent is not None:
            return f"{self.parent.global_name}.{self.name}"
        else:
            return self.name

    @property
    def printable_value(self):
        if self._value is None or self._index == -1:
            raise ValueError(f"{self.global_name} has not been assigned yet")
        return self._value


class ComparableParam(AbstractParam):
    def __init__(self, name: str):
        super().__init__(name)

    def __eq__(self, o: object) -> bool:
        if not isinstance(o, self.__class__):
            raise TypeError(f"{self.__class__} cannot be compared to {o.__class__}")
        if self._value is not None and o._value is not None:
            return self._value == o._value
        raise ValueError(f"{self.global_name}.value or {o.global_name}.value is None")

    def __ne__(self, o: object) -> bool:
        if not isinstance(o, self.__class__):
            raise TypeError(f"{self.__class__} cannot be compared to {o.__class__}")
        if self._value is not None and o._value is not None:
            return self._value != o._value
        raise ValueError(f"{self.global_name}.value or {o.global_name}.value is None")

    def __lt__(self, o: object) -> bool:
        if not isinstance(o, self.__class__):
            raise TypeError(f"{self.__class__} cannot be compared to {o.__class__}")
        if self._value is not None and o._value is not None:
            return self._value < o._value
        raise ValueError(f"{self.global_name}.value or {o.global_name}.value is None")

    def __le__(self, o: object) -> bool:
        if not isinstance(o, self.__class__):
            raise TypeError(f"{self.__class__} cannot be compared to {o.__class__}")
        if self._value is not None and o._value is not None:
            return self._value <= o._value
        raise ValueError(f"{self.global_name}.value or {o.global_name}.value is None")

    def __gt__(self, o: object) -> bool:
        if not isinstance(o, self.__class__):
            raise TypeError(f"{self.__class__} cannot be compared to {o.__class__}")
        if self._value is not None and o._value is not None:
            return self._value > o._value
        raise ValueError(f"{self.global_name}.value or {o.global_name}.value is None")

    def __ge__(self, o: object) -> bool:
        if not isinstance(o, self.__class__):
            raise TypeError(f"{self.__class__} cannot be compared to {o.__class__}")
        if self._value is not None and o._value is not None:
            return self._value >= o._value
        raise ValueError(f"{self.global_name}.value or {o.global_name}.value is None")


class EnumParam(AbstractParam):
    """
    EnumParam is a parameter that can only take one of a set of values.
    """

    def __init__(self, name: str, enum_value: list):
        super().__init__(name)
        self._enums = enum_value

    def init_equivalence(self):
        super().init_equivalence()

        if self._enums is None or len(self._enums) == 0:
            raise ValueError(f"{self.global_name}.enums is empty")

        for index in range(len(self._enums)):
            self.value_equivalence.append(Equivalence(self._value_enum, self._is_value_enum, (index,), (index,)))

    def _value_enum(self, index):
        return self._enums[index]

    def _is_value_enum(self, index, value):
        return self._enums[index] == value


class DynamicParam(AbstractParam):
    """
    Dynamic parameter is a parameter that bind with another parameter.
    """

    def __init__(self, name: str, target_op_id: str, target_global_name: str):
        super().__init__(name)
        self._target_op_id = target_op_id
        self._target_global_name = target_global_name

        self._dynamic_value = None

    def init_equivalence(self):
        super().init_equivalence()

        if self._dynamic_value is not None:
            self.value_equivalence.append(Equivalence(self._dynamic_value, self._is_dynamic_value))

    def _value_dynamic(self):
        if self._dynamic_value is None:
            raise ValueError(f"{self.global_name}.dynamic_value is None")
        return self._dynamic_value

    def _is_value_dynamic(self, v):
        return self._dynamic_value == v

    def set_dynamic_value(self, response_chain: dict):
        if self._target_op_id not in response_chain.keys():
            raise ValueError(f"{self.global_name}.target_op_id({self._target_op_id}) not in response_chain")
        response = response_chain.get(self._target_op_id)

        if isinstance(response, list):
            if len(response) == 0:
                raise ValueError(f"{self.global_name}.target_op_id({self._target_op_id}) response is empty")
            if len(response) > 1:
                response = response[0]

        if self._target_global_name in response.keys():
            self._dynamic_value = response.get(self._target_global_name)
        else:
            raise ValueError(f"{self.global_name}.target_global_name({self._target_global_name}) not in response")
