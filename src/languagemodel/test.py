import json
import os
from pathlib import Path

from loguru import logger

from src.Dto.keywords import URL
from src.Dto.parameter import EnumParam
from src.ca import RuntimeInfoManager
from src.languagemodel.LanguageModel import ParamValueModel
from src.openapiParser import Parser

swagger = "/Users/naariah/Documents/Python_Codes/RestCT/exp/swagger/GitLab/Branch.json"
os.environ["swagger"] = swagger
os.environ["model"] = "gpt-3.5-turbo-1106"
os.environ["language_model_key"] = "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"
os.environ["http_proxy"] = "http://localhost:7890"
os.environ["https_proxy"] = "http://localhost:7890"

with Path(swagger).open("r") as fp:
    spec = json.load(fp)

p = Parser(logger)
p.parse()
op = p.operations[1]
ep = [p for p in op.parameterList if not isinstance(p, EnumParam)]
bp = ep[0]
pl = bp.seeAllParameters()
p0 = pl[0].getGlobalName()
definition = spec.get("definitions").copy()
p_l = spec["paths"][op.url.replace(URL.baseurl, "")][op.method.value]["parameters"]
plstr = json.dumps(p_l)
# ref = str()
# for p_i in p_l:
#     if p_i["name"] == bp.name:
#         ref = p_i["schema"].get("$ref").split("/")[-1]
# def_dict = definition[ref]


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


# i = get_info(p0, definition, def_dict, bp)
# print(i)

r = RuntimeInfoManager()
m = ParamValueModel(op, ep, r, "/Users/naariah/Experiment/LLM")
pt = m.build_prompt()
# print(pt)
a = m.execute()
print()
t = r.get_llm_examples().get(op)
print()