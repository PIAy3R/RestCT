class Tasks:
    # COMBINATION = "combination"
    SPECIAL_VALUE = "value"
    BODY = "body"
    PARAMETER = "parameter"
    CONSTRAINT = "constraint"


class Template:
    SYS_ROLE_VALUE = """
You are a helpful assistant, helping check the constraint relationship in RESTful APIs and give some combination and 
specific value for parameters.
"""

    SYS_ROLE_RESPONSE = """
You are a helpful assistant, helping handle the issues related to RESTful APIs. 
RESTful API is an API style that uses URLs to locate resources and access operation resources. 
After accessing resources, the server of RESTful API usually returns a response, including status code and content. 
The status code is used to inform the user whether the operation is successful and the corresponding situation. 
The content usually has further instructions. When executed successfully, it may returns resource-related information. 
When execution fails, it may contains error specific information. 
Now you are an expert related to RESTful API and help analyze the content of the response the server send back.
"""

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
Error Cause Classification:
1. The parameter is assigned the wrong value, which may be a format error or a semantic error.
2. The constraints that need to be satisfied are broken between parameters of the Request.
"""

    TEXT_RES_VALUE = """
Now you are given the information about the parameters in Parameter info.It is a list contains python dicts, each dict 
corresponds to a parameter, recording the information of the parameter.
Parameter info:```{}```
Ask Parameter list:```{}```
Constraint:```{}```
"""

    TEXT_RES_RESPONSE = """
"""

    OTHER = """
3. This operation may depend on a previous operation, and the parameter value may be related to the result of the previous operation.
"""


class TaskTemplate:
    SPECIAL_VALUE = """
Your task:
- According to the Parameter info, give 3 possible values for each parameter in Parameter list. 
Format your response as a JSON object.
The format is {parameter1:[value1,value2,...],parameter2:[value1,value2,...],...}.
"""

    EXTRACT_PARAM = """
Your task:
- According to the information provided in Content, causes of errors are described in Error Cause Classification, 
analyze which parameters in the Parameter list have problems that 
cause the test case to fail to execute. Note that the parameter names in the response and the parameter names in the 
Parameter List may not be exactly the same, and there will be format changes. Format your response as a JSON object. 
The format is {params:[p1,p2,....]}.
If there is no parameter extracted, please return an empty list. The format is {params:[]}
"""

    CLASSIFY = """
Your task:
- Classify the error reason of each parameter. Format your response as a JSON object. 
The format is {p1:r, p2:r, .....}. Reason is expressed using numerical labels, now there are only two reasons.
Due to the provision of multiple test cases, the reasons for errors caused by the same parameter in different test cases 
are not the same. If multiple reasons occur, please classify them all.
"""

    GROUP = """
Your task:
- Group the parameters with constraint relationships, that is, the parameters with reason 2 in the classification are then subdivided.
Format your response as a JSON object. 
The format is {constraint1:[param1,param2,..], constraint:[param1,param2,....], .....}.     
"""

    CORNER_CASE = """
Your task:
- According to the Parameter info, infer and give one most possible error value for each parameter in Parameter list 
which can trigger the bugs. Format your response as a JSON object.
The format is {parameter1:[value1,value2,...],parameter2:[value1,value2,...],...}.
"""

    RES_VALUE = """
Your task:
- According to the constraints above and the information in Parameter info, give 3 possible values for each parameter 
in Ask Parameter list. 
Format your response as a JSON object.
The format is {parameter1:[value1,value2,...],parameter2:[value1,value2,...],...}. 
Pay attention to the constraints between parameters, especially when some parameters take a value, another parameter 
cannot take a value, or when some parameters take a value, the other parameter must take a certain value, etc.
Pay attention to the constraint relationship when giving the value. If there is a constraint relationship between p1 
and p2, the value of the corresponding position must comply with the constraint relationship.
"""

    ALL = """
Your task:
1. According to the information provided in Content, causes of errors are described in Error Cause Classification, 
analyze which parameters in the Parameter list have problems that  cause the test case to fail to execute. 
Note that the parameter names in the response and the parameter names in the Parameter List may not be exactly the 
same, and there will be format changes. 
Format your response as a JSON object. The format is {params:[p1,p2,....]}. 
If there is no parameter extracted, please return an empty list. The format is {params:[]}'}

2. Group the parameters with constraint relationships.Format your response as a JSON object. 
The format is {constraint1:[param1,param2,..], constraint:[param1,param2,....], .....}.


Finish the 2 tasks step by step because the results of the previous step may be useful for the next step. 
Don't return the results of your thinking, just return the json result.
If there is no result for a task, None is returned and all subsequent tasks return None.
The format is {Task1:result, Task2:result}
"""
