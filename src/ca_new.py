import time
from collections import defaultdict
from typing import List

from loguru import logger

from src.Dto.rest import RestOp, RestParam, PathParam
from src.config import Config
from src.executor import RestRequest
from src.info import RuntimeInfoManager


class CA:
    def __init__(self, config: Config, **kwargs):

        # response chain
        self._maxChainItems = 3
        # idCount: delete created resource
        self._id_counter: List[(int, str)] = list()
        self._config = config

        self._a_strength = config.a_strength  # cover strength for all parameters
        self._e_strength = config.e_strength  # cover strength for essential parameters

        self._manager = RuntimeInfoManager()
        # self._acts = ACTS(data_path, acts_jar)
        self._executor = RestRequest(config.header, config.query, self._manager)

        self._data_path = config.data_path
        self.start_time = None
        self._stat = kwargs.get("stat")

    def _select_response_chains(self, response_chains):
        """get _maxChainItems longest chains"""
        sorted_list = sorted(response_chains, key=lambda c: len(c.keys()), reverse=True)
        return sorted_list[:self._maxChainItems] if self._maxChainItems < len(sorted_list) else sorted_list

    def _timeout(self):
        return time.time() - self.start_time > self._config.budget

    def handle(self, sequence):
        for index, operation in enumerate(sequence):
            logger.debug(f"{index + 1}-th operation: {operation}")
            chain_list = self._manager.get_chains(self._maxChainItems)
            loop_num = 0
            while len(chain_list):
                loop_num += 1
                if self._timeout():
                    return False
                chain = chain_list.pop(0)
                is_break = self._handle_one_operation(index, operation, chain, sequence, loop_num)
                if is_break:
                    break
        return True

    def _handle_one_operation(self, index, operation: RestOp, chain: dict, sequence, loop_num) -> bool:
        success_url_tuple = tuple([op for op in sequence[:index] if op in chain.keys()] + [operation])
        if len(operation.parameters) == 0:
            logger.debug("operation has no parameter, execute and return")
            self._execute(operation)
            return True

        history = []
        # self._reset_constraints(operation, operation.parameters)
        self._handle_essential_params(operation, sequence[:index], success_url_tuple, chain, history)
        self._handle_all_params(operation, sequence[:index], success_url_tuple, chain, history)

    def _execute(self, op: RestOp):
        url = op.resolved_url
        verb = op.verb

    # def _reset_constraints(self, op: RestOp, parameters: List[RestParam]):
    #     constraint_processor = Processor(parameters)
    #     constraints: List[Constraint] = constraint_processor.parse()
    #     op.set_constraints(constraints)

    def _handle_essential_params(self, operation: RestOp, executed: List[RestOp], success_url_tuple, chain, history):
        # reused_case = self._manager.get_reused_with_essential_p(tuple(exec_ops + [operation]))
        # if len(reused_case) > 0:
        #     # 执行过
        #     logger.debug("use reuse_seq info: {}, parameters: {}", len(reused_case), len(reused_case[0].keys()))
        #     return reused_case

        parameter_list = list(filter(lambda p: p.factor.is_essential, operation.parameters))
        if len(parameter_list) == 0:
            cover_array = [{}]
        else:
            cover_array = self._cover_params(operation, parameter_list, [], chain, history)

    def _handle_all_params(self, operation: RestOp, executed: List[RestOp], success_url_tuple, chain, history):
        parameter_list = operation.parameters
        cover_array = self._cover_params(operation, parameter_list, [], chain, history)
        print("e")

    def _cover_params(self, operation: RestOp,
                      parameters: List[RestParam],
                      constraints,
                      chain,
                      history_ca_of_current_op: List[dict]):

        if history_ca_of_current_op is None:
            history_ca_of_current_op = []
        domain_map = defaultdict(list)
        for root_p in parameters:
            if isinstance(root_p, PathParam):
                root_p.factor.gen_path(operation, chain)
            else:
                root_p.factor.gen_domain()


class CAWithLLM(CA):
    def __init__(self, config: Config, **kwargs):
        super().__init__(config, **kwargs)
