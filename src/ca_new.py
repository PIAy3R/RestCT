import time
from collections import defaultdict
from typing import List, Tuple

from loguru import logger

from src.config import Config
from src.executor import RestRequest
from src.factor import Value, ValueType, AbstractFactor
from src.generator import ACTS
from src.info import RuntimeInfoManager
from src.keywords import DataType
from src.keywords import Method
from src.languagemodel.llm import ResponseModel
from src.nlp import Processor, Constraint
from src.rest import RestOp, RestParam, PathParam, QueryParam, BodyParam, HeaderParam


class CA:
    def __init__(self, config: Config, **kwargs):

        # response chain
        self._maxChainItems = 3
        # idCount: delete created resource
        self._id_counter: List[(int, str)] = list()
        self._config = config

        self._a_strength = config.a_strength  # cover strength for all parameters
        self._e_strength = config.e_strength  # cover strength for essential parameters

        self._manager = RuntimeInfoManager(config)
        self._executor = RestRequest(config.query, config.header, self._manager)

        self._data_path = config.data_path
        self.start_time = None

        self._acts = ACTS(self._data_path, config.jar)

        self._stat = kwargs.get("stat")

    def _select_response_chains(self, response_chains):
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
        self._stat.seq_executed_num += 1
        self._stat.sum_len_of_executed_seq += len(sequence)
        self._stat.update_executed_c_way(sequence)
        self._manager.save_response_to_file()
        return True

    def _handle_one_operation(self, index, operation: RestOp, chain: dict, sequence, loop_num) -> bool:
        success_url_tuple = tuple([op for op in sequence[:index] if op in chain.keys()] + [operation])
        if len(operation.parameters) == 0:
            logger.debug("operation has no parameter, execute and return")
            self._execute(operation, [{}], chain, success_url_tuple, [])
            return True

        history = []
        self._reset_constraints(operation, operation.parameters)

        (have_success_e, have_bug_e, e_response_list), e_ca = self._handle_params(operation, sequence[:index],
                                                                          success_url_tuple, chain, history, index,
                                                                          True)
        # e_ca = self._handle_essential_params(operation, sequence[:index], success_url_tuple, chain, history)
        # logger.info(f"{index + 1}-th operation essential parameters covering array size: {len(e_ca)}, "
        #             f"parameters: {len(e_ca[0]) if len(e_ca) > 0 else 0}, constraints: {len(operation.constraints)}")
        # have_success_e, have_bug_e, e_response_list = self._execute(operation, e_ca, chain, success_url_tuple, history,
        #                                                             True)
        is_break_e = have_success_e or have_bug_e

        # a_ca = self._handle_all_params(operation, sequence[:index], success_url_tuple, chain, history)
        # logger.info(f"{index + 1}-th operation essential parameters covering array size: {len(a_ca)}, "
        #             f"parameters: {len(a_ca[0]) if len(a_ca) > 0 else 0}, constraints: {len(operation.constraints)}")
        # have_success_a, have_bug_a, a_response_list = self._execute(operation, a_ca, chain, success_url_tuple, history,
        #                                                             False)
        (have_success_a, have_bug_a, a_response_list), a_ca = self._handle_params(operation, sequence[:index],
                                                                          success_url_tuple, chain, history, index,
                                                                          False)
        is_break_a = have_success_a or have_bug_a
        self._manager.save_response(operation, e_response_list + a_response_list, e_ca + a_ca)

        return is_break_e or is_break_a

    @staticmethod
    def set_param_value(op: RestOp, case, is_reuse=False):
        for p in op.parameters:
            p.factor.set_value(case, is_reuse)

    def process(self, op: RestOp, case, chain, is_reuse=False):
        self.set_param_value(op, case, is_reuse)
        url = op.resolved_url(chain)
        method = op.verb
        query_param = {p.factor.name: p.factor.printable_value() for p in op.parameters
                       if isinstance(p, QueryParam) and p.factor.value is not None}
        header_param = {p.factor.name: p.factor.printable_value() for p in op.parameters
                        if isinstance(p, HeaderParam) and p.factor.value is not None}
        body_param = next(filter(lambda p: isinstance(p, BodyParam), op.parameters), None)
        body = body_param.factor.printable_value() if body_param is not None else None
        kwargs = dict()
        if body is not None:
            kwargs["Content-Type"] = body_param.content_type
        status_code, response_data = self._executor.send(
            method,
            url,
            header_param,
            query=query_param,
            body=body,
            **kwargs
        )
        return status_code, response_data

    def _execute(self, op: RestOp, ca, chain, url_tuple, history, is_reuse=False, is_essential=True):
        self._stat.op_executed_num.add(op)
        history.clear()

        has_success = False
        has_bug = False

        if len(ca) == 0:
            raise Exception("the size of ca can not be zero")

        response_list: List[(int, object)] = []

        for case in ca:
            self._stat.dump_snapshot()
            status_code, response_data = self.process(op, case, chain, is_reuse)
            if status_code < 300:
                has_success = True
                history.append(case)
            elif status_code == 500:
                has_bug = True
            response_list.append((status_code, response_data))
        logger.debug(f"Status codes: {[sc for (sc, res) in response_list]}")
        self._handle_response(url_tuple, op, response_list, chain, ca, is_essential)
        return has_success, has_bug, response_list

    @staticmethod
    def _reset_constraints(op: RestOp, parameters: List[RestParam]):
        constraint_processor = Processor(parameters)
        constraints: List[Constraint] = constraint_processor.parse()
        op.set_constraints(constraints)

    # def _handle_essential_params(self, operation: RestOp, executed: List[RestOp], success_url_tuple, chain, history):
    #     # reused_case = self._manager.get_reused_with_essential_p(tuple(exec_ops + [operation]))
    #     # if len(reused_case) > 0:
    #     #     # 执行过
    #     #     logger.debug("use reuse_seq info: {}, parameters: {}", len(reused_case), len(reused_case[0].keys()))
    #     #     return reused_case
    #     logger.debug("handle essential parameters")
    #     parameter_list = list(filter(lambda p: p.factor.is_essential, operation.parameters))
    #     if len(parameter_list) == 0:
    #         cover_array = [{}]
    #     else:
    #         cover_array = self._cover_params(operation, parameter_list, [], chain, self._e_strength, history)
    #     return cover_array
    #
    # def _handle_all_params(self, operation: RestOp, executed: List[RestOp], success_url_tuple, chain, history):
    #     logger.debug("handle all parameters")
    #     parameter_list = operation.parameters
    #     cover_array = self._cover_params(operation, parameter_list, [], chain, self._a_strength, history)
    #     return cover_array

    def _handle_params(self, operation: RestOp, executed: List[RestOp], success_url_tuple, chain, history, index,
                       is_essential):
        if is_essential:
            logger.debug("handle essential parameters")
            parameter_list = list(filter(lambda p: p.factor.is_essential, operation.parameters))
        else:
            logger.debug("handle essential parameters")
            parameter_list = operation.parameters
        if len(parameter_list) == 0:
            cover_array = [{}]
            return self._execute(operation, cover_array, chain, success_url_tuple, history, False, True), [{}]
        else:
            is_reuse = False
            if is_essential:
                reused_case = self._manager.get_reused_with_essential_p(tuple(executed + [operation]))
                if len(reused_case) > 0:
                    # 执行过
                    logger.debug("        use reuseSeq info: {}, parameters: {}", len(reused_case),
                                 len(reused_case[0].keys()))
                    is_reuse = True
                    cover_array = reused_case
                else:
                    cover_array = self._cover_params(operation, parameter_list, operation.constraints, chain,
                                                     self._e_strength, history)
                    logger.info(
                        f"{index + 1}-th operation essential parameters covering array size: {len(cover_array)}, "
                        f"parameters: {len(cover_array[0]) if len(cover_array) > 0 else 0}, constraints: {len(operation.constraints)}")
                return self._execute(operation, cover_array, chain, success_url_tuple, history, is_reuse,
                                     True), cover_array
            else:
                reused_case = self._manager.get_reused_with_all_p(tuple(executed + [operation]))
                if len(reused_case) > 0:
                    # 执行过
                    logger.debug("        use reuseSeq info: {}, parameters: {}", len(reused_case),
                                 len(reused_case[0].keys()))
                    is_reuse = True
                    cover_array = reused_case
                else:
                    cover_array = self._cover_params(operation, parameter_list, operation.constraints, chain,
                                                     self._a_strength, history)
                    logger.info(f"{index + 1}-th operation all parameters covering array size: {len(cover_array)}, "
                                f"parameters: {len(cover_array[0]) if len(cover_array) > 0 else 0}, constraints: {len(operation.constraints)}")
                return self._execute(operation, cover_array, chain, success_url_tuple, history, is_reuse,
                                     False), cover_array

    def _cover_params(self, operation: RestOp,
                      parameters: List[RestParam],
                      constraints,
                      chain,
                      strength,
                      history_ca_of_current_op: List[dict]):

        if history_ca_of_current_op is None:
            history_ca_of_current_op = []
        domain_map = defaultdict(list)
        for root_p in parameters:
            if isinstance(root_p, PathParam):
                root_p.factor.gen_path(operation, chain)
            else:
                root_p.factor.gen_domain()
            if not self._manager.is_unresolved((operation, root_p.factor.get_global_name)):
                domain_map = root_p.factor.add_domain_to_map(domain_map)

        if history_ca_of_current_op is not None and len(history_ca_of_current_op) > 0:
            new_domain_map = {
                "history_ca_of_current_op": [Value(v, ValueType.Reused, DataType.Int32) for v in
                                             range(len(history_ca_of_current_op))]}

            for p in domain_map.keys():
                if p not in history_ca_of_current_op[0].keys():
                    new_domain_map[p] = domain_map.get(p)
                else:
                    for i in range(len(history_ca_of_current_op)):
                        history_ca_of_current_op[i][p] = AbstractFactor.mutate_value(history_ca_of_current_op[i].get(p))

            for c in operation.constraints:
                for p in c.paramNames:
                    if self._manager.is_unresolved(p):
                        return [{}]

            domain_map = new_domain_map

        for p, v in domain_map.items():
            logger.debug(f"            {p}: {len(v)} - {v}")

        return self._call_acts(domain_map, constraints, strength, history_ca_of_current_op)

    def _call_acts(self, domain_map, constraints, strength, history_ca_of_current_op):
        try:
            return self._acts.process(domain_map, constraints, strength, history_ca_of_current_op)
        except Exception:
            logger.warning("call acts wrong")

    def _handle_response(self, url_tuple, operation, response_list, chain, ca, is_essential):
        is_success = False
        for index, (sc, response) in enumerate(response_list):
            self._stat.req_num += 1
            self._stat.req_num_all += 1
            if sc < 300:
                self._manager.save_reuse(url_tuple, is_essential, ca[index])
                self._manager.save_ok_value(ca[index])
                self._manager.save_chain(chain, operation, response)
                is_success = True
                self._stat.req_20x_num += 1
                self._stat.op_success_num.add(operation)
                if operation.verb is Method.POST:
                    self._manager.save_id_count(operation, response, self._id_counter)
            elif sc in range(300, 400):
                self._stat.req_30x_num += 1
            elif sc in range(400, 500):
                self._stat.req_40x_num += 1
            elif sc in range(500, 600):
                # self._manager.save_bug(operation, ca[index], sc, response, chain, self._data_path, kwargs)
                is_success = True
                self._stat.req_50x_num += 1
                # self._stat.op_success_num.add(operation)
                # self._stat.bug.add(f"{operation.__repr__()}-{sc}-{response}")
            elif sc >= 600:
                self._stat.req_60x_num += 1
        if is_success:
            self._manager.save_success_seq(url_tuple)
            self._stat.update_success_c_way(url_tuple)


class CAWithLLM(CA):
    def __init__(self, config: Config, **kwargs):
        super().__init__(config, **kwargs)

        self._is_regenerate = False

    def _handle_one_operation(self, index, operation: RestOp, chain: dict, sequence, loop_num) -> bool:
        success_url_tuple = tuple([op for op in sequence[:index] if op in chain.keys()] + [operation])
        if len(operation.parameters) == 0:
            logger.debug("operation has no parameter, execute and return")
            self._execute(operation, [{}], chain, success_url_tuple, [])
            return True

        history = []
        self._reset_constraints(operation, operation.parameters)

        have_success_e, have_bug_e, e_response_list = self._handle_params(operation, sequence[:index],
                                                                          success_url_tuple, chain, history, index,
                                                                          True)
        is_break_e = have_success_e or have_bug_e

        have_success_a, have_bug_a, a_response_list = self._handle_params(operation, sequence[:index],
                                                                          success_url_tuple, chain, history, index,
                                                                          False)
        is_break_a = have_success_a or have_bug_a

        message = None
        if not operation.analysed:
            message, is_success_llm = self._analyse_constraint(operation, e_response_list + a_response_list)
            if is_success_llm:
                operation.set_analysed()

        if not (have_success_e and have_success_a and have_bug_e and have_bug_a):
            status_tuple = (have_success_e, have_success_a, have_bug_e, have_bug_a)
            logger.info("Expected status code(2xx or 500) missing, use llm to help re-generate")
            is_break = self._re_handle(index, operation, chain, sequence, loop_num, status_tuple, message)

        return is_break_e or is_break_a

    def _analyse_constraint(self, operation, response_list):
        sc_set = set([sc for (sc, r) in response_list])
        message = None
        is_success = False
        if all(200 <= sc < 300 for sc in sc_set):
            pass
        else:
            if not operation.analysed:
                if len(operation.get_leaf_factors()) <= 1:
                    logger.info(f"only {len(operation.get_leaf_factors())} parameter, skip constraint analysis")
                    operation.set_analysed()
                else:
                    message, is_success = self._call_response_language_model(operation, response_list)
        return message, is_success

    def _call_response_language_model(self, operation: RestOp, response_list: List[Tuple[int, object]]):
        if len(response_list) == 0:
            return
        response_model = ResponseModel(operation, self._manager, self._config, response_list=response_list)
        message, formatted_output, is_success = response_model.execute()
        return message, is_success

    def _re_handle(self, index, operation, chain, sequence: list, loop_num: int, status_tuple: tuple, message) -> bool:
        self._is_regen = True
        is_break = False
        if not (status_tuple[0] or status_tuple[1]):
            logger.info("no success request, use llm to help re-generate")
            success_url_tuple = tuple([op for op in sequence[:index] if op in chain.keys()] + [operation])
            if len(operation.parameterList) == 0:
                self._executes(operation, [{}], chain, success_url_tuple, [])
                return True

            history = []