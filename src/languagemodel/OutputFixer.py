import csv
import json
import re
from typing import Dict, List

from loguru import logger

from src.Dto.operation import Operation


class OutputFixer:
    def __init__(self, manager):
        self._manager = manager

    @staticmethod
    def decode_to_json(output_to_process):
        try:
            output_json: dict = json.loads(output_to_process)
        except json.JSONDecodeError:
            logger.warning("Language model returns an object that is not in JSON format")
            if re.search("```", output_to_process):
                try:
                    logger.info("The response contains json object")
                    output_json: dict = json.loads(output_to_process.split("```")[-1])
                    return output_json
                except:
                    logger.info("No json object find")
                    return {}
            else:
                logger.error("Expecting strings enclosed in double quotes")
                return {}
        return output_json

    def handle(self, output_to_process, parameter_list=None):
        pass


class ValueOutputFixer(OutputFixer):
    def __init__(self, manager, operation: Operation):
        super().__init__(manager)

        self._operation = operation

    def handle(self, output_to_process, parameter_list=None) -> dict:
        json_output = self.decode_to_json(output_to_process)
        processed_output = self.del_existing_example(json_output, parameter_list)
        self._manager.save_language_model_value_response(self._operation, processed_output)
        return processed_output

    @staticmethod
    def del_existing_example(json_output, parameter_list):
        processed_output: Dict[str, List] = {}
        for p, vl in json_output.items():
            example = ""
            for p_d in parameter_list:
                if p_d.get("name") == p:
                    example = p_d.get("example", None)
                    break
            for v in vl:
                if example != "" and example is not None and v == example:
                    continue
                if isinstance(v, str):
                    v = v.replace('|', ',')
                    v = v.replace(";", ",")
                if processed_output.get(p, None) is None:
                    processed_output.update({p: [v]})
                else:
                    processed_output[p].append(v)
        return processed_output


class CodeGenerationFixer(OutputFixer):
    def __init__(self, manager, operation: Operation):
        super().__init__(manager)

        self._operation = operation

    def handle(self, output_to_process, parameter_list=None):
        pass


class ResponseFixer(OutputFixer):
    def __init__(self, manager, operation: Operation):
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
        # param_list = json_output.get("Task1").get("params")
        reason_dict = json_output.get("Task2")
        group_dict = json_output.get("Task3")
        self.handle_group(group_dict, data_path)
        self.handle_cause(reason_dict)
        return json_output
