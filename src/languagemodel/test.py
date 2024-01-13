import json
import os
from pathlib import Path

from loguru import logger

from src.Dto.keywords import URL
from src.Dto.parameter import EnumParam
from src.ca import RuntimeInfoManager
from src.languagemodel.LanguageModel import ParamValueModel, ResponseModel
from src.openapiParser import Parser

swagger = "/Users/naariah/Documents/Python_Codes/RestCT/exp/swagger/GitLab/Branch.json"
os.environ["swagger"] = swagger
os.environ["model"] = "gpt-3.5-turbo-1106"
os.environ["language_model_key"] = "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"
# os.environ["http_proxy"] = "http://localhost:7890"
# os.environ["https_proxy"] = "http://localhost:7890"

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
res = [
    (400, {"message": {"import_url": ["is blocked: Only allowed schemes are http, https, git"], "name": [],
                       "limit_reached": []}}),
    (400, {"error": "name, path are missing, at least one parameter must be provided"}),
    (400, {"error": "avatar is invalid"}),
    (400, {"message": {"namespace": ["is not valid"], "limit_reached": []}}),
    (400, {"message": {"project_feature.merge_requests_access_level": [
        "cannot have higher visibility level than repository access level"], "project_feature.builds_access_level": [
        "cannot have higher visibility level than repository access level"],
        "import_url": ["is blocked: Only allowed schemes are http, https, git"],
        "repository_storage": ["is not included in the list"], "name": [], "limit_reached": []}})
]
pv = ParamValueModel(op, ep, r, "/Users/naariah/Experiment/LLM")
rm = ResponseModel(op, r, "/Users/naariah/Experiment/LLM", res)
pt = pv.build_prompt()
a = rm.execute()
print()
print(r.get_llm_constrainted_params(op))
# print(pt)
# a = pv.execute()
# print()
# t = r.get_llm_examples().get(op)
# print()
