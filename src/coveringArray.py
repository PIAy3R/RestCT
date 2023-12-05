from typing import List, Union, Optional

from src.rest import RestOp


class CaseContext:
    """
    maintain the context of a whole test case,
    including a series of http requests
    """

    def __init__(self):
        # historical responses of executed http requests in the case
        self._historical_responses: List[Union[dict, list, str]] = list()

        # current http request
        self._op: Optional[RestOp] = None
        self._response: Optional[Union[dict, list, str]] = None

    def _update_param_domain(self):
        """
        update the domain of the parameters in the current request
        """
        for param in self._op.parameters:
            param(self._historical_responses)

    def update(self, inputs: Dict[str, Any] = None, responses: Dict[str, Union[list, dict]] = None) -> None:
        """
        @param inputs: see all leaves of input parameters
        @param responses: list as received
        """
        if inputs is not None:
            if self.target_param not in inputs.keys():
                raise ValueError(f"target_param({self.target_param}) does not exist")
            self._compared_to = inputs.get(self.target_param)
        if responses is not None:
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
