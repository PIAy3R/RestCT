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
ep = [p for p in op.parameterList if not isinstance(p, EnumParam)]
r = RuntimeInfoManager()
m = ParamValueModel(op, ep, r, "C:/Users/NaaRiAh/Desktop/test/restcttest")
p = m.build_prompt()
# print(p)
a = m.execute()
print()
# t = r.get_llm_examples().get(op)
# print(t)
