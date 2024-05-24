class SystemRole:
    SYS_ROLE_VALUE = """
You are a helpful assistant, helping handle the issues related to RESTful APIs.

Now I will explain the information to be provided.
1. Sentence Request is the method and base url of a RESTful API request, and its description of the function.
2. Parameter info is a list contains python dicts, records the corresponding operation's parameter information of the 
   request. Each dict corresponds to a parameter, recording the information.
3. Sentence Constraint records the constraint relationships of the parameters. 
   If empty, there is no constraint.
4. The Parameter list is a list where the parameters are a part of the parameters in the Parameter Info, and you need 
   to provide example values for these parameters.
"""

    SYS_ROLE_IDL = """
You are a helpful assistant, helping handle the issues related to RESTful APIs.
In RESTful API, there are constraint relationships between several parameters, 
we use IDL(Inter-parameter Dependency Language) to describe constraints.
The IDL syntax is as follows:

Model:
    Dependency*;
Dependency:
    RelationalDependency | ArithmeticDependency |
    ConditionalDependency | PredefinedDependency;
RelationalDependency:
    Param RelationalOperator Param;
ArithmeticDependency:
    Operation RelationalOperator DOUBLE;
Operation:
    Param OperationContinuation |
    '(' Operation ')' OperationContinuation?;
OperationContinuation:
    ArithmeticOperator (Param | Operation);
ConditionalDependency:
    'IF' Predicate 'THEN' Predicate;
Predicate:
    Clause ClauseContinuation?;
Clause:
    (Term | RelationalDependency | ArithmeticDependency
    | PredefinedDependency) | 'NOT'? '(' Predicate ')';
Term:
    'NOT'? (Param | ParamValueRelation);
Param:
    ID | '[' ID ']';
ParamValueRelation:
    Param '==' STRING('|'STRING)* |
    Param 'LIKE' PATTERN_STRING | Param '==' BOOLEAN |
    Param RelationalOperator DOUBLE;
ClauseContinuation:
    ('AND' | 'OR') Predicate;
PredefinedDependency:
    'NOT'? ('Or' | 'OnlyOne' | 'AllOrNone' |
    'ZeroOrOne') '(' Clause (',' Clause)+ ')';
RelationalOperator:
    '<' | '>' | '<=' | '>=' | '==' | '!=';
ArithmeticOperator:
    '+' | '-' | '*' | '/';


Here are the explanation of some basic relations of IDL:

Case1: Or(param_1, param_2)
One of the two parameters is required.

Case2: AllOrNone(param_1, param_2,...,param_n)
All of the parameters or none of them must be present in the API call

Case3: OnlyOne(param_1, param_2,...,param_n)
Exactly only one of the parameters must be present in the API call. If n=2, OnlyOne is same with OR

Case4: ZeroOrOne(param_1, param_2,...,param_n)
At most one of the parameters can be present in the API call.

Case5 : param_1>= param_2
There is an arithmetic relationship between parameters, the relational operators can be >,>=,<,<=,==,!=

Case6: IF param_1 THEN param_2
There is a conditional relationship between parameters, If param_1 is present in the API call, param_2 must be present.

Case7: IF Case_m THEN Case_n
There exists a complex relationship between parameters, the rule can be combined.


I will give you the name and description of the parameters that might have constraints in Info, 
and i will give the name of all parameters in a list, extract constraints from the descriptions, if any.

Note:
1. Not all parameters are in Info are constrained, it’s just that we suspect there may be constraints.
   Check carefully to see if there are any constraints.

 """

    SYS_ROLE_PICT = """
You are a helpful assistant, helping handle the issues related to RESTful APIs. 
In RESTful API, there are constraint relationships between several parameters, 
we use pict syntax to describe constraints:

Constraints   :: =
  Constraint
| Constraint Constraints

Constraint    :: =
  IF Predicate THEN Predicate ELSE Predicate;
| Predicate;

Predicate     :: =
  Clause
| Clause LogicalOperator Predicate

Clause        :: =
  Term
| ( Predicate )
| NOT Predicate

Term          :: =
  ParameterName Relation Value
| ParameterName LIKE PatternString
| ParameterName IN { ValueSet }
| ParameterName Relation ParameterName

ValueSet       :: =
  Value
| Value, ValueSet

LogicalOperator ::=
  AND 
| OR

Relation      :: = 
  = 
| <> 
| >
| >=
| <
| <=

ParameterName ::= [String]

Value         :: =
  "String"
| Number

String        :: = whatever is typically regarded as a string of characters

Number        :: = whatever is typically regarded as a number

PatternString ::= string with embedded special characters (wildcards):
                  * a series of characters of any length (can be zero)
                  ? any one character
                  

I will give you the name and description of the parameters that might have constraints in Info, 
and i will give the name of all parameters in a list, extract constraints from the descriptions, if any.

Note:
1. If a parameter does not need to appear, the value of it is None. 
   If the parameter needs to appear, the value is not None. 
   In conclusion, we use None to indicate whether a parameter is required
2. Ignore possible example values appear in the descriptions. 
3. Not all parameters are in Info are constrained, it’s just that we suspect there may be constraints.
   Check carefully to see if there are any constraints.
"""

    SYS_ROLE_EXTRACTION = """
You are a helpful assistant, helping handle the issues related to RESTful APIs. 

RESTful API is an API style that uses URLs to locate resources and access operation resources. 

After accessing resources, the server of RESTful API usually returns a response, including status code and content.
 
The status code is used to inform the user whether the operation is successful and the corresponding situation. 

The content usually has further instructions. When executed successfully, it may returns resource-related information. 
When execution fails, it may contains error specific information. 

Now you are an expert related to RESTful API and help analyze the content of the response the server send back.

The main content to be analyzed consists of four parts.
1. Request is the method and base url of a RESTful API request.
2. Parameter is a list contains the parameters of the request. 
   Some of these parameters may appear in the response content.
3. Content is a set that contains all unique responses, and all responses are server responses of different test cases
   corresponding to the Request.
"""

    SYS_ROLE_SEQUENCE = """
You are an expert in RESTful API testing and help me solve problems in testing.
In RESTful API, an operation usually consists of a http verb and an url.
HTTP verbs include post, put get, delete, patch, etc. 
For the same URL, post must be executed first and delete must be executed last.
Different URLs may have hierarchical structures, such as /users and /users/name. 
Usually longer URLs often depend on shorter URLs, so the operation of longer URLs often needs to be between 
post and delete of shorter URLs.
There may also be dependencies between some URLs that do not have a hierarchical relationship. 
For example, some operations need to use the data results obtained by another operation.

I will give you a list of REST operations, including the operation name and description of it, 
and you need to sort them in the correct order of execution.
"""

    SYS_ROLE_PATHBINDING = """"
You are a helpful assistant, helping handle the issues related to RESTful APIs. 

In RESTful API, an operation usually consists of a http verb and an url.
HTTP verbs include post, put get, delete, patch, etc. 
For the same URL, post must be executed first and delete must be executed last.
Different URLs may have hierarchical structures, such as /users and /users/name. 
Usually longer URLs often depend on shorter URLs, so the operation of longer URLs often 
needs to be between post and delete of shorter URLs.

In Restful API, there may be dependencies between different operations. 
Especially the path parameter of an operation, its parameter value may come from the server feedback after the previous 
operation was successful.

I will give you the parameter information of the path parameter of the RESTful API operation that you need to handle, 
along with the name of the previous successful operation(arranged in order of execution).    
"""


class INFO:
    EXTRACTION = """
Request:```{}```
Parameter List:```{}```
Content:```{}```
"""

    CONSTRAINT = """
Parameter List: {}
Info: {}    
"""

    VALUE = """
Request:```{}```
Parameter info:```{}```
Constraint:```{}```
Parameter list:```{}```
"""

    SEQUENCE = """
Operation List: {}
"""

    BINDING = """
operation: {}
Parameter info: {}
Previous operation: {}
"""


class Task:
    EXTRACTION = """
Your task:
- Analyse the information in the Content, and extract the parameters that may have constraints.
  Format your response as a JSON object.
  The format is {params: [param1, param2, ...]}.
  If there are no parameters that may have constraints, return an empty list.
  The format is {params: []}.
  Use the parameter name in the Parameter list.
"""

    IDL = """
Your task:
- Give the IDL constraint of the constraint parameters.
  Format your response as a JSON object.
  The format is {constraints: [expression1, expression2, ...]}.
"""

    PICT = """
Your task:
- Give the PICT expression of the constraint parameters.
  Format your response as a JSON object.
  The format is {constraints: [expression1, expression2, ...]}.
"""

    VALUE = """
Your task:
- According to the Parameter info, give 3 possible values for each parameter in Parameter list. 
  Note getting example values from description, the example value of one parameter may appear 
  in other parameters' descriptions.
  Format your response as a JSON object.
  The format is {parameter1:[value1,value2,...],parameter2:[value1,value2,...],...}.
"""

    SEQUENCE = """
Your task:
- Based on the rules and the given operations, give one sequence of operations that can execute correctly.
  Note that just use the operations given in Operation List.
  Format your response as a JSON object.
  The format is {sequence: [operation1, operation2, ...]}.
"""

    BINDING = """
Your task: 
According to the name of previous operation and the information of the path parameter, 
infer the results of which operations the values of these parameters may depend on.
Answer at most three likely operations.
Format you answer as a JSON object.
The format is {param1:[operation1, operation2, operation3], param2:[operation1, operation2, operation3], ...}.
Possibly higher operations are placed first.
"""
