import json
from loguru import logger
import re


class OutputProcessor:
    def __init__(self, task: str, output_to_process: str, param_list: list, opera_info):
        self._task = task
        self._output_to_process = output_to_process
        self._param_list = param_list
        self._param_info: list = opera_info["parameters"]

    def main(self):
        def parseResponse(string_to_process):
            try:
                output_json: dict = json.loads(string_to_process)
            except json.JSONDecodeError:
                logger.info("Language model returns an object that is not in JSON format")
                if re.search("```", string_to_process):
                    logger.info("The response contains json object, try to get it out")
                    output_json: dict = json.loads(string_to_process.split("```")[-1])
                    return output_json
                else:
                    raise Exception("Expecting strings enclosed in double quotes")
            return output_json

        output_json = parseResponse(self._output_to_process)
        if self._task == "body":
            if output_json.get("body") is not None:
                output_json = output_json["body"]
            else:
                pass
        if self._task == "value":
            for param_dict in self._param_info:
                param_name = param_dict.get("name")
                if param_name in output_json:
                    example_value = param_dict.get("example")
                    if isinstance(output_json[param_name], list):
                        if example_value is not None and example_value in output_json[param_name]:
                            output_json[param_name].remove(example_value)
                    elif isinstance(output_json[param_name], str or int or float or bool):
                        if example_value is not None and example_value != output_json[param_name]:
                            output_json[param_name] = list(output_json[param_name])
                    elif isinstance(output_json[param_name], dict):
                        for k, v in output_json[param_name].items():
                            if isinstance(v, list):
                                output_json[param_name] = v
                                break
                        if example_value is not None and example_value in output_json[param_name]:
                            output_json[param_name].remove(example_value)
        if self._task == "combination":
            pass
        return output_json