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

    SYS_ROLE_RESPONSE = "You are a helpful assistant, helping handle the issues related to RESTful APIs. RESTful API " \
                        "is an API style that uses URLs to locate resources and access operation resources. After " \
                        "accessing resources, the server of RESTful API usually returns a response, including status " \
                        "code and content. The status code is used to inform the user whether the operation is " \
                        "successful and the corresponding situation. The content usually has further instructions. " \
                        "When executed successfully, it may returns resource-related information. When execution " \
                        "fails, it may contains error specific information. Now you are an expert related to " \
                        "RESTful API and help analyze the content of the response the server send back."

    EXPLANATION_VALUE = """
Sentence Request is the method and base url of a RESTful API request, and its description of the function.
Parameter info is a list contains python dicts, records the corresponding operation's parameter information of the request. A dict corresponds to a parameter, recording the information of the parameter.
Sentence Constraint records the constraint relationships that may not documented in the Parameter info. If empty, there is no constraint.
The Parameter list is a list where the parameters are a part of the parameters in the Parameter Info, and you need to provide example values for these parameters.
    """

    EXPLANATION_RESPONSE = """
The main content to be analyzed consists of four parts.
1.Sentence Request is the method and base url of a RESTful API request.
2.The Parameter list is a list contains the parameters of the request. Some of these parameters may appear in the response content
3.Content is a set that contains all unique responses, and all responses are server responses of different test cases 
corresponding to the Sentence Request.
4.Error Cause Classification is a description, because when the test case corresponding to the requests fails to 
execute, the response of the server may contain the cause of the error. Error Cause Classification briefly classifies 
these errors.
    """

    TEXT_VALUE = """
Request:```{}```
Parameter info:```{}```
Constraint:```{}```
Parameter list:```{}```
    """

    TEXT_RESPONSE = """
Request:```{}```
Parameter List:```{}```
Content:```{}```
Error Cause Classification:```{}```
     """

    PARAMETER = "Parameter info:```{}```\n"

    CODE_GENERATION = """
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
    FIND_PARAM = """
- According to the information provided in Content, analyze which parameters in the Parameter list have problems that 
cause the test case to fail to execute. Note that the parameter names in the response and the parameter names in the 
Parameter List may not be exactly the same, and there will be format changes. Format your response as a JSON object. 
The format is {params:[p1,p2,....]}
    """
    CLASSIFY = """
- Classify the error reason of each parameter. Format your response as a JSON object. 
The format is {p1:r, p2:r, .....}. Reason is expressed using numerical labels
    """


class URL:
    baseurl = ""
