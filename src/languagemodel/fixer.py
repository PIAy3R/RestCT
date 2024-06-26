import json
from typing import List

from src.rest import RestOp


class OutputFixer:
    def __init__(self, manager):
        self._manager = manager


class ResponseFixer(OutputFixer):
    def __init__(self, manager, operation: RestOp):
        super().__init__(manager)

        self._operation = operation

    def handle_res(self, output_to_process):
        json_output = json.loads(output_to_process)
        param_list = json_output["params"]
        if len(param_list) > 0:
            self._manager.save_problem_param(self._operation, param_list)
        return param_list, True


class ValueFixer(OutputFixer):
    def __init__(self, manager, operation: RestOp, parameter_list=None):
        super().__init__(manager)

        self._operation = operation
        self._parameter_list = parameter_list

    def handle(self, output_to_process, parameter_list):
        json_output = json.loads(output_to_process)
        for p in parameter_list:
            if p.get_global_name in json_output:
                p.set_llm_example(json_output[p.get_global_name])
        return json_output, True


class IDLFixer(OutputFixer):
    def __init__(self, manager, operation: RestOp, parameter_list=None):
        super().__init__(manager)

        self._operation = operation
        self._parameter_list = parameter_list

    def handle(self, output_to_process):
        json_output = json.loads(output_to_process)
        c_str_list = list(json_output.values())[0]
        if len(c_str_list) > 0:
            self._manager.save_idl(self._operation, c_str_list)
            self._manager.save_constraint_params(self._operation, c_str_list)
        return json_output, True


class PICTFixer(OutputFixer):
    def __init__(self, manager, operation: RestOp, parameter_list=None):
        super().__init__(manager)

        self._operation = operation
        self._parameter_list = parameter_list

    def handle(self, output_to_process):
        json_output = json.loads(output_to_process)
        v = list(json_output.values())[0]
        self._manager.save_pict(self._operation, v)
        return json_output, True


class SequenceFixer(OutputFixer):
    def __init__(self, manager, operations: List[RestOp]):
        super().__init__(manager)

        self._operations = operations

    def handle(self, output_to_process):
        op_sequence = []
        json_output = json.loads(output_to_process)
        sequence = json_output["sequence"]
        for op_str in sequence:
            for op in self._operations:
                if op.__repr__() == op_str:
                    op_sequence.append(op)
                    break
        return op_sequence, True


class PathFixer(OutputFixer):
    def __init__(self, manager, operation: RestOp, operations, parameter_list=None):
        super().__init__(manager)

        self._operation = operation
        self._operations = operations
        self._parameter_list = parameter_list

    def handle_param(self, output_to_process):
        try:
            json_output = json.loads(output_to_process)
            self._manager.bind_param(self._operation, json_output, self._parameter_list, self._operations)
            return json_output, True
        except:
            return None, False

    def handle_operation(self, response):
        json_output = json.loads(response)
        self._manager.save_path_binding(self._operation, json_output, self._parameter_list, self._operations)


class ErrorValueFixer(OutputFixer):
    def __init__(self, manager, operation: RestOp, parameter_list=None):
        super().__init__(manager)

        self._operation = operation
        self._parameter_list = parameter_list

    def handle(self, output_to_process):
        pass
