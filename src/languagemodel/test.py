import json
import os
from pathlib import Path

import tiktoken
from loguru import logger

from src.Dto.keywords import DataType, URL
from src.Dto.operation import Operation
from src.Dto.parameter import ValueType, EnumParam
from src.ca import RuntimeInfoManager
from src.languagemodel.LanguageModel import ParamValueModel, BodyParamModel
from src.openapiParser import Parser

swagger = "D:/Python_Codes/RestCT/exp/swagger/GitLab/Groups.json"
os.environ["swagger"] = swagger
os.environ["model"] = "gpt-3.5-turbo"
os.environ["language_model_key"] = "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"

p = Parser(logger)
p.parse()
op = p.operations[5]
ep = [p for p in op.parameterList if not isinstance(p, EnumParam)]
r = RuntimeInfoManager()
m = BodyParamModel(op, ep, r, "C:/Users/NaaRiAh/Desktop/test/restcttest")
pt = m.build_prompt()
print(pt)
a = m.execute()
print()
t = r.get_llm_examples().get(op)
# print(t)
print()

