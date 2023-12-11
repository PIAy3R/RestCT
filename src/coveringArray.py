import copy
import os
import shlex
import subprocess
from itertools import chain
from random import choice
from typing import Dict, Union, Optional, List, Tuple

import chardet

from src.executor import RestRequest
from src.factor import *
from src.factor.equivalence import AbstractBindings, Enumerated, Null
from src.rest import RestOp, PathParam, QueryParam, HeaderParam


class CA:
    """
    generate parameter covering array for each restOP in the same test case
    """

    def __init__(self, strength: int):
        self.test_case_id = 0
        self.strength = strength
        self.generator = ArrayGenerator()
        self.executor = None

        # historical responses of executed http requests in the case
        self._historical_responses: Dict[str, Union[dict, list, str]] = dict()

        # current http request
        self.op: Optional[RestOp] = None
        self.response: Optional[Union[dict, list, str]] = None

    def reset(self):
        self.op = None
        self.response = None
        self._historical_responses = dict()
        self.test_case_id += 1

    def _filter_equivalences(self):
        """
        remove unrealistic equivalences
        """
        for param in self.op.parameters:
            for f in param.factor.get_leaves():
                for e in f.equivalences:
                    if isinstance(e, AbstractBindings):
                        if e.target_op == self.op.__str__():
                            # 同一操作的参数约束先不处理
                            pass
                        elif e.target_op not in self._historical_responses.keys():
                            f.equivalences.remove(e)
                        elif e.target_op in self._historical_responses.keys():
                            # 不同操作的参数约束先不处理
                            e.update(responses=self._historical_responses)
                        else:
                            raise ValueError("Equivalence's target_op must be in _historical_responses")

                if len(f.equivalences) == 0:
                    # 参数没有赋值策略
                    f.equivalences.append(Enumerated(1))
                if isinstance(param, PathParam) and len(f.equivalences) > 1:
                    # 路径参数通过url关系进行绑定，只需要一个对应的值即可
                    e_list = [e for e in f.equivalences]
                    f.equivalences.clear()
                    f.equivalences.append(choice(e_list))

    @staticmethod
    def _update_bindings(op: RestOp):
        """
        update bindings among self.op.parameters
        self.op有一些参数的取值依赖于同个操作的其他参数
        当参数覆盖表生成后，绑定的参数也可以确定值了
        """
        factors = list(chain(*[_p.factor.get_leaves() for _p in op.parameters]))
        for param in op.parameters:
            for f in param.factor.get_leaves():
                for e in f.equivalences:
                    if isinstance(e, AbstractBindings) and e.target_op == op.__str__():
                        target = next(filter(lambda x: x.name == e.target_param, factors), None)
                        if target is None:
                            raise ValueError(f"target {e.target_param} not found")
                        if target.domain[target.index] == AbstractBindings.NOT_SET:
                            raise ValueError(f"target {e.target_param} not set")
                        e.update(inputs={target.global_name: target.domain[target.index]})

    @staticmethod
    def _update_domain_index(op: RestOp, case: Dict[str, int]):
        """
        @param case: 参数覆盖表的一个用例
        """
        for param in op.parameters:
            for f in param.factor.get_leaves():
                f.index = case[f.name]

    def _handle_one_case(self, case: Dict[str, int]) -> Tuple[int, Union[dict, str]]:
        """
        @param case: 参数覆盖表的一个用例
        """
        op = copy.deepcopy(self.op)

        self._update_domain_index(op, case)
        self._update_bindings(op)

        status_code, response = self._execute_case(op)
        if self.response is not None and 200 < status_code < 300:
            self.response = response

    def _execute_case(self, op: RestOp) -> Tuple[int, Union[dict, str]]:
        url = op.resolve_url()
        method = op.verb
        query_params = {p.factor.name: p.factor.printable_value for p in op.parameters if
                        isinstance(p, QueryParam) and p.factor.value != Null.NULL_STRING}
        header_params = {p.factor.name: p.factor.printable_value for p in op.parameters if
                         isinstance(p, HeaderParam) and p.factor.value != Null.NULL_STRING}
        path_param = next(filter(lambda p: isinstance(p, PathParam), op.parameters), None)
        kwargs = dict()
        body = None
        if path_param is not None:
            kwargs["Content-Type"] = path_param.factor.content_type
            body = path_param.factor.printable_value

        return self.executor.send(method, url, headers=header_params, query=query_params, body=body, **kwargs)

    def handle(self, sequence: List[RestOp]):
        self.reset()

        max_iteration = 5

        for op in sequence:
            self.op = copy.deepcopy(op)

            # validate all equivalences that is related to the previous executed request
            self._filter_equivalences()

            # generate domain
            for param in self.op.parameters:
                param.factor.generate_domain()

            # generate covering arrays
            covering_arrays: List[Dict[str, int]] = self.generator.handle(
                list(chain(*[_p.factor.get_leaves() for _p in self.op.parameters])),
                [],
                self.strength)

            for case in covering_arrays:
                self._handle_one_case(case)

            if self.response is not None:
                self._historical_responses[op.__str__()] = self.response
                self.response = None


class ArrayGenerator:
    def __init__(self):
        self.output_folder = os.getenv("OUTPUT_FOLDER", None)
        if self.output_folder is None:
            raise ValueError("OUTPUT_FOLDER is not set")
        if os.path.exists(self.output_folder) is False:
            os.mkdir(self.output_folder)

        self.acts_jar = os.getenv("ACTS_JAR", None)
        self.counter = 0
        if self.acts_jar is None:
            raise ValueError("ACTS_JAR is not set")
        if os.path.exists(self.acts_jar) is False:
            raise ValueError(f"ACTS_JAR {self.acts_jar} does not exist")

        self.factors: Optional[List[AbstractFactor]] = None
        self.forbidden_tuples: Optional[List[Dict[str, Union[str, int, float]]]] = None

        self._mappings: Dict[str, List[int, str, bool]] = dict()

    def _check(self):
        """
        1) acts 不支持的float, date, time, datetime型变成int型
        2) check forbidden tuples 涉及的参数和值是否存在
        3) 基于float, date, time和datetime参数的特殊性，映射forbidden tuples
        """
        for _f in self.factors:
            if isinstance(_f, (FloatFactor, DateFactor, TimeFactor, DateTimeFactor, IntegerFactor)):
                sorted_domain = sorted(filter(lambda v: v != Null.NULL_STRING, _f.domain))
                self._mappings[_f.global_name] = [sorted_domain.index(v) + 1 for v in _f.domain if
                                                  v != Null.NULL_STRING]
                if Null.NULL_STRING in _f.domain:
                    self._mappings[_f.global_name].insert(_f.domain.index(Null.NULL_STRING), 0)
            elif isinstance(_f, (StringFactor, EnumFactor)):
                self._mappings[_f.global_name] = [i + 1 for i in range(len(_f.domain))]
            else:
                continue

        for t in self.forbidden_tuples:
            for global_name, f_v in t.items():
                matched = next(filter(lambda f: f.global_name == global_name, self.factors), None)
                if matched is None:
                    raise ValueError(
                        f"CA {self.counter}: forbidden tuple's global name {global_name} not found in factors")
                if f_v not in matched.domain:
                    raise ValueError(f"CA {self.counter}: forbidden tuple's value {f_v} not found in factor's domain")

                if global_name in self._mappings.keys():
                    t[global_name] = self._mappings[global_name][matched.domain.index(f_v)]

    def _generate_input_content(self):
        content = "\n".join(
            ['[System]', '-- specify system name', f'Name: CA-{self.counter}', '',
             '[Parameter]', '-- general syntax is parameter_name(type): value1, value2...\n'])

        for f in self.factors:
            if f.global_name in self._mappings.keys():
                # todo: if enum values are comparable
                content += f.global_name + "(int): " + ", ".join(map(str, self._mappings[f.global_name])) + "\n"
            else:
                raise ValueError(f"CA {self.counter}: {f.global_name} is not mapped")

        content += "\n"

        if self.forbidden_tuples is not None and len(self.forbidden_tuples) > 0:
            content += "[Constraint]\n"
            for t in self.forbidden_tuples:
                content += "||".join([f"{n} != {v}" for n, v in t.items()]) + "\n"

        return content

    def _write_to_file(self, content: str):
        input_file = os.path.join(self.output_folder, f"ca_{self.counter}.txt")
        with open(input_file, "w") as fp:
            fp.write(content)
        return input_file

    def handle(self, factor: List[AbstractFactor], forbidden_tuples: List[Tuple[Union[str, int, float]]],
               strength: int = 2) -> List[Dict[str, int]]:
        self.factors = factor
        self.forbidden_tuples = forbidden_tuples
        self.counter += 1
        self._mappings.clear()

        self._check()

        content = self._generate_input_content()
        input_file = self._write_to_file(content)
        output_file = self.run_acts(input_file, strength)
        return self._parse_output(output_file)

    def run_acts(self, input_file: str, strength: int = 2):
        output_file = os.path.join(self.output_folder, f"ca_{self.counter}_output.txt")

        # acts 的文件路径不可以以"\"作为分割符，会被直接忽略，"\\"需要加上repr，使得"\\"仍然是"\\".
        command = rf'java -Dalgo=ipog -Ddoi={strength} -Doutput=csv -jar {self.acts_jar} {input_file} {output_file}'

        stdout, stderr = subprocess.Popen(shlex.split(command, posix=False), stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE).communicate()
        encoding = chardet.detect(stdout)["encoding"]
        stdout.decode(encoding)
        return output_file

    def _parse_output(self, out_file: str):
        with open(out_file, "r") as fp:
            lines = [line.strip("\n") for line in fp.readlines() if "#" not in line and len(line.strip("\n")) > 0]

        a: List[Dict[str, int]] = list()
        param_names = lines[0].strip("\n").split(",")
        for line in lines[1:]:
            d = dict()

            values = line.strip("\n").split(",")
            for i, v in enumerate(values):
                # 返回的是value在factor.domain中的索引
                d[param_names[i]] = self._mappings[param_names[i]].index(int(v))
            a.append(d)
        return a


if __name__ == '__main__':
    os.environ["OUTPUT_FOLDER"] = "/Users/lixin/Desktop"
    os.environ["ACTS_JAR"] = "/Users/lixin/Workplace/Python/PRestCT/lib/acts_2.93.jar"

    from swagger import ParserV3
    from bindingFactory import Builder
    from sequence import SCA

    from executor import HeaderAuth, Auth

    header_auth = HeaderAuth("Authorization", "Bearer GzyzXQYAsPkcRLZzeNTp")
    auth = Auth(header_auth=header_auth)

    parser = ParserV3("/Users/lixin/Workplace/Jupyter/work/swaggers/GitLab/Project.json")
    operations = parser.extract()
    builder = Builder()
    builder.initialize(operations)
    builder.initialize_factors_equivalence()

    ca = CA(2)
    ca.executor = RestRequest(auth)

    for seq in SCA.create_sca_model(2, builder.op_groups):
        ca.handle(seq)
        break
