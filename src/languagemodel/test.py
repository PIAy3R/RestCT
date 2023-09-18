import os

import tiktoken
from loguru import logger

from src.Dto.keywords import DataType
from src.Dto.operation import Operation
from src.Dto.parameter import ValueType, EnumParam
from src.ca import RuntimeInfoManager
from src.languagemodel.model import ParamValueModel
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
m = ParamValueModel(op, ep, r)
a = m.execute()
t = r.get_llm_examples().get(op)
print(t)

# string_to_count = "test the token count"
# encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
# num_tokens = len(encoding.encode(string_to_count))
# logger.info("token nums: {}".format(num_tokens))
