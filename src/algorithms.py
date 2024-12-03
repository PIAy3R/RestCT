import sys
import time
from loguru import logger
from pathlib import Path

from src.ca import CA, CAWithLLM
from src.info import RuntimeInfoManager
from src.sequence import Sequence
from src.swagger import SwaggerParser


class Initialize:
    def __init__(self, config):
        self._config = config
        self._logger = logger

        self._update_log_config()

        swagger_parser = SwaggerParser(self._config)
        self._operations = swagger_parser.extract()

        self._manager = RuntimeInfoManager(config)

    def _update_log_config(self):
        loggerPath = Path(self._config.data_path) / "log/log_{time}.log"
        logger.remove(0)
        logger.add(loggerPath.as_posix(), rotation="100 MB",
                   format="<level>{level: <6}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")
        logger.add(sys.stderr,
                   format="<level>{level: <6}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")


class RestCT(Initialize):
    def __init__(self, config):
        super().__init__(config)

        # self._sca = SCA(self._config.s_strength, self._operations, self._statistics)
        self._sca = Sequence(self._operations, self._config, self._manager)

        if not config.use_llm:
            self._ca = CA(self._config, manager=self._manager, operations=self._operations)
        else:
            self._ca = CAWithLLM(self._config, manager=self._manager, operations=self._operations)

    def run(self):
        # self._statistics.dump_snapshot()
        self._logger.info("operations: {}".format(len(self._operations)))
        self._ca.start_time = time.time()

        # round 1: cover all operations
        sequence = self._sca.build_sequence()
        # while not self._sca.is_all_covered():
        #     sequences.append(self._sca.build_one_sequence())
        #     self._statistics.dump_snapshot()

        logger.info(f"round 1: cover all operations, sequence length: {len(sequence)}")
        flag = self._ca.handle(sequence)
        if not flag:
            return

        # round 2: try to find bugs
        logger.info(f"round 2: try to find bugs")

        # # round 2: retry the failed operations
        # failed_operations = list(sequence - self._manager.get_success_responses().keys())
        # logger.info(f"round 2: retry the failed operations, failed operations: {len(failed_operations)}")
        # logger.info(f"Use llm to retry the failed operations")
        # flag = self._ca.handle(failed_operations)
        # if not flag:
        #     return

        # round 3: find unexpected errors
        # success_operations = self._manager.get_success_responses().keys()
        # sequences = self._sca.build_error_sequence(success_operations)
        # logger.info(f"round 3: find unexpected errors, sequence length: {len(sequence)}")
        # for index, sequence in enumerate(sequences):
        #     logger.info(f"sequence {index + 1}: {sequence}")
        #     flag = self._ca.handle(sequence)
        #     if not flag:
        #         return

        self._manager.save_constraint()
        self._manager.save_value_to_file()
        self._manager.save_case_response_to_file()
        # self._statistics.write_report()

# class LLM(Initialize):
#     def __init__(self, config):
#         super().__init__(config)
#
#         self._seq = Sequence(self._config.s_strength, self._operations)
#
#         self._ca = CAWithLLM(self._config, manager=self._manager, operations=self._operations)
#
#     def run(self):
#         self._logger.info("operations: {}".format(len(self._operations)))
#         self._ca.start_time = time.time()
#
#         # step 1: cover all operations
#         logger.info("step 1: cover all operations")
#         sequence = self._seq.build_sequence(self._operations)
#         assert len(sequence) == len(self._operations)
#         logger.info(f"sequence length: {len(sequence)}")
#         self._ca.handle(sequence)
#
#         # step 2: retry the failed operations
#
#         # step 3: trigger bugs
