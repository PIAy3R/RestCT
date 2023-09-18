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

swagger = "D:/Python_Codes/RestCT/exp/swagger/BingMap/Elevations.json"
os.environ["swagger"] = swagger
os.environ["model"] = "gpt-3.5-turbo"
os.environ["language_model_key"] = "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"

p = Parser(logger)
p.parse()
op = p.operations[1]
with Path(swagger).open("r") as fp:
    spec = json.load(fp)
print(spec.get("paths").get(op.url.replace(URL.baseurl, "")).get(op.method.value).get("parameters"))
print(op.url.replace(URL.baseurl, ""))
# ep = [p for p in op.parameterList if not isinstance(p, EnumParam)]
# r = RuntimeInfoManager()
# m = ParamValueModel(op, ep, r)
# a = m.execute()
# t = r.get_llm_examples().get(op)
# print(t)
