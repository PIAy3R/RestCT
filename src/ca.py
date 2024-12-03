from collections import defaultdict

import time
from loguru import logger
from typing import List, Tuple

from src.config import Config
from src.executor import RestRequest
from src.factor import Value, ValueType, StringFactor, EnumFactor, BooleanFactor
from src.generator import ACTS, PICT
from src.keywords import DataType
from src.keywords import Method
from src.languagemodel.llm import ResponseModel, ValueModel, IDLModel, PICTModel, PathModel, ErrorValueModel
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

        self._manager = kwargs.get("manager")
        self._executor = RestRequest(config.query, config.header, self._manager)

        self._data_path = config.data_path
        self.start_time = None

        self._acts = ACTS(self._data_path, config.jar)
        self._pict = PICT(self._data_path, config.pict)

        # self._stat = kwargs.get("stat")
        self._operations = kwargs.get("operations")

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
        # self._stat.seq_executed_num += 1
        # self._stat.sum_len_of_executed_seq += len(sequence)
        # self._stat.update_executed_c_way(sequence)
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
                                                                                  success_url_tuple, chain, history,
                                                                                  index,
                                                                                  True)

        is_break_e = have_success_e or have_bug_e

        (have_success_a, have_bug_a, a_response_list), a_ca = self._handle_params(operation, sequence[:index],
                                                                                  success_url_tuple, chain, history,
                                                                                  index,
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
        # self._stat.op_executed_num.add(op)
        history.clear()

        has_success = False
        has_bug = False

        if len(ca) == 0:
            raise Exception("the size of ca can not be zero")

        response_list: List[(int, object)] = []

        for case in ca:
            # self._stat.dump_snapshot()
            status_code, response_data = self.process(op, case, chain, is_reuse)
            if status_code < 300:
                has_success = True
                history.append(case)
            elif status_code == 500:
                has_bug = True
            response_list.append((status_code, response_data))

            # save case
            value_case = dict()
            for factor in op.get_leaf_factors():
                if factor.get_global_name in case:
                    value_case[factor.get_global_name] = factor.printable_value()
            self._manager.save_case_response(op, value_case, response_data, status_code)

        logger.debug(f"Status codes: {[sc for (sc, res) in response_list]}")
        self._handle_response(url_tuple, op, response_list, chain, ca, is_essential)
        return has_success, has_bug, response_list

    @staticmethod
    def _reset_constraints(op: RestOp, parameters: List[RestParam]):
        param_list = op.get_leaf_factors()
        constraint_processor = Processor(param_list)
        constraints: List[Constraint] = constraint_processor.parse()
        op.set_constraints(constraints)

    def _handle_params(self, operation: RestOp, executed: List[RestOp], success_url_tuple, chain, history, index,
                       is_essential, verify=False):
        if is_essential:
            logger.debug("handle essential parameters")
            parameter_list = list(filter(lambda p: p.factor.is_essential, operation.parameters))
            for p in operation.parameters:
                add = False
                if isinstance(p, BodyParam):
                    for f in p.factor.get_leaves():
                        if f.is_essential:
                            add = True
                            break
                if add:
                    parameter_list.append(p)
        else:
            logger.debug("handle all parameters")
            parameter_list = operation.parameters
        if len(parameter_list) == 0:
            cover_array = [{}]
            return self._execute(operation, cover_array, chain, success_url_tuple, history, False, True), [{}]
        else:
            is_reuse = False
            if is_essential:
                reused_case = self._manager.get_reused_with_essential_p(tuple(executed + [operation]))
                if len(reused_case) > 0 and not verify:
                    # 执行过
                    logger.debug("        use reuseSeq info: {}, parameters: {}", len(reused_case),
                                 len(reused_case[0].keys()))
                    is_reuse = True
                    cover_array = reused_case
                else:
                    cover_array = self._cover_params(operation, parameter_list, chain, self._e_strength, history,
                                                     is_essential)
                    logger.info(
                        f"{index + 1}-th operation essential parameters covering array size: {len(cover_array)}, "
                        f"parameters: {len(cover_array[0]) if len(cover_array) > 0 else 0}, "
                        f"constraints: {len(operation.constraints) if not operation.is_re_handle else len(operation.llm_constraints)}")
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
                    cover_array = self._cover_params(operation, parameter_list, chain, self._a_strength, history,
                                                     is_essential)
                    logger.info(
                        f"{index + 1}-th operation all parameters covering array size: {len(cover_array)}, "
                        f"parameters: {len(cover_array[0]) if len(cover_array) > 0 else 0}, "
                        f"constraints: {len(operation.constraints) if not operation.is_re_handle else len(operation.llm_constraints)}")
                return self._execute(operation, cover_array, chain, success_url_tuple, history, is_reuse,
                                     False), cover_array

    def _cover_params(self, operation: RestOp,
                      parameters: List[RestParam],
                      chain,
                      strength,
                      history_ca_of_current_op: List[dict],
                      is_essential):
        if history_ca_of_current_op is None:
            history_ca_of_current_op = []
        domain_map = defaultdict(list)
        for root_p in parameters:
            if isinstance(root_p, PathParam):
                root_p.factor.gen_path(operation, chain, self._manager)
                if not self._manager.is_unresolved((operation, root_p.factor.get_global_name)):
                    domain_map = root_p.factor.add_domain_to_map(domain_map)
            else:
                if is_essential:
                    for f in root_p.factor.get_leaves():
                        if f.is_essential:
                            f.gen_domain()
                            if not self._manager.is_unresolved((operation, f.get_global_name)):
                                domain_map = f.add_domain_to_map(domain_map)
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
                # else:
                #     for i in range(len(history_ca_of_current_op)):
                #         history_ca_of_current_op[i][p] = AbstractFactor.mutate_value(history_ca_of_current_op[i].get(p))

            for c in operation.constraints:
                for p in c.paramNames:
                    if self._manager.is_unresolved(p):
                        return [{}]

            domain_map = new_domain_map

        for p, v in domain_map.items():
            logger.debug(f"            {p}: {len(v)} - {v}")

        return self._call_pict(domain_map, operation, strength, history_ca_of_current_op)
        # return self._call_acts(operation, domain_map, constraints, strength, history_ca_of_current_op)

    def _call_acts(self, operation, domain_map, constraints, strength, history_ca_of_current_op):
        try:
            return self._acts.process(operation, domain_map, constraints, strength, history_ca_of_current_op)
        except Exception:
            logger.warning("call acts wrong")

    def _call_pict(self, domain_map, operation, strength, history_ca_of_current_op):
        try:
            return self._pict.process(domain_map, operation, strength, history_ca_of_current_op, self._manager)
        except Exception:
            logger.warning("call pict wrong")

    def _handle_response(self, url_tuple, operation, response_list, chain, ca, is_essential):
        is_success = False
        for index, (sc, response) in enumerate(response_list):
            # self._stat.req_num += 1
            # self._stat.req_num_all += 1
            if sc < 300:
                self._manager.save_reuse(url_tuple, is_essential, ca[index])
                self._manager.save_ok_value(ca[index])
                self._manager.save_chain(chain, operation, response)
                self._manager.save_success_response(operation, response)
                is_success = True
                # self._stat.req_20x_num += 1
                # self._stat.op_success_num.add(operation)
                if operation.verb is Method.POST:
                    self._manager.save_id_count(operation, response, self._id_counter)
            # elif sc in range(300, 400):
            # self._stat.req_30x_num += 1
            # elif sc in range(400, 500):
            # self._stat.req_40x_num += 1
            elif sc in range(500, 600):
                # self._manager.save_bug(operation, ca[index], sc, response, chain, self._data_path, kwargs)
                is_success = True
                # self._stat.req_50x_num += 1
                # self._stat.op_success_num.add(operation)
                # self._stat.bug.add(f"{operation.__repr__()}-{sc}-{response}")
            # elif sc >= 600:
            #     self._stat.req_60x_num += 1
        if is_success:
            self._manager.save_success_seq(url_tuple)
            # self._stat.update_success_c_way(url_tuple)


# class CAWithLLM(CA):
#     def __init__(self, config: Config, **kwargs):
#         super().__init__(config, **kwargs)
#
#         self._is_regenerate = False
#
#     def _handle_one_operation(self, index, operation: RestOp, chain: dict, sequence, loop_num) -> bool:
#         self._is_regenerate = False
#         success_url_tuple = tuple([op for op in sequence[:index] if op in chain.keys()] + [operation])
#         operation.is_re_handle = False
#         if len(operation.parameters) == 0:
#             logger.debug("operation has no parameter, execute and return")
#             self._execute(operation, [{}], chain, success_url_tuple, [])
#             return True
#
#         history = []
#         self._reset_constraints(operation, operation.parameters)
#
#         if loop_num == 1:
#             self._call_binding_model(operation, chain, self._operations)
#
#         (have_success_e, have_bug_e, e_response_list), e_ca = self._handle_params(operation, sequence[:index],
#                                                                                   success_url_tuple, chain, history,
#                                                                                   index,
#                                                                                   True)
#         is_break_e = have_success_e or have_bug_e
#
#         (have_success_a, have_bug_a, a_response_list), a_ca = self._handle_params(operation, sequence[:index],
#                                                                                   success_url_tuple, chain, history,
#                                                                                   index,
#                                                                                   False)
#         self._manager.save_response(operation, e_response_list + a_response_list, e_ca + a_ca)
#         is_break_a = have_success_a or have_bug_a
#
#         message = None
#         have_constraint = False
#         if not operation.analysed:
#             message, is_success_response = self._analyse_response(operation, e_response_list + a_response_list)
#             if is_success_response:
#                 operation.set_analyzed()
#             is_success_constraint, have_constraint = self._call_constraint_model(operation)
#
#         if not (have_success_e and have_success_a and have_bug_e and have_bug_a):
#             status_tuple = (have_success_e, have_success_a, have_bug_e, have_bug_a)
#             is_break = self._re_handle(index, operation, chain, sequence, loop_num, status_tuple, message,
#                                        have_constraint)
#             return is_break
#
#         return is_break_e or is_break_a
#
#     def _analyse_response(self, operation, response_list):
#         sc_set = set([sc for (sc, r) in response_list])
#         message = None
#         is_success = False
#         if all(200 <= sc < 300 for sc in sc_set):
#             pass
#         else:
#             if not operation.analysed:
#                 if len(operation.get_leaf_factors()) <= 1:
#                     logger.info(f"only {len(operation.get_leaf_factors())} parameter, skip constraint analysis")
#                     operation.set_analyzed()
#                 else:
#                     message, is_success = self._call_response_language_model(operation, response_list)
#         return message, is_success
#
#     def _re_handle(self, index, operation, chain, sequence: list, loop_num: int, status_tuple: tuple, message,
#                    have_constraint) -> bool:
#         operation.is_re_handle = True
#         self._is_regenerate = True
#         verify = (status_tuple[0] or status_tuple[1]) and have_constraint
#
#         # succeed to generate the request
#         if (not (status_tuple[0] or status_tuple[1])) or verify:
#             if not (status_tuple[0] or status_tuple[1]):
#                 logger.info("no success request, use llm to help re-generate")
#             elif verify:
#                 logger.info("have success request, but need to validate the constraints")
#
#             success_url_tuple = tuple([op for op in sequence[:index] if op in chain.keys()] + [operation])
#             if len(operation.parameters) == 0:
#                 self._execute(operation, [{}], chain, success_url_tuple, [])
#                 return True
#
#             history = []
#             # self._reset_constraints(operation, operation.parameters)
#             self.set_llm_constraints(operation)
#
#             if not (status_tuple[0] or status_tuple[1]):
#                 llm_examples = []
#                 for f in operation.get_leaf_factors():
#                     llm_examples += f.llm_examples
#                 if len(llm_examples) == 0:
#                     if not self._call_value_language_model(operation):
#                         logger.info("no param to ask")
#                         return False
#
#             try:
#                 (have_success_e, have_bug_e, e_response_list), e_ca = self._handle_params(operation, sequence[:index],
#                                                                                           success_url_tuple, chain,
#                                                                                           history,
#                                                                                           index, True, verify)
#                 is_break_e = have_success_e or have_bug_e
#
#                 (have_success_a, have_bug_a, a_response_list), a_ca = self._handle_params(operation, sequence[:index],
#                                                                                           success_url_tuple, chain,
#                                                                                           history,
#                                                                                           index, False, verify)
#                 is_break_a = have_success_a or have_bug_a
#             except:
#                 logger.exception("constraint failed")
#                 self._manager.clear_llm_result(operation)
#                 self._reset_constraints(operation, operation.parameters)
#                 (have_success_e, have_bug_e, e_response_list), e_ca = self._handle_params(operation, sequence[:index],
#                                                                                           success_url_tuple, chain,
#                                                                                           history,
#                                                                                           index, True, verify)
#                 is_break_e = have_success_e or have_bug_e
#
#                 (have_success_a, have_bug_a, a_response_list), a_ca = self._handle_params(operation, sequence[:index],
#                                                                                           success_url_tuple, chain,
#                                                                                           history,
#                                                                                           index, False, verify)
#                 is_break_a = have_success_a or have_bug_a
#
#             self._manager.save_response(operation, e_response_list + a_response_list, e_ca + a_ca)
#             self._manager.save_example_value(operation, e_response_list + a_response_list, e_ca + a_ca)
#
#             is_break = is_break_e or is_break_a
#
#             if loop_num == 3:
#                 if not is_break:
#                     logger.info(f"loop 3 times for {operation}, no success request, clear the LLM results")
#                     is_break = True
#                     if len(self._manager.get_constraint_params(operation)) > 0:
#                         operation.set_unanalyzed()
#                     self._manager.clear_llm_result(operation)
#                 if not is_break_e:
#                     for f in operation.get_leaf_factors():
#                         if f.is_essential:
#                             f.clear_llm_example()
#                 if not is_break_a:
#                     for f in operation.get_leaf_factors():
#                         f.clear_llm_example()
#                 return is_break
#
#         # trigger bugs
#         if not (status_tuple[2] or status_tuple[3]):
#             return True
#         #     logger.info("no 500 status code, use llm to help re-generate")
#         #
#         #     success_url_tuple = tuple([op for op in sequence[:index] if op in chain.keys()] + [operation])
#         #     if len(operation.parameters) == 0:
#         #         self._execute(operation, [{}], chain, success_url_tuple, [])
#         #         return True
#         #
#         #     history = []
#         #     self._reset_constraints(operation, operation.parameters)
#         #
#         #     self._call_error_model(operation)
#         #
#         #     (have_success_e, have_bug_e, e_response_list), e_ca = self._handle_params(operation, sequence[:index],
#         #                                                                               success_url_tuple, chain, history,
#         #                                                                               index, True, verify)
#         #     is_break_e = have_success_e or have_bug_e
#         #
#         #     (have_success_a, have_bug_a, a_response_list), a_ca = self._handle_params(operation, sequence[:index],
#         #                                                                               success_url_tuple, chain, history,
#         #                                                                               index, False, verify)
#         #     is_break_a = have_success_a or have_bug_a
#
#     def _call_response_language_model(self, operation: RestOp, response_list: List[Tuple[int, object]]):
#         if len(response_list) == 0:
#             return
#         response_model = ResponseModel(operation, self._manager, self._config, response_list=response_list)
#         message, formatted_output, is_success = response_model.execute()
#         return message, is_success
#
#     def _call_value_language_model(self, operation: RestOp):
#         param_to_ask = []
#         # problem_params = self._manager.get_constraint_params(operation)
#         for p in operation.parameters:
#             if isinstance(p, PathParam):
#                 if isinstance(p.factor, StringFactor):
#                     param_to_ask.append(p.factor)
#             if isinstance(p, QueryParam) or isinstance(p, BodyParam):
#                 for l in p.factor.get_leaves():
#                     if not isinstance(l, EnumFactor) and not isinstance(l, BooleanFactor):
#                         param_to_ask.append(l)
#                     # if l.is_essential:
#                     #     if not isinstance(l, EnumFactor) and not isinstance(l, BooleanFactor):
#                     #         param_to_ask.append(l)
#                     # elif l in problem_params:
#                     #     param_to_ask.append(l)
#             else:
#                 pass
#         if len(param_to_ask) == 0:
#             return False
#         else:
#             value_model = ValueModel(operation, self._manager, self._config, param_to_ask)
#             messages, formatted_output, is_success = value_model.execute()
#             return is_success
#
#     def _call_constraint_model(self, operation: RestOp):
#         param_to_ask = self._manager.get_problem_params(operation)
#         if len(param_to_ask) <= 1:
#             return [], False
#         idl_model = IDLModel(operation, self._manager, self._config, param_to_ask)
#         idl_message, idl_output, idl_is_success = idl_model.execute()
#         if len(idl_output['constraints']) > 0:
#             pict_param_to_ask = self._manager.get_constraint_params(operation)
#             pict_model = PICTModel(operation, self._manager, self._config, pict_param_to_ask)
#             pict_message, pict_output, pict_is_success = pict_model.execute()
#         else:
#             pict_is_success = True
#         return idl_is_success and pict_is_success, len(idl_output['constraints']) > 0
#
#     def set_llm_constraints(self, operation: RestOp):
#         for f in self._manager.get_constraint_params(operation):
#             f.is_constraint = True
#         operation.llm_constraints = self._manager.get_pict(operation)
#
#     def _call_binding_model(self, operation: RestOp, chain, all_operations: List[RestOp]):
#         param_to_ask = []
#         for p in operation.parameters:
#             if isinstance(p, PathParam):
#                 param_to_ask.append(p.factor)
#         if len(param_to_ask) == 0:
#             return
#         else:
#             path_model = PathModel(operation, self._manager, self._config, param_to_ask, all_operations)
#             messages, formatted_output, is_success = path_model.execute()
#             return is_success
#
#     def _call_error_model(self, operation: RestOp):
#         error_model = ErrorValueModel(operation, self._manager, self._config)
#         messages, formatted_output, is_success = error_model.execute()
#         return is_success

class CAWithLLM(CA):
    def __init__(self, config: Config, **kwargs):
        super().__init__(config, **kwargs)

        self._is_regenerate = False

    def _handle_for_pass(self, index, operation: RestOp, chain: dict, sequence, loop_num) -> bool:
        logger.info(f"handle {index + 1}-th operation: {operation}, use essential parameters for pass")
        self._is_regenerate = False
        success_url_tuple = tuple([op for op in sequence[:index] if op in chain.keys()] + [operation])
        operation.is_re_handle = False
        if len(operation.parameters) == 0:
            logger.debug("operation has no parameter, execute and return")
            self._execute(operation, [{}], chain, success_url_tuple, [])
            return True

        history = []
        self._reset_constraints(operation, operation.parameters)

        if loop_num == 1:
            self._call_binding_model(operation, chain, self._operations)

        (have_success_e, have_bug_e, e_response_list), e_ca = self._handle_params(operation, sequence[:index],
                                                                                  success_url_tuple, chain, history,
                                                                                  index,
                                                                                  True)
        is_break_e = have_success_e or have_bug_e

        message = None
        have_constraint = False
        if not operation.analysed:
            message, is_success_response = self._analyse_response(operation, e_response_list)
            if is_success_response:
                operation.set_analyzed()
            is_success_constraint, have_constraint = self._call_constraint_model(operation)

        if not (have_success_e and have_bug_e):
            status_tuple = (have_success_e, False, have_bug_e, False)
            is_break = self._re_handle(index, operation, chain, sequence, loop_num, status_tuple, message,
                                       have_constraint)
            return is_break

        return is_break_e

    def _handle_one_operation(self, index, operation: RestOp, chain: dict, sequence, loop_num) -> bool:
        self._is_regenerate = False
        success_url_tuple = tuple([op for op in sequence[:index] if op in chain.keys()] + [operation])
        operation.is_re_handle = False
        if len(operation.parameters) == 0:
            logger.debug("operation has no parameter, execute and return")
            self._execute(operation, [{}], chain, success_url_tuple, [])
            return True

        history = []
        self._reset_constraints(operation, operation.parameters)

        if loop_num == 1:
            self._call_binding_model(operation, chain, self._operations)

        (have_success_e, have_bug_e, e_response_list), e_ca = self._handle_params(operation, sequence[:index],
                                                                                  success_url_tuple, chain, history,
                                                                                  index,
                                                                                  True)
        is_break_e = have_success_e or have_bug_e

        (have_success_a, have_bug_a, a_response_list), a_ca = self._handle_params(operation, sequence[:index],
                                                                                  success_url_tuple, chain, history,
                                                                                  index,
                                                                                  False)
        self._manager.save_response(operation, e_response_list + a_response_list, e_ca + a_ca)
        is_break_a = have_success_a or have_bug_a

        message = None
        have_constraint = False
        if not operation.analysed:
            message, is_success_response = self._analyse_response(operation, e_response_list + a_response_list)
            if is_success_response:
                operation.set_analyzed()
            is_success_constraint, have_constraint = self._call_constraint_model(operation)

        if not (have_success_e and have_success_a and have_bug_e and have_bug_a):
            status_tuple = (have_success_e, have_success_a, have_bug_e, have_bug_a)
            is_break = self._re_handle(index, operation, chain, sequence, loop_num, status_tuple, message,
                                       have_constraint)
            return is_break

        return is_break_e or is_break_a

    def _analyse_response(self, operation, response_list):
        sc_set = set([sc for (sc, r) in response_list])
        message = None
        is_success = False
        if all(200 <= sc < 300 for sc in sc_set):
            pass
        else:
            if not operation.analysed:
                if len(operation.get_leaf_factors()) <= 1:
                    logger.info(f"only {len(operation.get_leaf_factors())} parameter, skip constraint analysis")
                    operation.set_analyzed()
                else:
                    message, is_success = self._call_response_language_model(operation, response_list)
        return message, is_success

    def _re_handle(self, index, operation, chain, sequence: list, loop_num: int, status_tuple: tuple, message,
                   have_constraint) -> bool:
        operation.is_re_handle = True
        self._is_regenerate = True
        verify = (status_tuple[0] or status_tuple[1]) and have_constraint

        # succeed to generate the request
        if (not (status_tuple[0] or status_tuple[1])) or verify:
            if not (status_tuple[0] or status_tuple[1]):
                logger.info("no success request, use llm to help re-generate")
            elif verify:
                logger.info("have success request, but need to validate the constraints")

            success_url_tuple = tuple([op for op in sequence[:index] if op in chain.keys()] + [operation])
            if len(operation.parameters) == 0:
                self._execute(operation, [{}], chain, success_url_tuple, [])
                return True

            history = []
            # self._reset_constraints(operation, operation.parameters)
            self.set_llm_constraints(operation)

            if not (status_tuple[0] or status_tuple[1]):
                llm_examples = []
                for f in operation.get_leaf_factors():
                    llm_examples += f.llm_examples
                if len(llm_examples) == 0:
                    if not self._call_value_language_model(operation):
                        logger.info("no param to ask")
                        return False

            try:
                (have_success_e, have_bug_e, e_response_list), e_ca = self._handle_params(operation, sequence[:index],
                                                                                          success_url_tuple, chain,
                                                                                          history,
                                                                                          index, True, verify)
                is_break_e = have_success_e or have_bug_e

                (have_success_a, have_bug_a, a_response_list), a_ca = self._handle_params(operation, sequence[:index],
                                                                                          success_url_tuple, chain,
                                                                                          history,
                                                                                          index, False, verify)
                is_break_a = have_success_a or have_bug_a
            except:
                logger.exception("constraint failed")
                self._manager.clear_llm_result(operation)
                self._reset_constraints(operation, operation.parameters)
                (have_success_e, have_bug_e, e_response_list), e_ca = self._handle_params(operation, sequence[:index],
                                                                                          success_url_tuple, chain,
                                                                                          history,
                                                                                          index, True, verify)
                is_break_e = have_success_e or have_bug_e

                (have_success_a, have_bug_a, a_response_list), a_ca = self._handle_params(operation, sequence[:index],
                                                                                          success_url_tuple, chain,
                                                                                          history,
                                                                                          index, False, verify)
                is_break_a = have_success_a or have_bug_a

            self._manager.save_response(operation, e_response_list + a_response_list, e_ca + a_ca)
            self._manager.save_example_value(operation, e_response_list + a_response_list, e_ca + a_ca)

            is_break = is_break_e or is_break_a

            if loop_num == 3:
                if not is_break:
                    logger.info(f"loop 3 times for {operation}, no success request, clear the LLM results")
                    is_break = True
                    if len(self._manager.get_constraint_params(operation)) > 0:
                        operation.set_unanalyzed()
                    self._manager.clear_llm_result(operation)
                if not is_break_e:
                    for f in operation.get_leaf_factors():
                        if f.is_essential:
                            f.clear_llm_example()
                if not is_break_a:
                    for f in operation.get_leaf_factors():
                        f.clear_llm_example()
                return is_break

        # trigger bugs
        if not (status_tuple[2] or status_tuple[3]):
            return True
        #     logger.info("no 500 status code, use llm to help re-generate")
        #
        #     success_url_tuple = tuple([op for op in sequence[:index] if op in chain.keys()] + [operation])
        #     if len(operation.parameters) == 0:
        #         self._execute(operation, [{}], chain, success_url_tuple, [])
        #         return True
        #
        #     history = []
        #     self._reset_constraints(operation, operation.parameters)
        #
        #     self._call_error_model(operation)
        #
        #     (have_success_e, have_bug_e, e_response_list), e_ca = self._handle_params(operation, sequence[:index],
        #                                                                               success_url_tuple, chain, history,
        #                                                                               index, True, verify)
        #     is_break_e = have_success_e or have_bug_e
        #
        #     (have_success_a, have_bug_a, a_response_list), a_ca = self._handle_params(operation, sequence[:index],
        #                                                                               success_url_tuple, chain, history,
        #                                                                               index, False, verify)
        #     is_break_a = have_success_a or have_bug_a

    def _call_response_language_model(self, operation: RestOp, response_list: List[Tuple[int, object]]):
        if len(response_list) == 0:
            return
        response_model = ResponseModel(operation, self._manager, self._config, response_list=response_list)
        message, formatted_output, is_success = response_model.execute()
        return message, is_success

    def _call_value_language_model(self, operation: RestOp):
        param_to_ask = []
        # problem_params = self._manager.get_constraint_params(operation)
        for p in operation.parameters:
            if isinstance(p, PathParam):
                if isinstance(p.factor, StringFactor):
                    param_to_ask.append(p.factor)
            if isinstance(p, QueryParam) or isinstance(p, BodyParam):
                for l in p.factor.get_leaves():
                    if not isinstance(l, EnumFactor) and not isinstance(l, BooleanFactor):
                        param_to_ask.append(l)
                    # if l.is_essential:
                    #     if not isinstance(l, EnumFactor) and not isinstance(l, BooleanFactor):
                    #         param_to_ask.append(l)
                    # elif l in problem_params:
                    #     param_to_ask.append(l)
            else:
                pass
        if len(param_to_ask) == 0:
            return False
        else:
            value_model = ValueModel(operation, self._manager, self._config, param_to_ask)
            messages, formatted_output, is_success = value_model.execute()
            return is_success

    def _call_constraint_model(self, operation: RestOp):
        param_to_ask = self._manager.get_problem_params(operation)
        if len(param_to_ask) <= 1:
            return [], False
        idl_model = IDLModel(operation, self._manager, self._config, param_to_ask)
        idl_message, idl_output, idl_is_success = idl_model.execute()
        if len(idl_output['constraints']) > 0:
            pict_param_to_ask = self._manager.get_constraint_params(operation)
            pict_model = PICTModel(operation, self._manager, self._config, pict_param_to_ask)
            pict_message, pict_output, pict_is_success = pict_model.execute()
        else:
            pict_is_success = True
        return idl_is_success and pict_is_success, len(idl_output['constraints']) > 0

    def set_llm_constraints(self, operation: RestOp):
        for f in self._manager.get_constraint_params(operation):
            f.is_constraint = True
        operation.llm_constraints = self._manager.get_pict(operation)

    def _call_binding_model(self, operation: RestOp, chain, all_operations: List[RestOp]):
        param_to_ask = []
        for p in operation.parameters:
            if isinstance(p, PathParam):
                param_to_ask.append(p.factor)
        if len(param_to_ask) == 0:
            return
        else:
            path_model = PathModel(operation, self._manager, self._config, param_to_ask, all_operations)
            messages, formatted_output, is_success = path_model.execute()
            return is_success

    def _call_error_model(self, operation: RestOp):
        error_model = ErrorValueModel(operation, self._manager, self._config)
        messages, formatted_output, is_success = error_model.execute()
        return is_success

