import abc
import copy
from abc import ABC
from typing import Tuple, Optional, Union, Any, List, Dict

from src.factor.equivalence import Enumerated, AbstractEquivalence, Null, AbstractBindings


class AbstractFactor(metaclass=abc.ABCMeta):
    """
    Abstract class for parameters
    """
    __slots__ = (
        "name", "_description", "required", "parent", "_examples", "_default", "domain", "index", "equivalences")

    def __init__(self, name: str):
        # Initialize the name and description of the factor
        self.name: str = name
        self._description: Optional[str] = None

        # Set the required flag to true
        self.required: bool = True
        self.parent: Optional[AbstractFactor] = None

        # specified values
        self._examples: list = []
        self._default: Optional[Any] = None

        self.domain: list = []
        self.index: int = -1
        self.equivalences: List[AbstractEquivalence] = []

    @property
    def description(self):
        return self._description

    @description.setter
    def description(self, text: str):
        # todo: format text with nlp
        if text is None or len(text) == 0:
            raise ValueError("Description cannot be empty")
        self._description = text

    def set_example(self, example):
        parsed_example = self._spilt_example(example)
        if parsed_example is not None:
            for e in parsed_example:
                if e not in self._examples:
                    self._examples.append(e)

    @abc.abstractmethod
    def init_equivalences(self):
        if not self.required:
            self.equivalences.append(Null())

    def _spilt_example(self, example) -> Union[list, None]:
        if example is None:
            return None
        if isinstance(example, list):
            return example
        if isinstance(example, dict):
            raise ValueError("Example cannot be a dict")
        return [example]

    def set_default(self, default_value):
        self._default = default_value

    def get_leaves(self) -> Tuple:
        """
        Get all leaves of the factor tree,
        excluding arrays and objects themselves.
        """
        return self,

    @property
    def global_name(self):
        if self.parent is not None:
            return f"{self.parent.global_name}.{self.name}"
        else:
            return self.name

    @property
    def is_active(self):
        """有确切的值"""
        if self.domain is None or len(self.domain) == 0 or self.index < 0:
            return False
        return True

    @property
    def is_initialized(self):
        """已经有equivalences了"""
        return len(self.equivalences) > 0

    @property
    def value(self):
        if self.is_active:
            return self.domain[self.index]
        else:
            raise ValueError(f"{self.global_name} has not been assigned yet")

    @property
    def printable_value(self):
        return self.value

    def update_equivalences(self, inputs: Dict[str, Any] = None, responses: Dict[str, Union[list, dict]] = None):
        for e in self.equivalences:
            if isinstance(e, AbstractBindings):
                e.update(inputs, responses)

    def generate_domain(self):
        """
        when all equivalences are ready
        generate the domain of the factor
        """
        self.domain.clear()
        for e in self.equivalences:
            self.domain.append(e.generate())

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.name == other.name

    def __str__(self):
        return self.global_name

    def __repr__(self):
        return self.global_name

    def __deepcopy__(self, memo):
        ins = self.__class__(name=self.name)
        ins._description = self._description
        ins.required = self.required
        ins.index = self.index

        ins.parent = copy.deepcopy(self.parent, memo)
        ins._examples = copy.deepcopy(self._examples, memo)
        ins._default = copy.deepcopy(self._default, memo)
        ins.domain = copy.deepcopy(self.domain, memo)
        ins.equivalences = copy.deepcopy(self.equivalences, memo)

        return ins


class ComparableFactor(AbstractFactor, ABC):
    def __init__(self, name: str):
        super().__init__(name)

    def __eq__(self, o: object) -> bool:
        if not isinstance(o, self.__class__):
            raise TypeError(f"{self.__class__} cannot be compared to {o.__class__}")
        if self.is_active and o.is_active:
            return self.value == o.value
        raise ValueError(f"{self.global_name}.value or {o.global_name}.value is None")

    def __ne__(self, o: object) -> bool:
        if not isinstance(o, self.__class__):
            raise TypeError(f"{self.__class__} cannot be compared to {o.__class__}")
        if self.is_active and o.is_active:
            return self.value != o.value
        raise ValueError(f"{self.global_name}.value or {o.global_name}.value is None")

    def __lt__(self, o: object) -> bool:
        if not isinstance(o, self.__class__):
            raise TypeError(f"{self.__class__} cannot be compared to {o.__class__}")
        if self.is_active and o.is_active:
            return self.value < o.value
        raise ValueError(f"{self.global_name}.value or {o.global_name}.value is None")

    def __le__(self, o: object) -> bool:
        if not isinstance(o, self.__class__):
            raise TypeError(f"{self.__class__} cannot be compared to {o.__class__}")

        if self.is_active and o.is_active:
            return self.value <= o.value
        raise ValueError(f"{self.global_name}.value or {o.global_name}.value is None")

    def __gt__(self, o: object) -> bool:
        if not isinstance(o, self.__class__):
            raise TypeError(f"{self.__class__} cannot be compared to {o.__class__}")

        if self.is_active and o.is_active:
            return self.value > o.value
        raise ValueError(f"{self.global_name}.value or {o.global_name}.value is None")

    def __ge__(self, o: object) -> bool:
        if not isinstance(o, self.__class__):
            raise TypeError(f"{self.__class__} cannot be compared to {o.__class__}")
        if self.is_active and o.is_active:
            return self.value >= o.value
        raise ValueError(f"{self.global_name}.value or {o.global_name}.value is None")


class EnumFactor(AbstractFactor):
    """
    EnumFactor is a factor that can only take one of a set of values.
    """

    def __init__(self, name: str, enum_value: list):
        super().__init__(name)
        self.domain = enum_value
        self.index = 0

    def init_equivalences(self):
        super().init_equivalences()

        if not self.is_active:
            raise ValueError(f"{self.global_name}.enums is empty")

        for v in self.domain:
            self.equivalences.append(Enumerated(v))

    def __deepcopy__(self, memo):
        ins = super().__deepcopy__(memo)
        ins.domain = copy.deepcopy(self.domain, memo)
        return ins


class BoolFactor(EnumFactor):
    def __init__(self, name: str):
        super(BoolFactor, self).__init__(name, [True, False])
