import os
import shlex
import subprocess
from typing import Dict, Union, Optional, List, Tuple

import chardet

from src.factor import *
from src.factor.equivalence import AbstractBindings, Enumerated, Null
from src.rest import RestOp


class CA:
    """
    generate parameter covering array for each restOP in the same test case
    """

    def __init__(self):
        self.test_case_id = 0

        self.generator = ArrayGenerator()

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

    def _validate_equivalences(self):
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

    def handle(self, sequence: List[RestOp]):
        self.reset()

        for op in sequence:
            self.op = op

            # validate all equivalences that is related to the previous executed request
            self._validate_equivalences()

            # generate domain
            for param in self.op.parameters:
                for f in param.factor.get_leaves():
                    f.generate_domain()

            # generate covering arrays


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
            if isinstance(_f, (FloatFactor, DateFactor, TimeFactor, DateTimeFactor)):
                sorted_domain = sorted(filter(lambda v: v != Null.NULL_STRING, _f.domain))
                self._mappings[_f.global_name] = [sorted_domain.index(v) + 1 for v in _f.domain if
                                                  v != Null.NULL_STRING]
                if Null.NULL_STRING in _f.domain:
                    self._mappings[_f.global_name].insert(_f.domain.index(Null.NULL_STRING), 0)

        for t in self.forbidden_tuples:
            for global_name, f_v in t.items():
                matched = list(filter(lambda f: f.global_name == global_name, self.factors))
                if len(matched) == 0:
                    raise ValueError(
                        f"CA {self.counter}: forbidden tuple's global name {global_name} not found in factors")
                target = matched[0]
                if f_v not in target.domain:
                    raise ValueError(f"CA {self.counter}: forbidden tuple's value {f_v} not found in factor's domain")

                if global_name in self._mappings.keys():
                    t[global_name] = self._mappings[global_name][target.domain.index(f_v)]

    def _generate_input_content(self):
        content = "\n".join(
            ['[System]', '-- specify system name', f'Name: CA-{self.counter}', '',
             '[Parameter]', '-- general syntax is parameter_name(type): value1, value2...\n'])

        for f in self.factors:
            if isinstance(f, IntegerFactor):
                content += f.global_name + "(int): " + ", ".join(map(str, f.domain)) + "\n"
            elif isinstance(f, (FloatFactor, DateFactor, TimeFactor, DateTimeFactor)):
                content += f.global_name + "(int): " + ", ".join(map(str, self._mappings[f.global_name])) + "\n"
            elif isinstance(f, BoolFactor):
                content += f.global_name + "(boolean): " + ", ".join(map(str, f.domain)) + "\n"
            elif isinstance(f, EnumFactor):
                # todo: if enum values are comparable
                content += f.global_name + "(enum): " + ", ".join(map(str, f.domain)) + "\n"
            else:
                content += f.global_name + "(enum): " + ", ".join(map(str, f.domain)) + "\n"

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
               strength: int = 2) -> List[Dict[str, list]]:
        self.factors = factor
        self.forbidden_tuples = forbidden_tuples
        self.counter += 1

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

        a: List[Dict[str, list]] = list()
        param_names = lines[0].strip("\n").split(",")
        for line in lines[1:]:
            d = dict()

            values = line.strip("\n").split(",")
            for i, v in enumerate(values):
                factor = list(filter(lambda f: f.global_name == param_names[i], self.factors))[0]
                if param_names[i] in self._mappings.keys():
                    index = self._mappings[param_names[i]].index(int(v))
                    d[param_names[i]] = factor.domain[index]
                else:
                    if v == Null.NULL_STRING:
                        d[param_names[i]] = Null.NULL_STRING
                    elif isinstance(factor, IntegerFactor):
                        d[param_names[i]] = int(v)
                    elif isinstance(factor, BoolFactor):
                        d[param_names[i]] = bool(v)
                    else:
                        d[param_names[i]] = v

            a.append(d)
        return a
