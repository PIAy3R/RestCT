import abc
import json
import os
import random
import shlex
import subprocess

import chardet
from loguru import logger


class Generator(metaclass=abc.ABCMeta):
    def __init__(self, output_folder: str, tool_path: str = None, strength: int = 2):
        self._output_folder = output_folder
        self.output_folder = os.path.join(self._output_folder, "pict")
        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)

        self.counter = 0
        self.tool = tool_path
        self.strength = strength

        # 记录每轮生成多少条测试用例，用于随机测试
        self._test_info = dict()

    @staticmethod
    def _check_fbt(name_mappings: dict[str, str],
                   value_mappings: dict[str, dict[int, str]],
                   ftb: list[dict[str, str]]) -> list[dict[str, int]]:
        """根据domain将不可行的fbt删除，将可行fbt转换成统一表示"""
        """
                将 fbt 和 domain 进行统一
                @param name_mappings: formatted name: original name
                @param value_mappings: formatted name: [(value, [equivalent_name, ...])]
                @param ftb: forbidden tuples
                @return: ftb
                """
        transformed_ftb = []
        for t in ftb:
            new_t = {}
            for global_name, f_v in t.items():
                transformed_name = next(
                    (_transformed for _transformed in name_mappings.keys() if
                     name_mappings[_transformed] == global_name), None)
                if transformed_name is None:
                    break
                transformed_value = next((_transformed for _transformed in value_mappings.get(global_name).keys() if
                                          value_mappings[global_name][_transformed] == f_v), None)
                if transformed_value is not None:
                    new_t[transformed_name] = transformed_value

            if len(new_t.keys()) == len(t.keys()):
                transformed_ftb.append(new_t)

        return transformed_ftb

    @abc.abstractmethod
    def _generate_input_content(self,
                                op_id: str,
                                name_mappings: dict[str, str],
                                value_mappings: dict[str, dict[str, int]],
                                ftb: list[dict[str, int]]):
        """生成工具输入文件内容"""
        raise NotImplementedError()

    def _write_to_file(self, op_id: str, content: str):
        input_file = os.path.join(self.output_folder, f"{self.__class__.__name__}_{op_id}_{self.counter}.txt")
        with open(input_file, "w") as fp:
            fp.write(content)
        return input_file

    @abc.abstractmethod
    def create_command(self, input_file: str, output_file: str, strength: int = 2):
        """创建工具命令"""
        raise NotImplementedError()

    def _run_tool(self, op_id: str, input_file: str, strength: int = 2):
        """运行工具，并返回结果运行工具，并返回结果"""
        output_file = os.path.join(self.output_folder, f"{self.__class__.__name__}_{op_id}_{self.counter}_output.txt")

        command = self.create_command(input_file, output_file, strength)

        stdout, stderr = subprocess.Popen(shlex.split(command, posix=False), stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE).communicate()
        encoding = chardet.detect(stdout)["encoding"]
        if encoding is not None:
            stdout = stdout.decode(encoding)
        else:
            stdout = stdout.decode("utf-8")

        encoding = chardet.detect(stderr)["encoding"]
        if encoding is not None:
            stderr = stderr.decode(encoding)
        else:
            stderr = stderr.decode("utf-8")
        logger.trace(f"ca progress: {stdout}")
        logger.trace(f"ca error: {stderr}")
        return output_file, stdout, stderr

    def save_test_info(self):
        """保存测试信息"""
        to_file = os.path.join(self.output_folder, f"{self.__class__.__name__}_test_info.json")
        with open(to_file, "w", encoding="utf-8") as f:
            json.dump(self._test_info, f, ensure_ascii=False, indent=4)

    @staticmethod
    @abc.abstractmethod
    def _parse_output(name_mappings: dict[str, str],
                      value_mappings: dict[str, dict[int, str]],
                      out_file: str):
        """解析工具输出"""
        raise NotImplementedError()

    def handle(self,
               op_id: str,
               from_func: str,
               params: list[str],
               domains: list[list[str]],
               forbidden_tuples: list[dict[str, str]]) -> list[dict[str, str]]:

        if len(params) == 0:
            return [{}]

        strength = min(self.strength, len(params))

        if op_id not in self._test_info.keys():
            self._test_info[op_id] = {"explored": list(), "triggered": list()}

        self.counter += 1

        ca_op_id = op_id.replace(":", "-").replace("/", "#")

        _name_mappings: dict[str, str] = {f"P{idx}": f for idx, f in enumerate(params)}
        _value_mappings = {f: {e_idx: _e for e_idx, _e in enumerate(domains[f_idx])} for f_idx, f in enumerate(params)}

        fbt = self._check_fbt(_name_mappings, _value_mappings, forbidden_tuples)

        content = self._generate_input_content(ca_op_id, _name_mappings, _value_mappings, fbt)
        input_file = self._write_to_file(ca_op_id, content)
        output_file, _, _ = self._run_tool(ca_op_id, input_file, strength)
        results = self._parse_output(_name_mappings, _value_mappings, output_file)

        if len(results) > 1000:
            results = random.sample(results, k=1000)
        if len(results) == 1:
            d = results[0]
            if any("random" in s.lower() for s in d.values()):
                results = results * 50

        if "explore" in from_func.lower():
            self._test_info[op_id]["explored"].append(len(results))
        elif "trig" in from_func.lower():
            self._test_info[op_id]["triggered"].append(len(results))
        else:
            raise ValueError(f"Unknown function {from_func}")

        return results


class ACTS(Generator):
    def __init__(self, output_folder: str, tool_path: str, strength: int = 2):
        super().__init__(output_folder, tool_path, strength)

    def _generate_input_content(self,
                                op_id: str,
                                name_mappings: dict[str, str],
                                value_mappings: dict[str, dict[str, int]],
                                ftb: list[dict[str, int]]):
        content = "\n".join(
            ['[System]', '-- specify system name', f'Name: CA-{op_id}-{self.counter}', '',
             '[Parameter]', '-- general syntax is parameter_name(type): value1, value2...\n'])

        for transformed_name, f in name_mappings.items():
            content += f"{transformed_name}(int): {','.join([str(idx) for idx in value_mappings.get(f).keys()])}\n"

        content += "\n"

        if len(ftb) > 0:
            content += "[Constraint]\n"
            for t in ftb:
                content += "||".join([f"{f} != {v}" for f, v in t.items()]) + "\n"

        return content

    def create_command(self, input_file: str, output_file: str, strength: int = 2):
        # acts 的文件路径不可以以"\"作为分割符，会被直接忽略，"\\"需要加上repr，使得"\\"仍然是"\\".
        return rf'java -Dalgo=ipog -Ddoi={strength} -Doutput=csv -jar {self.tool} {input_file} {output_file}'

    @staticmethod
    def _parse_output(name_mappings: dict[str, str],
                      value_mappings: dict[str, dict[int, str]],
                      out_file: str):
        if os.path.exists(out_file) is False:
            return [{}]

        with open(out_file, "r") as fp:
            lines = [line.strip("\n") for line in fp.readlines() if "#" not in line and len(line.strip("\n")) > 0]

        # results: [{param_a: used_equivalence}]
        results: list[dict[str, str]] = list()
        param_names = lines[0].strip("\n").split(",")

        for line in lines[1:]:
            d = dict()

            values = line.strip("\n").split(",")
            for i, v in enumerate(values):
                global_name = name_mappings[param_names[i]]
                value = value_mappings[global_name][int(v)]
                d[global_name] = value
            results.append(d)
        return results


class PICT(Generator):
    def __init__(self, output_folder: str, tool_path: str = None, strength: int = 2):
        super().__init__(output_folder, tool_path, strength)

    def _generate_input_content(self, op_id: str, name_mappings: dict[str, str],
                                value_mappings: dict[str, dict[str, int]], ftb: list[dict[str, int]]):
        content = ""
        for transformed_name, f in name_mappings.items():
            content += f"{transformed_name}:{','.join([str(idx) for idx in value_mappings.get(f).keys()])}\n"

        content += "\n"

        if len(ftb) > 0:
            for t in ftb:
                content += " OR ".join([f"[{k}] <> {v}" for k, v in t.items()]) + ";\n"

        return content

    def create_command(self, input_file: str, output_file: str, strength: int = 2):
        r = random.randint(1, 1000)
        return rf"{self.tool} {input_file} /o:{strength} /r:{r}"

    def handle(self,
               op_id: str,
               from_func: str,
               params: list[str],
               domains: list[list[str]],
               forbidden_tuples: list[dict[str, str]]) -> list[dict[str, str]]:
        if len(params) == 0:
            return [{}]

        if op_id not in self._test_info.keys():
            self._test_info[op_id] = {"explored": list(), "triggered": list()}

        strength = min(self.strength, len(params))

        self.counter += 1

        ca_op_id = op_id.replace(":", "-").replace("/", "#")

        _name_mappings: dict[str, str] = {f"P{idx}": f for idx, f in enumerate(params)}
        _value_mappings = {f: {e_idx: _e for e_idx, _e in enumerate(domains[f_idx])} for f_idx, f in enumerate(params)}

        fbt = self._check_fbt(_name_mappings, _value_mappings, forbidden_tuples)

        content = self._generate_input_content(ca_op_id, _name_mappings, _value_mappings, fbt)
        input_file = self._write_to_file(ca_op_id, content)
        _, stdout, stderr = self._run_tool(ca_op_id, input_file, strength)
        if len(stdout) == 0:
            return [{}]

        results = self._parse_output(_name_mappings, _value_mappings, stdout)

        if len(results) > 1000:
            results = random.sample(results, k=1000)
        if len(results) == 1:
            d = results[0]
            if any("random" in s.lower() for s in d.values()):
                results = results * 50

        if "explore" in from_func.lower():
            self._test_info[op_id]["explored"].append(len(results))
        elif "trig" in from_func.lower():
            self._test_info[op_id]["triggered"].append(len(results))
        else:
            raise ValueError(f"Unknown function {from_func}")

        return results

    @staticmethod
    def _parse_output(name_mappings: dict[str, str], value_mappings: dict[str, dict[int, str]], out_file: str):
        # results: [{param_a: used_equivalence}]
        results: list[dict[str, str]] = list()

        param_names = None
        for line in out_file.split("\n"):
            line = line.strip()
            if line.startswith("Used seed:") or line == "":
                continue
            if line.startswith("P"):
                param_names = [p.strip() for p in line.split("\t")]
            else:
                d = dict()

                values = [v.strip() for v in line.split("\t")]
                for i, v in enumerate(values):
                    global_name = name_mappings[param_names[i]]
                    value = value_mappings[global_name][int(v)]
                    d[global_name] = value
                results.append(d)
        return results


class Randomize(Generator):
    def __init__(self, output_folder: str):
        super().__init__(output_folder, None)

    def _generate_input_content(self, op_id: str, name_mappings: dict[str, str],
                                value_mappings: dict[str, dict[str, int]], ftb: list[dict[str, int]]):
        pass

    def create_command(self, input_file: str, output_file: str, strength: int = 2):
        pass

    @staticmethod
    def _parse_output(name_mappings: dict[str, str], value_mappings: dict[str, dict[int, str]], out_file: str):
        pass

    @staticmethod
    def _solve_constraints(factors: list[str], domains: list[list[str]], constraints: list[dict[str, str]]):
        def is_valid_assignment(assignment):
            for constraint in constraints:
                # Check if the current assignment violates any constraint
                if all(assignment[param] == value for param, value in constraint.items()):
                    return False
            return True

        def dfs(param_idx, assignment):
            param = factors[param_idx]
            if param_idx == len(factors):
                # Check if the current assignment satisfies all constraints
                if is_valid_assignment(assignment):
                    solutions.append(assignment.copy())
                return

            domain = domains[param_idx]
            for value in domain:
                assignment[param] = value
                dfs(param_idx + 1, assignment)

        solutions = []
        initial_assignment = dict()
        dfs(0, initial_assignment)
        return solutions

    def handle(self,
               op_id: str,
               from_func: str,
               params: list[str],
               domains: list[list[str]],
               forbidden_tuples: list[dict[str, str]]) -> list[dict[str, str]]:
        if "explore" in from_func.lower():
            num_list = self._test_info.get(op_id, {}).get("explored")
        elif "trig" in from_func.lower():
            num_list = self._test_info.get(op_id, {}).get("triggered")
        else:
            raise Exception(f"Unknown from_func: {from_func}")

        if len(num_list) == 0:
            return []

        num = num_list.pop(0)

        _name_mappings: dict[str, str] = {f"P{idx}": f for idx, f in enumerate(params)}
        _value_mappings = {f: {e_idx: _e for e_idx, _e in enumerate(domains[f_idx])} for f_idx, f in enumerate(params)}
        fbt = self._check_fbt(_name_mappings, _value_mappings, forbidden_tuples)
        constraints = [
            {_name_mappings[transformed_f]: _value_mappings[int(v_idx)] for transformed_f, v_idx in d.items()} for d in
            fbt if len(d) > 0]

        factors_without_constraints = []
        domains_without_constraints = []
        factors_with_constraints = []
        domains_with_constraints = []
        for f, d in zip(params, domains):
            if any(f in c.keys() for c in constraints):
                factors_with_constraints.append(f)
                domains_with_constraints.append(d)
            else:
                factors_without_constraints.append(f)
                domains_without_constraints.append(d)

        solutions = []
        if len(factors_with_constraints) > 0:
            solutions = self._solve_constraints(factors_with_constraints, domains_with_constraints, constraints)
            if len(solutions) == 0:
                return []

        results = []
        while True:
            case = {_f: random.choice(_d) for _f, _d in zip(factors_without_constraints, domains_without_constraints)}
            if len(solutions) > 0:
                case.update(random.choice(solutions))
            results.append(case)
            if len(results) == num:
                break
        return results
   