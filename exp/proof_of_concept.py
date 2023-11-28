# 2023.11.22
import csv
import json
import os
import re

import spacy
from openapi_parser.parser import parse
from openapi_parser.specification import *


class Analyser:
    def __init__(self):
        self.root_dir = "/Users/lixin/Workplace/Jupyter/work"
        self.swaggers = ["swaggers/GitLab"]
        self.logs = ["poc_csv/branch", "poc_csv/commit", "poc_csv/groups", "poc_csv/issues", "poc_csv/repository",
                     "poc_csv/projects"]

        self.nlp = spacy.load("en_core_web_sm")

        # processed data
        self.enum_param_list = dict()
        self.enum_values = dict()
        self.numeric_param_list = dict()
        self.all_param_list = dict()

        self.filtered_data = dict()
        self.not_param_names = ["Operation", "Timestamp", "statuscode", "response"]
        self.error_messages = dict()

    def _extract_info_from_spec(self, op_id, name, schema):
        if isinstance(schema, Boolean):
            self.enum_param_list[op_id].add(name)
        elif len(schema.enum) > 0:
            if op_id not in self.enum_values.keys():
                self.enum_values[op_id] = dict()
            self.enum_param_list[op_id].add(name)
            self.enum_values[op_id][name] = [e for e in schema.enum]
        elif isinstance(schema, (Integer, Number)):
            self.numeric_param_list[op_id].add(name)
        elif isinstance(schema, String):
            if schema.format is not None and schema.format.value in ["date-time", "date", "time"]:
                self.numeric_param_list[op_id].add(name)
        else:
            pass

        self.all_param_list[op_id].add(name)

    def _parse_swagger(self, swagger):
        for path in swagger.paths:
            for operation in path.operations:
                key = f"{operation.method.value}***{path.url}"
                if key not in self.enum_param_list.keys():
                    self.enum_param_list[key] = set()
                if key not in self.numeric_param_list.keys():
                    self.numeric_param_list[key] = set()
                if key not in self.all_param_list:
                    self.all_param_list[key] = set()

                for param in operation.parameters:
                    name = param.name
                    schema = param.schema
                    self._extract_info_from_spec(key, name, schema)

                body = operation.request_body
                if body is not None:
                    if isinstance(body.content, Object):
                        for p in body.content.properties:
                            self._extract_info_from_spec(key, p.name, p.schema)

    def extract_swagger(self, folder: str):
        for path in os.listdir(folder):
            if path.endswith(".json"):
                print(path)
                swagger = parse(os.path.join(folder, path))

                self._parse_swagger(swagger)

    def save_spec_info(self):
        data = [(self.all_param_list, "all_param.json"), (self.enum_param_list, "enum_param.json"),
                (self.numeric_param_list, "numeric_param.json"), (self.enum_values, "enum_value.json")]
        for (v, f) in data:
            # set -> list
            for k_, v_ in v.items():
                if isinstance(v_, set):
                    v[k_] = list(v_)
            f_path = os.path.join(self.root_dir, f)
            with open(f_path, "w") as fp:
                json.dump(v, fp, indent=2)

    def initialize(self):
        for swagger_folder in self.swaggers:
            abs_folder = os.path.join(self.root_dir, swagger_folder)
            self.extract_swagger(abs_folder)

        self.save_spec_info()

    def parse_log(self):
        for log_folder in self.logs:
            abs_folder = os.path.join(self.root_dir, log_folder)
            for json_file in os.listdir(abs_folder):
                if json_file.endswith(".csv"):
                    self._process_log_csv(os.path.join(abs_folder, json_file))

    def _find_key(self, verb, url):
        for key in self.all_param_list.keys():
            k_verb, k_uri = key.split("***")
            if k_verb.lower() == verb.lower() and url.endswith(k_uri):
                return key

        raise ValueError(f"can not find  key for {verb} {url}")

    def _handle_success_case(self, key, line):
        if key not in self.filtered_data.keys():
            self.filtered_data[key] = []

        case = self.do_case(key, line)
        case["20X"] = 1
        self.filtered_data[key].append(case)

    def do_case(self, key, line):
        case = dict()
        for name in line.keys():
            if name in self.not_param_names:
                continue
            value = line[name]
            if value == "null":
                case[name] = "E_NULL"
            elif name in self.enum_param_list.get(key, []):
                case[name] = "E_" + value
            else:
                if len(value) == 0:
                    case[name] = "E_LEN_0"
                else:
                    case[name] = "E_FILLED"
        return case

    def _handle_failed_case(self, key, line):
        if key not in self.filtered_data.keys():
            self.filtered_data[key] = []
        if key not in self.error_messages.keys():
            self.error_messages[key] = set()

        case = self.do_case(key, line)
        message = line["response"]
        if message.startswith("{") and message.endswith("}"):
            texts = self._parse_json(key, line, json.loads(message))
        else:
            texts = self._parse_text(key, line, message)

        for (pattern, involved_params) in texts:
            params_string = "+".join(involved_params)
            self.error_messages[key].add((pattern, *involved_params))
            case[f"Y_{pattern}***{params_string}"] = 1
        self.filtered_data[key].append(case)

    def _parse_json(self, key, line, message, extra=None) -> list:
        if isinstance(message, dict):
            results = []
            for k, v in message.items():
                results.extend(self._parse_json(key, line, v, k))
            return results
        elif isinstance(message, list):
            results = []
            for item in message:
                results.extend(self._parse_json(key, line, item, extra))
            return results
        else:
            return self._parse_text(key, line, message, extra)

    def _parse_text(self, key, line, message, extra=None) -> list:
        doc = self.nlp(message)
        results = list()
        for s in doc.sents:
            pattern, involved = self._parse_sentence(key, line, s.text)
            if extra is not None:
                extra_pattern, extra_involved = self._parse_sentence(key, line, extra)
                pattern = f"{extra_pattern}:{pattern}"
                involved.extend(extra_involved)

            if len(involved) > 0:
                results.append((pattern, list(set(involved))))

        return results

    def _parse_sentence(self, key, line, sentence: str) -> tuple:
        involved = set()
        for name in self.all_param_list[key]:
            # match name in the sentence as a whole word
            escaped_name = re.escape(name)
            matched = re.search(rf"\b{escaped_name}\b", sentence)

            if matched:
                sentence = re.sub(rf"\b{escaped_name}\b", "__PARAM__", sentence)
                involved.add(name)

        for k, v in line.items():
            if k in self.not_param_names or v == "__null__" or len(v) == 0:
                continue
            if len(involved) > 0 and k not in involved:
                continue
            escaped_v = re.escape(v)
            re_pattern = re.compile(rf'(?:(?<=^)|(?<=\W)){escaped_v}(?=\W|$)')
            matched = re_pattern.search(sentence)
            if matched:
                sentence = re_pattern.sub("__VALUE__", sentence)
                involved.add(k)
                break
        return sentence, list(involved)

    def _process_log_csv(self, abs_file_path):
        # 少了一列header， 补全
        # with open(abs_file_path, "r") as fp:
        #     lines = fp.readlines()
        #     lines[0] = lines[0].replace(",response message", ",status_code, response")
        # with open(abs_file_path, "w") as fp:
        #     fp.writelines(lines)
        with open(abs_file_path, "r") as fp:
            reader = csv.DictReader(row.replace('\0', '').replace('\x00', '') for row in fp)
            for line in reader:
                verb, url = line["Operation"].split("***")
                key = self._find_key(verb, url)
                if line["statuscode"].startswith('2'):
                    self._handle_success_case(key, line)
                else:
                    self._handle_failed_case(key, line)

    def save_result(self):
        # 补全 dict
        for key, cases in self.filtered_data.items():
            errors = self.error_messages.get(key, set())
            if len(errors) == 0:
                continue
            for case in cases:
                for (pattern, *param) in errors:
                    param_string = "+".join(param)
                    y = f"Y_{pattern}***{param_string}"
                    if y not in case.keys():
                        if "20X" in case.keys():
                            case[y] = 0
                        else:
                            case[y] = -1

        f_path = os.path.join(self.root_dir, "result.json")
        with open(f_path, "w") as fp:
            json.dump(self.filtered_data, fp, indent=2)


if __name__ == '__main__':
    a = Analyser()
    a.initialize()
    a.parse_log()
    a.save_result()
