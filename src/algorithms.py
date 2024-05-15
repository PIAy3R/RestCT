import sys
import time
from pathlib import Path

from loguru import logger

from src.ca_new import CA, CAWithLLM
from src.info import RuntimeInfoManager
from src.sequence import SCA
from src.statistics import Statistics
from src.swagger import SwaggerParser


class RestCT:
    def __init__(self, config):
        self._config = config
        self._logger = logger
        self._statistics = Statistics(config)

        self._update_log_config()

        swagger_parser = SwaggerParser(self._config)
        self._operations = swagger_parser.extract()
        self._statistics.op_num.update(self._operations)
        self._manager = RuntimeInfoManager(config)

        self._sca = SCA(self._config.s_strength, self._operations, self._statistics)

        if not config.use_llm:
            self._ca = CA(self._config, stat=self._statistics, manager=self._manager)
        else:
            self._ca = CAWithLLM(self._config, stat=self._statistics, manager=self._manager)

    def run(self):
        self._statistics.dump_snapshot()
        self._logger.info("operations: {}".format(len(self._operations)))
        self._ca.start_time = time.time()

        sequences = []
        while not self._sca.is_all_covered():
            sequences.append(self._sca.build_one_sequence())
            self._statistics.dump_snapshot()

        for index, sequence in enumerate(sorted(sequences, key=lambda s: len(s))):
            logger.info(f"handle sequence {index + 1}, sequence length: {len(sequence)}")
            flag = self._ca.handle(sequence)
            if not flag:
                break
        self._manager.save_constraint()
        self._statistics.write_report()

    def _update_log_config(self):
        loggerPath = Path(self._config.data_path) / "log/log_{time}.log"
        logger.remove(0)
        logger.add(loggerPath.as_posix(), rotation="100 MB",
                   format="<level>{level: <6}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")
        logger.add(sys.stderr,
                   format="<level>{level: <6}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")
