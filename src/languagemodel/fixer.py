import csv
import json

from src.rest import RestOp


class OutputFixer:
    def __init__(self, manager):
        self._manager = manager


class ResponseFixer(OutputFixer):
    def __init__(self, manager, operation: RestOp):
        super().__init__(manager)

        self._operation = operation

    def save_group(self, data_path, output_json):
        group_path = data_path / "grouped_constraint.csv"
        with group_path.open("w") as fp:
            writer = csv.writer(fp, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            writer.writerow(["operation", "constraint_param_pair"])
            for constraint, parameters in output_json.items():
                writer.writerow([self._operation, parameters])

    def save_params(self, param_list):
        self._manager.save_param(self._operation, param_list)

    def handle_group(self, group_dict, data_path):
        self._manager.save_language_model_group(self._operation, group_dict)
        self.save_group(data_path, group_dict)

    def handle_res(self, output_to_process, data_path):
        json_output = json.loads(output_to_process)
        param_list = json_output["params"]
        if len(param_list) > 0:
            self._manager.save_constraint_params(self._operation, param_list)
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
        v = list(json_output.values())[0]
        self._manager.save_idl(self._operation, v)
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
