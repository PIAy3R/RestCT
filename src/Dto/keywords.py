from enum import Enum


class DocKey:
    # 文档
    REF_SIGN = "$ref"
    ALL_OF = "allOf"
    ONE_OF = "oneOf"
    ANY_OF = "anyOf"
    ADDITIONAL_PROPERTIES = "additionalProperties"

    SCHEMES = "schemes"
    BASEPATH = "basePath"
    DEFINITIONS = "definitions"
    PATHS = "paths"
    HOST = "host"
    PROTOCOL = "protocol"
    PARAMS = "parameters"
    RESPONSES = "responses"
    PROPERTIES = "properties"
    EXAMPLE = "example"


class ParamKey:
    # 参数
    NAME = "name"
    TYPE = "type"
    FORMAT = "format"
    ENUM = "enum"
    DEFAULT = "default"
    DESCRIPTION = "description"
    REQUIRED = "required"
    MAXITEMS = "maxItems"
    MINITEMS = "minItems"
    UNIQUEITEMS = "uniqueItems"
    MAXIMUM = "maximum"
    MINIMUM = "minimum"
    EXCLUSIVEMAXIMUM = "exclusiveMaximum"
    EXCLUSIVEMINIMUM = "exclusiveMinimum"
    MULTIPLEOF = "multipleOf"
    MAXLENGTH = "maxLength"
    MINLENGTH = "minLength"

    ITEMS = "items"
    LOCATION = "in"

    SCHEMA = "schema"


class DataType(Enum):
    # 数字
    Integer = "integer"
    Number = "number"
    Int32 = "int32"
    Int64 = "int64"
    Float = "float"
    Double = "double"
    Long = "long"
    # 字符串
    String = "string"
    Byte = "byte"
    Binary = "binary"
    Date = "date"
    DateTime = "datetime"
    Password = "password"
    # 布尔
    Bool = "boolean"
    # 文件
    File = "file"
    UUID = "uuid"
    # 复杂类型
    Array = "array"
    Object = "object"

    NULL = "NONE"

    @staticmethod
    def from_string(value, value_type):
        try:
            if value_type in [DataType.Integer, DataType.Int32, DataType.Int64, DataType.Long]:
                value = int(value)
            elif value_type in [DataType.Float, DataType.Double, DataType.Number]:
                value = float(value)
            elif value_type in [DataType.String]:
                value = str(value)
            elif value_type in [DataType.Byte]:
                value = bytes(value)
            elif value_type in [DataType.Bool]:
                if str(value).lower() == "true":
                    value = True
                else:
                    value = False
        except (ValueError, TypeError):
            return value
        return value


class Loc(Enum):
    FormData = "formData"
    Body = "body"
    Query = "query"
    Path = "path"
    Header = "header"

    NULL = "NONE"


class Method(Enum):
    POST = "post"
    GET = "get"
    DELETE = "delete"
    PUT = "put"


class Tasks:
    COMBINATION = "combination"
    SPECIAL_VALUE = "value"
    BODY = "body"


class Template:
    SYS_ROLE = "You are a helpful assistant, helping check the constraint relationship in RESTful APIs and give " \
               "some combination and specific value for parameters.\n"
    EXPLANATION = """
Sentence Request is the method and base url of a RESTful API request, and its description of the function.
Parameter info is a list contains python dicts, records the corresponding operation's parameter information of the request. A dict corresponds to a parameter, recording the information of the parameter.
Sentence Constraint records the constraint relationships that may not documented in the Parameter info. If empty, there is no constraint.
The Parameter list is a list where the parameters are a part of the parameters in the Parameter Info, and you need to provide example values for these parameters.
    """
    TEXT = """
Request:```{}```
Parameter info:```{}```
Constraint:```{}```
Parameter list:```{}```
    """
    PARAMETER = "Parameter info:```{}```\n"
    # BODY_EXPLANATION = """There is a body parameter, it contains other parameters, the following description will give
    #     the information of the body parameter.
    #     Body parameter info: {}\n"""
    CODEGENERATION = """
import unittest
import requests
class APITestCase(unittest.TestCase):
    def test_send_request(self):
        #This is a test case for a RESTful API
        #The base url is {}
        #The url of the api is {}
        #The http method of this request is {}
        #The content type of this request is {}
        #This request contians {} parameters.
        {}
        {}
    """

    CODEGEN_PARAM = """
        #The parameter {} is a {} parameter, its location is {}, its description is {}, it is required: {}.
    """


class TaskTemplate:
    SPECIAL_VALUE = "- According to the Parameter info, give 3 possible values for each parameter in Parameter list. " \
                    "Format your response as a JSON object.\n" \
        # "The format is {parameter1:[value1,value2,...],parameter2:[value1,value2,...],...}.\n"
    COMBINATION = "- According to the Parameter info and Constraint, give 3 possible valid combinations of " \
                  "parameters in Parameter list and their specific value. " \
                  "Format your response as a JSON object.\n" \
                  "The format is {combination1:{parameter1:value,parameter2:value,...}, combination2,...}."
    ALL_VALUE = "- According to the Parameter info, give 3 possible values for each parameter in Parameter list of " \
                "each request. Format your response as a JSON object. The format is " \
                "{request1:{parameter1:[value1,value2,...],parameter2:[value1,value2,...],...},request2,...}\n"
    BODY = "- According to the Body parameter info, give 1 possible value for each parameter in Body parameter. " \
           "Format your response as a JSON object. "
    FAKER = "Your task:\n" \
            "- Give the right methods in the callable method list of faker to generate random value for parameter " \
            "info(A parameter can use more than one methods). Take the description field into account, " \
            "it may indicate the format of the data. Format your answer as a JSON object. The format is like {" \
            "parameter1: method_name, parameter2: [method_name, method_name], .....} "


class URL:
    baseurl = ""
