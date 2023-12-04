import abc
from typing import Dict, Any, Union, Optional

from src.factor.equivalence import AbstractEquivalence


class AbstractBindings(AbstractEquivalence, metaclass=abc.ABCMeta):
    def __init__(self, belong_to: str, target_op: str, target_param: str):
        self.op_id: str = belong_to
        self.target_op: str = target_op
        self.target_param: str = target_param

        self._compared_to: Optional[Any] = None
        self.generator: Optional[AbstractEquivalence] = None

    def update(self, inputs: Dict[str, Any] = None, responses: Dict[str, Union[list, dict]] = None) -> None:
        """
        @param inputs: see all leaves of input parameters
        @param responses: list as received
        """
        if inputs is not None:
            if self.target_param not in inputs.keys():
                raise ValueError(f"target_param({self.target_param}) does not exist")
            self._compared_to = inputs.get(self.target_param)
        elif responses is not None:
            self._update_with_response(responses)

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


class EqualTo(AbstractBindings):
    def __init__(self, belong_to: str, target_op: str, target_param: str):
        super().__init__(belong_to, target_op, target_param)

    def check(self, value) -> bool:
        if self._compared_to is None:
            raise ValueError("Value is not set")
        return value == self._compared_to

    def generate(self) -> Any:
        if self._compared_to is None:
            self.update()
        return self._compared_to

    def __str__(self):
        return f"E: EqualTo {self.target_op}:{self.target_param} = {self._compared_to}"

    def __repr__(self):
        return f"E: EqualTo {self.target_op}:{self.target_param} = {self._compared_to}"


class GreaterThan(AbstractBindings):
    def __init__(self, belong_to: str, target_op: str, target_param: str):
        super().__init__(belong_to, target_op, target_param)

    def check(self, value) -> bool:
        if self._compared_to is None:
            raise ValueError("Value is not set")
        return value > self._compared_to

    def generate(self) -> Any:
        pass

    def __str__(self):
        return f"E: GreaterThan {self.target_op}:{self.target_param} = {self._compared_to}"

    def __repr__(self):
        return f"E: GreaterThan {self.target_op}:{self.target_param} = {self._compared_to}"


class LessThan(AbstractBindings):
    def __init__(self, belong_to: str, target_op: str, target_param: str):
        super().__init__(belong_to, target_op, target_param)

    def check(self, value) -> bool:
        if self._compared_to is None:
            raise ValueError("Value is not set")
        return value < self._compared_to

    def generate(self) -> Any:
        pass

    def __str__(self):
        return f"E: LessThan {self.target_op}:{self.target_param} = {self._compared_to}"

    def __repr__(self):
        return f"E: LessThan {self.target_op}:{self.target_param} = {self._compared_to}"
