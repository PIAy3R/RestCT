import csv
import json

from src.rest import RestOp


class OutputFixer:
    def __init__(self, manager):
        self._manager = manager

    def handle(self, output_to_process, parameter_list=None):
        pass


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

    def handle_cause(self, reason_dict):
        self._manager.save_language_model_cause(self._operation, reason_dict)

    def handle_group(self, group_dict, data_path):
        self._manager.save_language_model_group(self._operation, group_dict)
        self.save_group(data_path, group_dict)

    def handle_res(self, output_to_process, data_path):
        json_output = json.loads(output_to_process)
        try:
            param_list = json_output["Task1"]["params"]
            group_dict = json_output["Task2"]
        except:
            return None, False
        if group_dict is not None:
            self.handle_group(group_dict, data_path)
        return json_output, True
