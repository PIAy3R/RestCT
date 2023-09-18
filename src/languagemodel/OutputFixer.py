import abc
import json
from loguru import logger
import re

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

    def handle(self, output_to_process):
        pass


class ValueOutputFixer(OutputFixer):
    def __init__(self, manager, operation: Operation):
        super().__init__(manager)

        self._operation = operation

    def handle(self, output_to_process) -> dict:
        json_output = self.decode_to_json(output_to_process)
        self._manager.save_language_model_response(self._operation, json_output)
        return json_output
