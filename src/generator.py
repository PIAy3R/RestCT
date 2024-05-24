import os
import random
import re
import shlex
import subprocess
from pathlib import Path
from typing import Dict, List

import chardet

from src.factor import Value
from src.nlp import Constraint


class ACTS:
    def __init__(self, data_path, jar):
        self._workplace = Path(data_path) / "acts"
        self.jar = jar
        if not self._workplace.exists():
            self._workplace.mkdir()

    @staticmethod
    def get_id(operation, param_name, domain_map):
        global_name = param_name
        for f in operation.get_leaf_factors():
            if f.name == param_name:
                global_name = f.get_global_name
                break
        index = domain_map.index(global_name)
        return "P" + str(index)

    @staticmethod
    def get_name(param_id: str, domain_map):
        index = int(param_id.lstrip("P"))
        return domain_map[index]

    def transformConstraint(self, operation, domain_map, paramNames, constraint: Constraint):
        cStr = constraint.toActs(operation, domain_map)
        if cStr is None:
            return ""
        for paramName in constraint.paramNames:
            pattern = r"\b" + paramName + r"\b"
            paramId = self.get_id(operation, paramName, paramNames)
            cStr = re.sub(re.compile(pattern), paramId, cStr)
        return eval(cStr)

    def writeInput(self, operation, domain_map, param_names, constraints, strength) -> Path:
        inputFile = self._workplace / "input.txt"
        with inputFile.open("w") as fp:
            fp.write(
                "\n".join(
                    ['[System]', '-- specify system name', 'Name: {}'.format("acts" + str(strength)), '',
                     '[Parameter]', '-- general syntax is parameter_name(type): value1, value2...\n'])
            )
            # write parameter ids
            for paramName, domain in domain_map.items():
                fp.write("{}(int):{}\n".format(self.get_id(operation, paramName, param_names),
                                               ",".join([str(i) for i in range(len(domain))])))

            fp.write("\n")
            # write constraints
            if len(constraints) > 0:
                fp.write("[Constraint]\n")
                for c in constraints:
                    [fp.write(ts + "\n") for ts in self.transformConstraint(operation, domain_map, param_names, c)]

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

    def parseOutput(self, outputFile: Path, domain_map, param_names, history_ca_of_current_op: List[dict]):
        with outputFile.open("r") as fp:
            lines = [line.strip("\n") for line in fp.readlines() if "#" not in line and len(line.strip("\n")) > 0]
        param_names = [self.get_name(paramId, param_names) for paramId in lines[0].strip("\n").split(",")]
        coverArray: List[Dict[str, Value]] = list()
        for line in lines[1:]:
            valueDict = dict()
            valueIndexList = line.strip("\n").split(",")
            for i, valueIndex in enumerate(valueIndexList):
                valueDict[param_names[i]] = domain_map[param_names[i]][int(valueIndex)]
            if "history_ca_of_current_op" in valueDict.keys():
                history_index = valueDict.pop("history_ca_of_current_op")
                valueDict.update(history_ca_of_current_op[history_index.val])
            coverArray.append(valueDict)

        return coverArray

    def process(self, operation, domain_map, constraints: List[Constraint], strength: int,
                history_ca_of_current_op: List[dict]):
        strength = min(strength, len(domain_map.keys()))
        param_names = list(domain_map.keys())
        inputFile = self.writeInput(operation, domain_map, param_names, constraints, strength)
        outputFile = self.callActs(strength, inputFile)
        return self.parseOutput(outputFile, domain_map, param_names, history_ca_of_current_op)


class PICT:
    def __init__(self, data_path, pict):
        self._workplace = Path(data_path) / "pict"
        self.pict = pict
        if not self._workplace.exists():
            self._workplace.mkdir()

    @staticmethod
    def get_id(operation, param_name, domain_map):
        global_name = param_name
        for f in operation.get_leaf_factors():
            if f.name == param_name:
                global_name = f.get_global_name
                break
        index = domain_map.index(global_name)
        return "P" + str(index)

    def process(self, domain_map, op, strength: int, history_ca_of_current_op: List[dict], manager):
        _name_mappings: dict[str, str] = {f"P{idx}": f for idx, f in enumerate(domain_map.keys())}
        _value_mappings = {f: {e_idx: _e for e_idx, _e in enumerate(domain_map[f])} for f_idx, f in
                           enumerate(domain_map.keys())}
        strength = min(strength, len(domain_map.keys()))
        input_file = self._write_input(op, _name_mappings, _value_mappings, domain_map, manager)
        output_file, stdout, stderr = self._call_pict(input_file, strength)
        results = self._parse_output(_name_mappings, _value_mappings, output_file, history_ca_of_current_op)
        return results

    def _write_input(self, operation, name_mappings, value_mappings, domain_map, manager):
        input_file = self._workplace / "pict.txt"
        content = ""
        for transformed_name, f in name_mappings.items():
            content += f"{transformed_name}: {', '.join([str(idx) for idx in value_mappings.get(f).keys()])}\n"
        content += "\n"
        if not name_mappings.get("P0") == "history_ca_of_current_op":
            if not operation.is_re_handle:
                if len(operation.constraints) > 0:
                    for c in operation.constraints:
                        c_str = self._transform_constraints(operation, domain_map, c)
                        for cs in c_str:
                            content += cs + ";\n"
            else:
                c = self._write_llm_constraints(operation, manager, domain_map)
                content += c
        with input_file.open("w") as fp:
            fp.write(content)
        return input_file

    def _call_pict(self, input_file, strength):
        output_file = os.path.join(self._workplace, f"output.txt")

        r = random.randint(1, 1000)
        command = rf"{self.pict} {input_file} /o:{strength} /r:{r}"

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
        with open(output_file, "w") as fp:
            fp.write(stdout)
        return output_file, stdout, stderr

    def _parse_output(self, name_mappings, value_mappings, output_file, history):
        results: list[dict[str, Value]] = list()

        param_names = None
        with open(output_file, "r") as fp:
            output_file = fp.read()
        for line in output_file.split("\n"):
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
                if "history_ca_of_current_op" in d.keys():
                    history_index = d.pop("history_ca_of_current_op")
                    d.update(history[history_index.val])
                results.append(d)
        return results

    def _transform_constraints(self, operation, domain_map, constraint):
        cStr = constraint.to_pict(operation, domain_map)
        if cStr is None:
            return ""
        for paramName in constraint.paramNames:
            pattern = r"\b" + paramName + r"\b"
            paramId = self.get_id(operation, paramName, list(domain_map.keys()))
            cStr = re.sub(re.compile(pattern), paramId, cStr)
        return self._transform_to_pict(cStr)

    def _transform_to_pict(self, cStr):
        transformed = []
        for c in eval(cStr):
            replaced = []
            for exp in c.split("=>"):
                exp = exp.replace("==", "=")
                exp = exp.replace("!=", "<>")
                exp = exp.replace("||", "OR")
                exp = exp.replace("&&", "AND")
                replaced.append(exp)
            c_str = f"IF {replaced[0]} THEN {replaced[1]}"
            transformed.append(c_str)
        return tuple(transformed)

    def _write_llm_constraints(self, operation, manager, domain_map):
        constraints = manager.get_pict(operation)
        if len(constraints) == 0:
            return ""
        else:
            content = ""
            for c in constraints:
                param_names = []
                for p in operation.get_leaf_factors():
                    if p.get_global_name in c:
                        param_names.append(p.get_global_name)
                for param_name in sorted(param_names, reverse=True, key=lambda s: len(s)):
                    paramId = self.get_id(operation, param_name, list(domain_map.keys()))
                    c = c.replace(param_name, f"[{paramId}]")
                pattern = r'"([^"]+)"|\'([^\']+)\''
                quoted_words = re.findall(pattern, c)
                words = [word[0] if word[0] else word[1] for word in quoted_words]
                if len(words) == 0:
                    for param_name in param_names:
                        value_list = [str(v.val) for v in domain_map[param_name]]
                        for v_str in value_list:
                            if v_str in c:
                                c = c.replace(v_str, str(value_list.index(v_str)))
                    content += c + "\n\n"
                else:
                    to_add = True
                    for word in words:
                        value_all = []
                        for param_name in param_names:
                            value_list = [str(v.val) for v in domain_map[param_name]]
                            value_all += value_list
                            for v_str in value_list:
                                if v_str in c:
                                    c = c.replace(v_str, str(value_list.index(v_str)))
                        if word not in value_all:
                            to_add = False
                            break
                    if to_add:
                        c = c.replace("'", "")
                        c = c.replace("\"", "")
                        content += c + "\n\n"
            return content
