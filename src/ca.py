import dataclasses
import json
import os
import random
import re
import shlex
import subprocess
import time
from collections import defaultdict
from pathlib import Path
from typing import List, Tuple, Dict, Union, Set, Any

import chardet
import requests
from loguru import logger

from src.Dto.constraint import Constraint, Processor
from src.Dto.keywords import Loc, DataType, Method
from src.Dto.operation import Operation
from src.Dto.parameter import AbstractParam, ValueType, Value, EnumParam, BoolParam
from src.languagemodel.LanguageModel import ParamValueModel, ResponseModel


def _saveChain(responseChains: List[dict], chain: dict, opStr: str, response):
    newChain = chain.copy()
    newChain[opStr] = response
    responseChains.append(newChain)
    if len(responseChains) > 10:
        responseChains.pop(0)


class ACTS:
    def __init__(self, dataPath, jar):
        self._workplace = Path(dataPath) / "acts"
        self.jar = jar
        if not self._workplace.exists():
            self._workplace.mkdir()

    @staticmethod
    def getId(paramName, paramNames):
        index = paramNames.index(paramName)
        return "P" + str(index)

    @staticmethod
    def getName(paramId: str, paramNames):
        index = int(paramId.lstrip("P"))
        return paramNames[index]

    def transformConstraint(self, domain_map, paramNames, constraint: Constraint):
        cStr = constraint.toActs(domain_map)
        if cStr is None:
            return ""
        for paramName in constraint.paramNames:
            pattern = r"\b" + paramName + r"\b"
            paramId = self.getId(paramName, paramNames)
            cStr = re.sub(re.compile(pattern), paramId, cStr)
        return eval(cStr)

    def writeInput(self, domain_map, paramNames, constraints, strength) -> Path:
        inputFile = self._workplace / "input.txt"
        with inputFile.open("w") as fp:
            fp.write(
                "\n".join(
                    ['[System]', '-- specify system name', 'Name: {}'.format("acts" + str(strength)), '',
                     '[Parameter]', '-- general syntax is parameter_name(type): value1, value2...\n'])
            )
            # write parameter ids
            for paramName, domain in domain_map.items():
                fp.write("{}(int):{}\n".format(self.getId(paramName, paramNames),
                                               ",".join([str(i) for i in range(len(domain))])))

            fp.write("\n")
            # write constraints
            if len(constraints) > 0:
                fp.write("[Constraint]\n")
                for c in constraints:
                    [fp.write(ts + "\n") for ts in self.transformConstraint(domain_map, paramNames, c)]

        return inputFile

    def callActs(self, strength: int, inputFile) -> Path:
        outputFile = self._workplace / "output.txt"
        jarPath = Path(self.jar)
        algorithm = "ipog"

        # acts 的文件路径不可以以"\"作为分割符，会被直接忽略，"\\"需要加上repr，使得"\\"仍然是"\\".
        command = r'java -Dalgo={0} -Ddoi={1} -Doutput=csv -jar {2} {3} {4}'.format(algorithm, str(strength),
                                                                                    str(jarPath),
                                                                                    str(inputFile),
                                                                                    str(outputFile))
        stdout, stderr = subprocess.Popen(shlex.split(command, posix=False), stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE).communicate()
        encoding = chardet.detect(stdout)["encoding"]
        stdout.decode(encoding)
        return outputFile

    def parseOutput(self, outputFile: Path, domain_map, paramNames, history_ca_of_current_op: List[dict]):
        with outputFile.open("r") as fp:
            lines = [line.strip("\n") for line in fp.readlines() if "#" not in line and len(line.strip("\n")) > 0]
        paramNames = [self.getName(paramId, paramNames) for paramId in lines[0].strip("\n").split(",")]
        coverArray: List[Dict[str, Value]] = list()
        for line in lines[1:]:
            valueDict = dict()
            valueIndexList = line.strip("\n").split(",")
            for i, valueIndex in enumerate(valueIndexList):
                valueDict[paramNames[i]] = domain_map[paramNames[i]][int(valueIndex)]
            if "history_ca_of_current_op" in valueDict.keys():
                history_index = valueDict.pop("history_ca_of_current_op")
                valueDict.update(history_ca_of_current_op[history_index.val])
            coverArray.append(valueDict)

        return coverArray

    def process(self, domain_map, constraints: List[Constraint], strength: int, history_ca_of_current_op: List[dict]):
        strength = min(strength, len(domain_map.keys()))
        paramNames = list(domain_map.keys())
        inputFile = self.writeInput(domain_map, paramNames, constraints, strength)
        outputFile = self.callActs(strength, inputFile)
        return self.parseOutput(outputFile, domain_map, paramNames, history_ca_of_current_op)


class Executor:
    def __init__(self, queryAuth, headerAuth, manager):
        self._auth = None if len(queryAuth) == 0 and len(headerAuth) == 0 else Auth(headerAuth, queryAuth)
        self._manager = manager

    def process(self, operation, ca_item, previous_responses) -> Tuple[int, object]:
        """
        Executor的任务只有发送请求，不处理CA相关的东西
        @param operation: the target operation
        @param ca_item: assignment
        @param previous_responses: the chain
        @return: status code and response info
        """
        self.setParamValue(operation, ca_item)
        kwargs = self.assemble(operation, previous_responses)
        return self.send(operation, **kwargs)

    @staticmethod
    def assemble(operation, responses) -> dict:
        url = operation.url
        headers = {
            'Content-Type': operation.header[0] if operation.header is not None else "application/json",
            'user-agent': 'my-app/0.0.1'
        }
        params = dict()
        files = dict()
        formData = dict()
        body = dict()

        for p in operation.parameterList:
            value = p.printableValue(responses)
            if value is None:
                if p.loc is Loc.Path:
                    url = url.replace("{" + p.name + "}", str("abc"))
                # assert p.loc is not Loc.Path, "{}:{}".format(p.name, p.loc.value)
            else:
                if p.type is DataType.File:
                    # todo: fixme: bug
                    files = value
                elif p.loc is Loc.Path:
                    assert p.name != "" and p.name is not None
                    url = url.replace("{" + p.name + "}", str(value))
                elif p.loc is Loc.Query:
                    params[p.name] = value
                elif p.loc is Loc.Header:
                    headers[p.name] = value
                elif p.loc is Loc.FormData:
                    if isinstance(value, dict):
                        formData.update(value)
                    else:
                        formData[p.name] = value
                elif p.loc is Loc.Body:
                    if isinstance(value, dict):
                        body.update(value)
                    else:
                        body[p.name] = value
                else:
                    raise Exception("unexpected Param Loc Type: {}".format(p.name))

        kwargs = dict()
        kwargs["url"] = url
        kwargs["headers"] = headers
        if len(params) > 0:
            kwargs["params"] = params
        if len(files) > 0:
            kwargs["files"] = files
        if len(formData) > 0:
            kwargs["data"] = formData
        if len(body) > 0:
            kwargs["data"] = json.dumps(body)
        return kwargs

    def get_kwargs(self, operation, ca_item, previous_responses):
        """
        Executor的任务只有发送请求，不处理CA相关的东西
        @param operation: the target operation
        @param ca_item: assignment
        @param previous_responses: the chain
        @return: status code and response info
        """
        self.setParamValue(operation, ca_item)
        kwargs = self.assemble(operation, previous_responses)
        return kwargs

    @staticmethod
    def setParamValue(operation, case):
        # parameters: List[AbstractParam] = self._operation.genDomain(dict(), dict())
        for p in operation.parameterList:
            p.value = p.getValueDto(case)

    def send(self, operation, **kwargs) -> Tuple[int, Union[str, dict, None]]:
        self._manager.register_request()

        # for k, v in kwargs.items():
        #     logger.debug("{}: {}", k, v)
        # todo:  more reasonable handling methods
        try:
            feedback = getattr(requests, operation.method.value.lower())(**kwargs, timeout=50,
                                                                         auth=self._auth)
        except TypeError:
            raise Exception("request type error: {}".format(operation.method.value.lower()))
        except ValueError:
            return 700, None
        except requests.exceptions.Timeout:
            return 700, "timeout"
        except requests.exceptions.TooManyRedirects:
            raise Exception("bad url, try a different one\n url: {}".format(kwargs.get("url")))
        except requests.exceptions.RequestException:
            feedback = None

        if feedback is None:
            # logger.debug("status code: {}", 600)
            return 600, None
        try:
            # logger.debug("status code: {}", feedback.status_code)
            # logger.debug(feedback.json())
            return feedback.status_code, feedback.json()
        except json.JSONDecodeError:
            return feedback.status_code, feedback.text


class Auth:
    def __init__(self, headerAuth, queryAuth):
        self.headerAuth = headerAuth
        self.queryAuth = queryAuth

    def __call__(self, r):
        for key, token in self.headerAuth.items():
            r.headers[key] = token
        for key, token in self.queryAuth.items():
            r.params[key] = token
        return r


class RuntimeInfoManager:
    def __init__(self):
        self._num_of_requests = 0
        self.llm_call = 0
        self.call_time = 0
        self.prompt_tokens = 0
        self.cost = 0

        self._ok_value_dict: Dict[str, List[Value]] = defaultdict(list)
        self._reused_essential_seq_dict: Dict[Tuple[Operation], List[Dict[str, Value]]] = defaultdict(list)
        self._reused_all_p_seq_dict: dict = defaultdict(list)
        self._response_chains: List[Dict[str, object]] = [dict()]
        self._bug_list: list = list()
        self._success_sequence: set = set()
        self._unresolved_params: Set[Tuple[Operation, str]] = set()
        self._postman_bug_info: list = list()

        self._llm_example_value_dict: Dict[Operation, Dict[AbstractParam, Union[dict, list]]] = dict()
        self._llm_cause_dict: Dict[Operation, Dict[AbstractParam, List[int]]] = dict()
        self._llm_constraint_group: Dict[Operation, List[List[AbstractParam]]] = dict()
        # self._llm_constraint_dict: Dict[Operation, List[AbstractParam]] = dict()
        # self._llm_ask_dict: Dict[Operation, List[AbstractParam]] = dict()

    def essential_executed(self, operations: Tuple[Operation]):
        return operations in self._reused_essential_seq_dict.keys()

    def all_executed(self, operations: Tuple[Operation]):
        return operations in self._reused_all_p_seq_dict.keys()

    def get_reused_with_essential_p(self, operations: Tuple[Operation]):
        reused_case = self._reused_essential_seq_dict.get(operations, list())
        if len(reused_case) > 0:
            return [{p: Value(v.val, ValueType.Reused, v.type) for p, v in case.items()} for case in reused_case]
        return []

    def get_reused_with_all_p(self, operations: Tuple[Operation]):
        reused_case = self._reused_all_p_seq_dict.get(operations, list())
        if len(reused_case) > 0:
            return [{p: Value(v.val, ValueType.Reused, v.type) for p, v in case.items()} for case in reused_case]
        return []

    def get_ok_value_dict(self):
        return self._ok_value_dict

    def get_llm_examples(self):
        return self._llm_example_value_dict

    def get_llm_constrainted_params(self, operation):
        params = set()
        for p in operation.parameterList:
            for constraint in self._llm_constraint_group.get(operation, []):
                if p in constraint:
                    params.add(p)
            # if p in self._llm_cause_dict.get(operation, {}):
            #     if 2 in self._llm_cause_dict.get(operation, {}).get(p):
            #         params.append(p)
        return list(params)

    def get_llm_ask_params(self, operation):
        params = []
        for p in operation.parameterList:
            if p in self.get_llm_constrainted_params(operation):
                params.append(p)
            else:
                if p in self._llm_cause_dict.get(operation, {}) and 1 in self._llm_cause_dict.get(operation, {}).get(p):
                    params.append(p)
        return params

    def get_llm_cause_params(self, operation):
        return self._llm_cause_dict.get(operation, {})

    def get_llm_grouped_constraint(self, operation):
        return self._llm_constraint_group.get(operation, [])

    def is_unresolved(self, p_name):
        return p_name in self._unresolved_params

    def register_request(self):
        self._num_of_requests += 1

    def update_llm_data(self, model_token_tuple: Tuple[str, int, int], call_time):
        """
        :param model_token_tuple: (model name, total_tokens, input_tokens counted by tiktoken)
        :call_time: the time of calling language model
        """
        self.llm_call += 1
        self.call_time += call_time
        self.prompt_tokens += model_token_tuple[1]
        self.cost += self._count_cost(model_token_tuple)

    def clear_llm(self):
        self.llm_call = 0
        self.call_time = 0
        self.prompt_tokens = 0
        self.cost = 0

    def _count_cost(self, model_token_tuple: Tuple[str, int, int]):
        model = model_token_tuple[0]
        total_tokens = model_token_tuple[1]
        input_tokens = model_token_tuple[2]
        out_tokens = total_tokens - input_tokens
        if model == "gpt-4-1106-preview":
            return input_tokens * 0.00001 + out_tokens * 0.00003
        if model == "gpt-4":
            return input_tokens * 0.00003 + out_tokens * 0.00006
        if model == "gpt-4-32k":
            return input_tokens * 0.00006 + out_tokens * 0.00012
        if model == "gpt-3.5-turbo-1106":
            return input_tokens * 0.000001 + out_tokens * 0.000002
        if model == "gpt-3.5-turbo-instruct":
            return input_tokens * 0.0000015 + out_tokens * 0.000002

    def save_reuse(self, url_tuple, is_essential, case):
        if is_essential:
            to_dict = self._reused_essential_seq_dict
        else:
            to_dict = self._reused_all_p_seq_dict
        if len(to_dict[url_tuple]) < 10:
            to_dict[url_tuple].append(case)

    def save_ok_value(self, case):
        for paramStr, value in case.items():
            if paramStr not in self._ok_value_dict.keys():
                self._ok_value_dict[paramStr].append(value)
            else:
                lst = self._ok_value_dict.get(paramStr)
                if len(lst) < 10 and value not in lst:
                    lst.append(value)

    def save_chain(self, chain, operation, response):
        new_chain = chain.copy()
        new_chain[operation] = response
        self._response_chains.append(new_chain)
        if len(self._response_chains) > 10:
            self._response_chains.pop(0)

    def save_id_count(self, operation, response, id_counter):
        if isinstance(response, dict):
            iid = response.get("id")
            try:
                id_counter.append((iid, operation.url))
            except TypeError:
                pass
        elif isinstance(response, list):
            for r in response:
                iid = r.get("id")
                try:
                    id_counter.append((int(iid), operation.url))
                except TypeError:
                    pass
        else:
            pass

    class EnumEncoder(json.JSONEncoder):
        PUBLIC_ENUMS = {
            'ValueType': ValueType,
            'DataType': DataType,
            'Method': Method,
            'Operation': Operation
        }

        def default(self, obj):
            if type(obj) in self.PUBLIC_ENUMS.values():
                return {"__enum__": str(obj)}
            return json.JSONEncoder.default(self, obj)

    def save_bug(self, operation, case, sc, response, chain, data_path, kwargs):
        self.add_postman_list(operation, kwargs)
        op_str_set = {d.get("method").name + d.get("url") + str(d.get("statusCode")) for d in self._bug_list}
        if operation.method.name + operation.url + str(sc) in op_str_set:
            return
        chain_save = [op.__repr__() for op in chain]
        bug_info = {
            "url": operation.url,
            "method": operation.method,
            "parameters": {paramName: dataclasses.asdict(value) for paramName, value in case.items()},
            "statusCode": sc,
            "response": response,
            "responseChain": chain_save
        }
        self._bug_list.append(bug_info)

        folder = Path(data_path) / "bug/"
        if not folder.exists():
            folder.mkdir(parents=True)
        bugFile = folder / "bug_{}.json".format(str(len(op_str_set)))
        with bugFile.open("w") as fp:
            json.dump(bug_info, fp, cls=RuntimeInfoManager.EnumEncoder)
        return bug_info

    # todo optimize the save_to_postman method
    def save_to_postman(self, data_path):
        folder = Path(data_path) / "bug/postman"
        if not folder.exists():
            folder.mkdir(parents=True)
        files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
        number_of_files = len(files)
        post_json = folder / "postman_collection_{}.json".format(str(number_of_files + 1))
        postman_request = {
            "collection": {
                "info": {
                    "name": "postman_bugs",
                    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
                },
                "item": self._postman_bug_info
            }
        }
        if len(self._postman_bug_info) > 0:
            with post_json.open("w") as fp:
                json.dump(postman_request, fp)
        self._postman_bug_info.clear()

    def add_postman_list(self, operation, kwargs):
        param_string = "&".join(
            [f"{k}={v}" for k, v in kwargs.get("params").items()] if kwargs.get("params") is not None else [])
        info = {
            "name": "Request{}".format(str(len(self._postman_bug_info) + 1)),
            "request": {
                "url": (kwargs["url"] + "?" + param_string) if param_string != "" else kwargs["url"],
                "method": operation.method.value.upper(),
                "header": [{"key": k, "value": v} for k, v in kwargs["headers"].items()],
                "body": {
                    "mode": "formdata" if "json" not in kwargs["headers"]["Content-Type"] else "raw"
                }
            }
        }
        if kwargs.get("data") is None:
            info["request"].pop("body")
        elif info["request"]["body"]["mode"] == "formdata":
            info["request"]["body"]["formdata"] = [{"key": k, "value": v} for k, v in kwargs["data"].items()]
        else:
            info["request"]["body"]["raw"] = json.dumps(kwargs["data"])
        self._postman_bug_info.append(info)

    def save_success_seq(self, url_tuple):
        self._success_sequence.add(url_tuple)

    def get_chains(self, maxChainItems):
        sortedList = sorted(self._response_chains, key=lambda c: len(c.keys()), reverse=True)
        return sortedList[:maxChainItems] if maxChainItems < len(sortedList) else sortedList

    def save_language_model_value_response(self, operation, json_output):
        if self._llm_example_value_dict.get(operation) is None:
            self._llm_example_value_dict[operation] = {}
        for k, v in json_output.items():
            for p in operation.parameterList:
                if p.getGlobalName() == k:
                    self._llm_example_value_dict[operation][k] = v

    # def save_language_model_constraint(self, operation, cause_dict: dict):
    #     if self._llm_constraint_dict.get(operation) is None:
    #         self._llm_constraint_dict[operation] = []
    #     for param, reason in cause_dict.items():
    #         if 2 in reason:
    #             for p in operation.parameterList:
    #                 if p.name == param:
    #                     self._llm_constraint_dict[operation].append(p)

    # def save_language_model_ask(self, operation, cause_dict: dict):
    #     if self._llm_ask_dict.get(operation) is None:
    #         self._llm_ask_dict[operation] = []
    #     for param, reason in cause_dict.items():
    #         if 1 in reason:
    #             for p in operation.parameterList:
    #                 if p.name == param:
    #                     self._llm_ask_dict[operation].append(p)

    def save_language_model_cause(self, operation, cause_dict: dict):
        if self._llm_cause_dict.get(operation) is None:
            self._llm_cause_dict[operation] = {}
        for p in operation.parameterList:
            if p.name in cause_dict.keys():
                self._llm_cause_dict[operation][p] = cause_dict[p.name]

    def save_language_model_group(self, operation, grouped: dict):
        if self._llm_constraint_group.get(operation) is None:
            self._llm_constraint_group[operation] = []
        for k, v in grouped.items():
            if len(v) == 1:
                continue
            new_v_list = []
            for p in operation.parameterList:
                if p.getGlobalName() in v:
                    new_v_list.append(p)
            self._llm_constraint_group[operation].append(new_v_list)


class CA:
    def __init__(self, data_path, acts_jar, a_strength, e_strength, **kwargs):

        # response chain
        self._maxChainItems = 3
        # idCount: delete created resource
        self._id_counter: List[(int, str)] = list()

        self._aStrength = a_strength  # cover strength for all parameters
        self._eStrength = e_strength  # cover strength for essential parameters

        self._manager = RuntimeInfoManager()
        self._acts = ACTS(data_path, acts_jar)
        self._executor = Executor(kwargs.get("query_auth"), kwargs.get("header_auth"), self._manager)

        self._data_path = data_path
        self._start_time = time.time()
        self._stat = kwargs.get("stat")

    def _select_response_chains(self, response_chains):
        """get _maxChainItems longest chains"""
        sortedList = sorted(response_chains, key=lambda c: len(c.keys()), reverse=True)
        return sortedList[:self._maxChainItems] if self._maxChainItems < len(sortedList) else sortedList

    def _executes(self, operation, ca, chain, url_tuple, history, is_essential=True) -> tuple[bool, bool, list[Any]]:
        self._stat.op_executed_num.add(operation)
        history.clear()

        has_success = False
        has_bug = False

        if len(ca) == 0:
            raise Exception("the size of ca can not be zero")

        response_list: List[(int, object)] = []
        for case in ca:
            self._stat.dump_snapshot()
            status_code, response = self._executor.process(operation, case, chain)
            response_list.append((status_code, response))

            if status_code < 300:
                has_success = True
                history.append(case)
            elif 500 <= status_code < 600:
                has_bug = True

        logger.info(f"status code list:{[sc for (sc, r) in response_list]}")

        self._handle_feedback(url_tuple, operation, response_list, chain, ca, is_essential)

        return has_success, has_bug, response_list

    def _handle_feedback(self, url_tuple, operation, response_list, chain, ca, is_essential):
        is_success = False
        for index, (sc, response) in enumerate(response_list):
            kwargs = self._executor.get_kwargs(operation, ca[index], chain)
            self._stat.req_num += 1
            self._stat.req_num_all += 1
            if sc < 300:
                self._manager.save_reuse(url_tuple, is_essential, ca[index])
                self._manager.save_ok_value(ca[index])
                self._manager.save_chain(chain, operation, response)
                is_success = True

                self._stat.req_20x_num += 1
                self._stat.op_success_num.add(operation)
                if operation.method is Method.POST:
                    self._manager.save_id_count(operation, response, self._id_counter)
            elif sc in range(300, 400):
                self._stat.req_30x_num += 1
            elif sc in range(400, 500):
                self._stat.req_40x_num += 1
            elif sc in range(500, 600):
                self._manager.save_bug(operation, ca[index], sc, response, chain, self._data_path, kwargs)
                is_success = True
                self._stat.req_50x_num += 1
                # self._stat.op_success_num.add(operation)
                self._stat.bug.add(f"{operation.__repr__()}-{sc}-{response}")
            elif sc >= 600:
                self._stat.req_60x_num += 1

        self._manager.save_to_postman(self._data_path)
        if is_success:
            self._manager.save_success_seq(url_tuple)
            self._stat.update_success_c_way(url_tuple)

        self._stat.dump_snapshot()

    def _handle_one_operation(self, index, operation: Operation, chain: dict, sequence, loop_num) -> bool:
        """
        @return: should jump out the loop of chain_list?
        """
        success_url_tuple = tuple([op for op in sequence[:index] if op in chain.keys()] + [operation])

        if len(operation.parameterList) == 0:
            logger.debug("operation has no parameter, execute and return")
            self._executes(operation, [{}], chain, success_url_tuple, [])
            return True

        history = []

        self._reset_constraints(operation, operation.parameterList)

        e_ca = self._handle_essential_params(operation, sequence[:index], chain, history)
        logger.info(f"{index + 1}-th operation essential parameters covering array size: {len(e_ca)}, "
                    f"parameters: {len(e_ca[0]) if len(e_ca) > 0 else 0}, constraints: {len(operation.constraints)}")

        have_success_e, have_bug_e, e_response_list = self._executes(operation, e_ca, chain, success_url_tuple, history,
                                                                     True)
        is_break_e = have_success_e or have_bug_e

        if all([p.isEssential for p in operation.parameterList]):
            return is_break_e

        a_ca = self._handle_all_params(operation, sequence[:index], chain, history)
        logger.info(f"{index + 1}-th operation all parameters covering array size: {len(a_ca)}, "
                    f"parameters: {len(a_ca[0]) if len(a_ca) > 0 else 0}, constraints: {len(operation.constraints)}")

        have_success_a, have_bug_a, a_response_list = self._executes(operation, a_ca, chain, success_url_tuple, history,
                                                                     False)
        is_break_a = have_success_a or have_bug_a

        return is_break_e or is_break_a

    def _handle_essential_params(self, operation, exec_ops, chain, history):
        """

        :param operation:
        :param exec_ops: sequence[:i]
        :param chain:
        :return:
        """
        reused_case = self._manager.get_reused_with_essential_p(tuple(exec_ops + [operation]))
        if len(reused_case) > 0:
            # 执行过
            logger.debug("        use reuseSeq info: {}, parameters: {}", len(reused_case), len(reused_case[0].keys()))
            return reused_case

        parameter_list = list(filter(lambda p: p.isEssential, operation.parameterList))
        if len(parameter_list) == 0:
            return [{}]

        return self._cover_params(operation, parameter_list, operation.constraints, chain, history)

    def _handle_all_params(self, operation, exec_ops, chain, history):
        reused_case = self._manager.get_reused_with_all_p(tuple(exec_ops + [operation]))
        if len(reused_case) > 0:
            # 执行过
            logger.debug("        use reuseSeq info: {}, parameters: {}", len(reused_case), len(reused_case[0].keys()))
            return reused_case

        parameter_list = operation.parameterList

        return self._cover_params(operation, parameter_list, operation.constraints, chain, history)

    def _cover_params(self, operation, parameters, constraints, chain, history_ca_of_current_op: List[dict]):
        """
        generate domain for each parameter of the current operation
        @param history_ca_of_current_op: ca_1 -> ca_2 -> ca_3, currently, essential_ca -> all_ca
        @param operation: the target operation
        @param parameters: parameter list
        @param constraints: the constraints among parameters
        @param chain: a response chain
        @return: the parameters and their domains
        """

        if history_ca_of_current_op is None:
            history_ca_of_current_op = []

        domain_map = defaultdict(list)
        for root_p in parameters:
            p_with_children = root_p.genDomain(operation.__repr__(), chain, self._manager.get_ok_value_dict())
            for p in p_with_children:
                if not self._manager.is_unresolved(operation.__repr__() + p.name):
                    domain_map[p.getGlobalName()] = p.domain

        if history_ca_of_current_op is not None and len(history_ca_of_current_op) > 0:
            new_domain_map = {
                "history_ca_of_current_op": [Value(v, ValueType.Reused, DataType.Int32) for v in
                                             range(len(history_ca_of_current_op))]}

            for p in domain_map.keys():
                if p not in history_ca_of_current_op[0].keys():
                    new_domain_map[p] = domain_map.get(p)

            for c in operation.constraints:
                for p in c.paramNames:
                    if self._manager.is_unresolved(p):
                        return [{}]

            domain_map = new_domain_map

        for p, v in domain_map.items():
            logger.debug(f"            {p}: {len(v)} - {v}")

        return self._call_acts(domain_map, constraints, self._eStrength, history_ca_of_current_op)

    def _call_acts(self, domain_map, constraints, strength, history_ca_of_current_op):
        try:
            return self._acts.process(domain_map, constraints, strength, history_ca_of_current_op)
        except Exception:
            logger.warning("call acts wrong")

    @staticmethod
    def _timeout(start_time, budget):
        return time.time() - start_time > budget

    @staticmethod
    def _reset_constraints(operation: Operation, parameters: List[AbstractParam]):
        constraint_processor = Processor(parameters)
        constraints: List[Constraint] = constraint_processor.parse()
        operation.set_constraints(constraints)

    def clear_up(self):
        for iid, url in self._id_counter:
            resource_id = url.rstrip("/") + "/" + str(iid)
            try:
                requests.delete(url=resource_id, auth=Auth())
            except Exception:
                continue

    def handle(self, sequence, budget):
        for index, operation in enumerate(sequence):
            logger.debug("{}-th operation: {}*{}", index + 1, operation.method.value, operation.url)
            chainList = self._manager.get_chains(self._maxChainItems)
            loop_num = 0
            while len(chainList):
                loop_num += 1
                if self._timeout(self._start_time, budget):
                    self._stat.seq_executed_num += 1
                    self._stat.sum_len_of_executed_seq += index
                    self._stat.update_executed_c_way(sequence[:index])
                    return False
                chain = chainList.pop(0)
                is_break = self._handle_one_operation(index, operation, chain, sequence, loop_num)
                if is_break:
                    break
        self._stat.seq_executed_num += 1
        self._stat.sum_len_of_executed_seq += len(sequence)
        self._stat.update_executed_c_way(sequence)
        self._stat.update_llm_data(self._manager.llm_call, self._manager.call_time, self._manager.prompt_tokens,
                                   self._manager.cost)
        self._manager.clear_llm()
        return True


class CAWithLLM(CA):
    def __init__(self, data_path, acts_jar, a_strength, e_strength, **kwargs):
        super().__init__(data_path, acts_jar, a_strength, e_strength, **kwargs)

        self._is_regen = False

    def _check_llm_response(self, operation, e_response_list, a_response_list, e_ca, a_ca):
        pass

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

            self._reset_constraints(operation, operation.parameterList)
            # self._add_llm_constraints(operation)

            if self._manager.get_llm_examples().get(operation) is None or len(
                    self._manager.get_llm_examples().get(operation)) == 0:
                flag = self._call_value_language_model(operation, message)
                if not flag:
                    logger.info("no param to ask")
                    return False

            e_ca = self._handle_essential_params(operation, sequence[:index], chain, history)
            logger.info(f"{index + 1}-th operation essential parameters covering array size: {len(e_ca)}, "
                        f"parameters: {len(e_ca[0]) if len(e_ca) > 0 else 0}, constraints: {len(operation.constraints)}")

            have_success_e, have_bug_e, e_response_list = self._executes(operation, e_ca, chain, success_url_tuple,
                                                                         history,
                                                                         True)
            is_break_e = have_success_e or have_bug_e

            if all([p.isEssential for p in operation.parameterList]):
                return is_break_e

            a_ca = self._handle_all_params(operation, sequence[:index], chain, history)
            logger.info(f"{index + 1}-th operation all parameters covering array size: {len(a_ca)}, "
                        f"parameters: {len(a_ca[0]) if len(a_ca) > 0 else 0}, constraints: {len(operation.constraints)}")

            have_success_a, have_bug_a, a_response_list = self._executes(operation, a_ca, chain, success_url_tuple,
                                                                         history,
                                                                         False)
            is_break_a = have_success_a or have_bug_a

            is_break = is_break_e or is_break_a

            # self._check_llm_response(operation, e_response_list, a_response_list, e_ca, a_ca)

            if loop_num == 3 and self._manager.get_llm_examples().get(operation) is not None and not is_break:
                logger.info(
                    "previous example values provided by LLM of this operation did not work, clear the value")
                self._manager.get_llm_examples().get(operation).clear()
                self._manager.get_llm_grouped_constraint(operation).clear()

        if not (status_tuple[2] or status_tuple[3]):
            pass
            # logger.info("no 500 status code, use llm to help re-generate")

        return is_break

    # def _add_llm_constraints(self, operation: Operation):
    #     llm_constraints = []
    #     constraint_param_list = self._manager.get_llm_constrainted_params(operation)

    def _call_response_language_model(self, operation: Operation, response_list: List[Tuple[int, object]]):
        if len(response_list) == 0:
            return
        response_model = ResponseModel(operation, self._manager, self._data_path, response_list)
        message, formatted_output = response_model.execute()
        return message

    def _call_value_language_model(self, operation: Operation, message):
        param_to_ask = []
        loc_set = set()
        for param in operation.parameterList:
            if (param.isEssential and not isinstance(param, EnumParam)
                    and not isinstance(param, BoolParam) and param.loc != Loc.Path):
                param_to_ask.append(param)
                loc_set.add(param.loc)
            elif not param.isEssential:
                if (param in self._manager.get_llm_ask_params(operation)
                        and not isinstance(param, EnumParam) and not isinstance(param, BoolParam)):
                    param_to_ask.append(param)
                    loc_set.add(param.loc)
        if len(param_to_ask) != 0:
            value_model = ParamValueModel(operation, param_to_ask, self._manager, self._data_path)
            value_model.execute(message)
        else:
            return False
        return True

    def _re_count(self, e_ca, a_ca):
        self._stat.req_num -= (len(e_ca) + len(a_ca))
        self._stat.req_40x_num -= (len(e_ca) + len(a_ca))

    def _handle_one_operation(self, index, operation: Operation, chain: dict, sequence, loop_num) -> bool:
        self._is_regen = False
        success_url_tuple = tuple([op for op in sequence[:index] if op in chain.keys()] + [operation])

        if len(operation.parameterList) == 0:
            logger.debug("operation has no parameter, execute and return")
            self._executes(operation, [{}], chain, success_url_tuple, [])
            return True

        history = []

        self._reset_constraints(operation, operation.parameterList)

        e_ca = self._handle_essential_params(operation, sequence[:index], chain, history)
        logger.info(f"{index + 1}-th operation essential parameters covering array size: {len(e_ca)}, "
                    f"parameters: {len(e_ca[0]) if len(e_ca) > 0 else 0}, constraints: {len(operation.constraints)}")

        have_success_e, have_bug_e, e_response_list = self._executes(operation, e_ca, chain, success_url_tuple, history,
                                                                     True)
        is_break_e = have_success_e or have_bug_e

        if all([p.isEssential for p in operation.parameterList]):
            if not is_break_e:
                logger.info("no success request, use llm to help re-generate")
                is_break = self._re_handle(index, operation, chain, sequence, loop_num,
                                           (have_success_e, have_bug_e), None)
                return is_break
            else:
                return is_break_e

        a_ca = self._handle_all_params(operation, sequence[:index], chain, history)
        logger.info(f"{index + 1}-th operation all parameters covering array size: {len(a_ca)}, "
                    f"parameters: {len(a_ca[0]) if len(a_ca) > 0 else 0}, constraints: {len(operation.constraints)}")
        have_success_a, have_bug_a, a_response_list = self._executes(operation, a_ca, chain, success_url_tuple, history,
                                                                     False)
        is_break_a = have_success_a or have_bug_a

        is_break = is_break_e or is_break_a
        response_list = e_response_list + a_response_list

        sc_set = set([sc for (sc, r) in response_list])
        message = None
        if len(sc_set) == 1 and 200 <= sc_set.pop() < 300:
            pass
        elif len(sc_set) == 2 and all((200 <= x < 300) if i == 0 else x == 500 for i, x in enumerate(sorted(sc_set))):
            pass
        else:
            if not operation.grouped:
                message = self._call_response_language_model(operation, response_list)
                operation.set_grouped()

        if not (have_success_e and have_success_a and have_bug_e and have_bug_a):
            status_tuple = (have_success_e, have_success_a, have_bug_e, have_bug_a)
            logger.info("Expected status code(2xx or 500) missing, use llm to help re-generate")
            self._re_count(e_ca, a_ca)
            is_break = self._re_handle(index, operation, chain, sequence, loop_num, status_tuple, message)

        return is_break

    def _cover_params(self, operation, parameters, constraints, chain, history_ca_of_current_op: List[dict]):
        """
        generate domain for each parameter of the current operation
        @param history_ca_of_current_op: ca_1 -> ca_2 -> ca_3, currently, essential_ca -> all_ca
        @param operation: the target operation
        @param parameters: parameter list
        @param constraints: the constraints among parameters
        @param chain: a response chain
        @return: the parameters and their domains
        """

        example_dict = self._manager.get_llm_examples().get(operation)
        llm = False
        constraints_pair = set()

        if history_ca_of_current_op is None:
            history_ca_of_current_op = []

        domain_map = defaultdict(list)
        for root_p in parameters:
            root_p.domain.clear()
            p_with_children = root_p.genDomain(operation.__repr__(), chain, self._manager.get_ok_value_dict())

            for p in p_with_children:
                if self._is_regen:
                    if p.getGlobalName() in example_dict.keys():
                        index = random.randint(0, len(example_dict.get(p.getGlobalName())) - 1)
                        value = DataType.from_string(example_dict.get(p.getGlobalName())[index], p.type)
                        if not isinstance(p, EnumParam):
                            p.domain.append(Value(value, ValueType.Example, p.type))
                        # for value in example_dict.get(p.getGlobalName()):
                        #     value = DataType.from_string(value, p.type)
                        #     if not isinstance(p, EnumParam):
                        #         p.domain.append(Value(value, ValueType.Example, p.type))

                if not self._manager.is_unresolved(operation.__repr__() + p.name):
                    domain_map[p.getGlobalName()] = p.domain

        raw_domain_map = domain_map.copy()

        if history_ca_of_current_op is not None and len(history_ca_of_current_op) > 0:
            domain_map = raw_domain_map
            new_domain_map = {
                "history_ca_of_current_op": [Value(v, ValueType.Reused, DataType.Int32) for v in
                                             range(len(history_ca_of_current_op))]}
            for p in domain_map.keys():
                if p not in history_ca_of_current_op[0].keys():
                    new_domain_map[p] = domain_map.get(p)
            for c in operation.constraints:
                for p in c.paramNames:
                    if self._manager.is_unresolved(p):
                        return [{}]
            domain_map = new_domain_map
        else:
            if (self._manager.get_llm_examples().get(operation) is not None and
                    len(self._manager.get_llm_examples().get(operation)) > 0):
                if self._manager.get_llm_grouped_constraint(operation) is not None:
                    new_domain_map = {}
                    constraint_params = set()
                    for p in self._manager.get_llm_constrainted_params(operation) + self.get_op_constraints(operation):
                        constraint_params.add(p)
                    for pairs in self._manager.get_llm_grouped_constraint(operation):
                        constraints_pair.add(tuple(pairs))
                    for c in operation.constraints:
                        c_l = []
                        for p in operation.parameterList:
                            if p.getGlobalName() in c.ents:
                                c_l.append(p)
                        constraints_pair.add(tuple(c_l))
                    llm = True
                    # example = self._manager.get_llm_examples().get(operation)
                    for n, llm_constraints in enumerate(constraints_pair):
                        p_name = f"constraint{n}"
                        new_domain_map[p_name] = [Value(f"combination{i}", ValueType.Example, DataType.String) for i in
                                                  range(3)]
                    for p in domain_map.keys():
                        if p not in [cp.getGlobalName() for cp in constraint_params]:
                            new_domain_map[p] = domain_map.get(p)
                    domain_map = new_domain_map

        for p, v in domain_map.items():
            logger.debug(f"            {p}: {len(v)} - {v}")

        acts = self._call_acts(domain_map, constraints, self._eStrength, history_ca_of_current_op)
        if llm:
            return self._unpack_llm_response(acts, operation, constraints_pair)
        else:
            return acts

    def _handle_essential_params(self, operation, exec_ops, chain, history):
        """

        :param operation:
        :param exec_ops: sequence[:i]
        :param chain:
        :return:
        """
        for p in operation.parameterList:
            if p in self._manager.get_llm_constrainted_params(operation):
                if not p.isEssential:
                    p.isConstrained = True
        parameter_list = list(filter(lambda p: p.isEssential, operation.parameterList))
        if len(parameter_list) == 0:
            return [{}]

        return self._cover_params(operation, parameter_list, operation.constraints, chain, history)

    def _handle_all_params(self, operation, exec_ops, chain, history):

        parameter_list = operation.parameterList

        return self._cover_params(operation, parameter_list, operation.constraints, chain, history)

    def _unpack_llm_response(self, acts, operation, constraints_pair):
        new_acts = []
        # constraint_params = self._manager.get_llm_grouped_constraint(operation)
        constraint_params = constraints_pair
        example = self._manager.get_llm_examples().get(operation)
        for array in acts:
            new_array = {}
            for c, v in array.items():
                if "constraint" in c:
                    con_index = int(c.replace("constraint", ""))
                    com_index = int(v.val.replace("combination", ""))
                    param_to_unpack = list(constraint_params)[con_index]
                    for p in param_to_unpack:
                        if example[p.getGlobalName()][com_index] != '':
                            value = Value(example[p.getGlobalName()][com_index], ValueType.Example, p.type)
                            new_array[p.getGlobalName()] = value
                        else:
                            if p.required:
                                value = Value(example[p.getGlobalName()][com_index], ValueType.Example, p.type)
                            else:
                                value = Value(None, ValueType.Example, p.type)
                            new_array[p.getGlobalName()] = value
                else:
                    new_array[c] = v
            new_acts.append(new_array)
        return new_acts

    @staticmethod
    def get_op_constraints(operation):
        constraint_str = []
        constraint_param = []
        for c in operation.constraints:
            for p in c.ents:
                constraint_str.append(p)
        for p in operation.parameterList:
            if p.getGlobalName() in constraint_str:
                constraint_param.append(p)
        return constraint_param
