import re

from src.nlp import Constraint
from src.rest import RestOp


class IDL:
    def __init__(self, idl: str, operation: RestOp):
        self._idl = idl
        self._operation = operation

    def to_constraint(self):
        ents = []
        param_names = set()
        values = set()
        for p in self._operation.get_leaf_factors():
            if p.get_global_name in self._idl:
                p.is_constraint = True
                ents.append(p.get_global_name)
                param_names.add(p.get_global_name)

        if "==" or "!=" in self._idl:
            match = re.search(r'"([^"]+)"', self._idl)
            if match:
                values.add(match.group(1))

        print(values)

        if "IF" and "THEN" in self._idl:
            matches = re.findall(r'IF\s(.*?)\sTHEN\s(.*?)$', self._idl)
            condition = matches[0][0]
            result = matches[0][1]
            condition_template = self.transfer_base_idl(condition, param_names)
            result_template = self.transfer_base_idl(result, param_names)
            template = f"({condition_template} => {result_template})"
        else:
            template = self.transfer_base_idl(self._idl, param_names)
        print(template)
        constraint = Constraint(template, param_names, values, ents)
        self._operation.constraints.append(constraint)

    def transfer_base_idl(self, idl_str: str, param_names):
        template = None
        if "OR" in idl_str:
            matches = re.findall(r'(.*?)\s+OR\s+(.*?)$', idl_str)
            condition1 = matches[0][0]
            condition2 = matches[0][1]
            condition1_template = self.transfer_base_idl(condition1, param_names)
            condition2_template = self.transfer_base_idl(condition2, param_names)
            template = f"({condition1_template}) || ({condition2_template})"
        if "AND" in idl_str:
            matches = re.findall(r'(.*?)\s+AND\s+(.*?)$', idl_str)
            condition1 = matches[0][0]
            condition2 = matches[0][1]
            condition1_template = self.transfer_base_idl(condition1, param_names)
            condition2_template = self.transfer_base_idl(condition2, param_names)
            template = f"({condition1_template}) && ({condition2_template})"
        if "==" or "!=" in idl_str:
            pass
        if "Or" in idl_str:
            template = "(\"(AA != 'None') => (BB = 'None')\", \"(BB = 'None') => (AA != 'None')\", \"(BB != 'None') => (AA = 'None')\", \"(AA = 'None') => (BB != 'None')\")"
        elif "AllOrNone" in self._idl:
            templates = []
            for i in range(len(param_names)):
                chars = [chr(n + 65) for n in range(len(param_names))]
                letter = chr(i + 65)
                remaining_chars = [c for c in chars if c != letter]
                condition1 = f"({letter}{letter} = 'None')"
                result1 = "&&".join([f"{c}{c} = 'None'" for c in remaining_chars])
                condition2 = f"({letter}{letter} != 'None')"
                result2 = "&&".join([f"{c}{c} != 'None'" for c in remaining_chars])
                templates.append(f"\"{condition1} => ({result1})\"")
                templates.append(f"\"({result1}) => {condition1}\"")
                templates.append(f"\"{condition2} => ({result2})\"")
                templates.append(f"\"({result2}) => {condition2}\"")
            template = f"({','.join(templates)})"
        elif "OnlyOne" in self._idl:
            templates = []
            for i in range(len(param_names)):
                chars = [chr(n + 65) for n in range(len(param_names))]
                letter = chr(i + 65)
                remaining_chars = [c for c in chars if c != letter]
                condition = f"({letter}{letter} != 'None')"
                result = "&&".join([f"{c}{c} = 'None'" for c in remaining_chars])
                templates.append(f"\"{condition} => ({result})\"")
                templates.append(f"\"({result}) => {condition}\"")
            template = f"({','.join(templates)})"
        elif "ZeroOrOne" in self._idl:
            templates = []
            for i in range(len(param_names)):
                chars = [chr(n + 65) for n in range(len(param_names))]
                letter = chr(i + 65)
                remaining_chars = [c for c in chars if c != letter]
                condition = f"({letter}{letter} != 'None')"
                result = "&&".join([f"{c}{c} = 'None'" for c in remaining_chars])
                templates.append(f"\"{condition} => ({result})\"")
            template = f"({','.join(templates)})"
        else:
            template = None

        return template
