import json
import os
from pathlib import Path

import tiktoken
from loguru import logger

from src.Dto.keywords import DataType, URL
from src.Dto.operation import Operation
from src.Dto.parameter import ValueType, EnumParam
from src.ca import RuntimeInfoManager
from src.languagemodel.LanguageModel import ParamValueModel
from src.openapiParser import Parser

swagger = "D:/Python_Codes/RestCT/exp/swagger/BingMap/Route.json"
os.environ["swagger"] = swagger
os.environ["model"] = "gpt-3.5-turbo"
os.environ["language_model_key"] = "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"

with Path(swagger).open("r") as fp:
    spec = json.load(fp)

p = Parser(logger)
p.parse()
op = p.operations[6]
ep = [p for p in op.parameterList if not isinstance(p, EnumParam)]
bp = ep[0]
pl = bp.seeAllParameters()
p0 = pl[0].getGlobalName()
print(p0)
definition = spec.get("definitions").copy()
p_l = spec["paths"][op.url.replace(URL.baseurl, "")][op.method.value]["parameters"]
ref = str()
for p_i in p_l:
    if p_i["name"] == bp.name:
        ref = p_i["schema"].get("$ref").split("/")[-1]
def_dict = definition[ref]


def get_info(param, definition, def_dict, body):
    for p_n in param.split("@"):
        if p_n == body.name:
            continue
        elif p_n == "_item":
            ref = def_dict.get("items").get("$ref").split("/")[-1]
            def_dict = definition.get(ref)
        else:
            info = def_dict.get("properties").get(p_n)
            def_dict = info
    return info


i = get_info(p0, definition, def_dict, bp)
print(i)

r = RuntimeInfoManager()
m = ParamValueModel(op, ep, r, "D:/TestData")
pt = m.build_prompt()
print(pt)
a = m.execute()
print()
t = r.get_llm_examples().get(op)
print(t)
print()
