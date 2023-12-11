import abc
import copy
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Dict, Union

from src.factor.equivalence import *


class AbstractBindings(AbstractEquivalence, metaclass=abc.ABCMeta):
    class TYPES(Enum):
        INT = "integer"
        FLOAT = "float"
        DATE = "date"
        DATETIME = "datetime"
        TIME = "time"

    NOT_SET = "__NOT_SET__"

    def __init__(self, target_op: str, target_param: str, p_type, **kwargs):
        if p_type not in AbstractBindings.TYPES.__members__.values():
            raise ValueError(f"type({p_type}) is not supported")

        self.target_op: str = target_op
        self.target_param: str = target_param
        self.type: AbstractBindings.TYPES = p_type

        self._compared_to: Optional[Union[str, int, float, datetime]] = None
        self.generator: Optional[AbstractEquivalence] = None

        for key, value in kwargs.items():
            setattr(self, key, value)

    def update(self, inputs: Dict[str, Any] = None, responses: Dict[str, Union[list, dict]] = None) -> None:
        """
        @param inputs: all leaves of input parameters
        @param responses: list as received
        """
        if inputs is not None and responses is not None:
            raise ValueError("inputs and responses cannot be both set")
        if inputs is None and responses is None:
            raise ValueError("inputs and responses cannot be both None")

        if inputs is not None:
            if self.target_param not in inputs.keys():
                raise ValueError(f"target_param({self.target_param}) does not exist")
            self._compared_to = inputs.get(self.target_param)
        if responses is not None:
            self._update_with_response(responses)

        self._update_comparator()

    def _update_with_response(self, responses: Dict[str, Union[list, dict]]):
        if self.target_op not in responses.keys():
            raise ValueError(f"target_op_id({self.target_op}) response does not exist")
        response = responses.get(self.target_op)
        if isinstance(response, list):
            if len(response) == 0:
                raise ValueError(f"target_op_id({self.target_op}) response is empty")
            else:
                response = response[0]

        if self.target_param in response.keys():
            self._compared_to = response.get(self.target_param)
        else:
            raise ValueError(f"target_op({self.target_op}) response has no key({self.target_param})")

    @abc.abstractmethod
    def _update_comparator(self):
        """
        set self.generator
        """""
        pass

    def generate(self) -> Any:
        if self.generator is None:
            return AbstractBindings.NOT_SET
        return self.generator.generate()

    def check(self, value) -> bool:
        if self.generator is None:
            raise ValueError("Value is not set")
        return self.generator.check(value)

    def __deepcopy__(self, memo):
        ins = self.__class__(self.target_op, self.target_param, self.type)

        for key, value in self.__dict__.items():
            setattr(ins, key, copy.deepcopy(value, memo))
        return ins

    def __eq__(self, other):
        if isinstance(other, EqualTo):
            return self.target_op == other.target_op and self.target_param == other.target_param
        return False


class EqualTo(AbstractBindings):
    def __init__(self, target_op: str, target_param: str, p_type: AbstractBindings.TYPES, **kwargs):
        super().__init__(target_op, target_param, p_type, **kwargs)

    def _update_comparator(self):
        if self._compared_to is None:
            raise ValueError("Value is not set")

        self.generator = Enumerated(self._compared_to)

    def __str__(self):
        return f"E: EqualTo {self.target_op}:{self.target_param} = {self._compared_to}"

    def __repr__(self):
        return f"E: EqualTo {self.target_op}:{self.target_param} = {self._compared_to}"


class GreaterThan(AbstractBindings):
    def __init__(self, target_op: str, target_param: str, p_type: AbstractBindings.TYPES, **kwargs):
        super().__init__(target_op, target_param, p_type, **kwargs)

    def _update_comparator(self):
        if self._compared_to is None:
            raise ValueError("Value is not set")

        maximum = self.maximum if hasattr(self, "maximum") else self._compared_to + 1000

        if self.type is AbstractBindings.TYPES.INT:
            self.generator = IntBetween(self._compared_to, maximum)
        elif self.type is AbstractBindings.TYPES.FLOAT:
            self.generator = FloatBetween(self._compared_to, maximum)
        elif self.type is AbstractBindings.TYPES.DATE:
            self.generator = DateBetween(self._compared_to, maximum)
        elif self.type is AbstractBindings.TYPES.DATETIME:
            self.generator = DateTimeBetween(self._compared_to, maximum)
        elif self.type is AbstractBindings.TYPES.TIME:
            self.generator = TimeBetween(self._compared_to, maximum)
        else:
            raise ValueError(f"type({self.type}) is not supported")

    def __str__(self):
        return f"E: GreaterThan {self.target_op}:{self.target_param} = {self._compared_to}"

    def __repr__(self):
        return f"E: GreaterThan {self.target_op}:{self.target_param} = {self._compared_to}"


class LessThan(AbstractBindings):
    def __init__(self, target_op: str, target_param: str, p_type: AbstractBindings.TYPES, **kwargs):
        super().__init__(target_op, target_param, p_type, **kwargs)

    def _update_comparator(self):
        if self._compared_to is None:
            raise ValueError("Value is not set")

        minimum = self.minimum if hasattr(self, "minimum") else self._compared_to - 1000

        if self.type is AbstractBindings.TYPES.INT:
            self.generator = IntBetween(minimum, self._compared_to)
        elif self.type is AbstractBindings.TYPES.FLOAT:
            self.generator = FloatBetween(minimum, self._compared_to)
        elif self.type is AbstractBindings.TYPES.DATE:
            self.generator = DateBetween(minimum, self._compared_to)
        elif self.type is AbstractBindings.TYPES.DATETIME:
            self.generator = DateTimeBetween(minimum, self._compared_to)
        elif self.type is AbstractBindings.TYPES.TIME:
            self.generator = TimeBetween(minimum, self._compared_to)
        else:
            raise ValueError(f"type({self.type}) is not supported")

    def __str__(self):
        return f"E: LessThan {self.target_op}:{self.target_param} = {self._compared_to}"

    def __repr__(self):
        return f"E: LessThan {self.target_op}:{self.target_param} = {self._compared_to}"
