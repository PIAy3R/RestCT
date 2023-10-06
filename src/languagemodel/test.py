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

swagger = "D:/Python_Codes/RestCT/exp/swagger/BingMap/Route.json"
os.environ["swagger"] = swagger
os.environ["model"] = "gpt-3.5-turbo"
os.environ["language_model_key"] = "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"

p = Parser(logger)
p.parse()
op = p.operations[0]
ep = [p for p in op.parameterList if not isinstance(p, EnumParam)]
r = RuntimeInfoManager()
m = BodyParamModel(op, ep, r, "D:/TestData")
pt = m.build_prompt()
print(pt)
a = m.execute()
print()
t = r.get_llm_examples().get(op)
print(t)

