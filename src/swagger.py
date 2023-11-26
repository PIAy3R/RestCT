from urllib.parse import urlparse

from openapi_parser.parser import parse
from openapi_parser.specification import *

from src.parameter import *
from src.rest import *


class ParserV3:
    def __init__(self, swagger_path):
        # 解析swagger文件
        self._swagger: Specification = parse(swagger_path)

        # 可能有多个server，只存一个
        self._server: str = self._get_server()

    def _get_server(self):
        """
        get bash path of url
        """
        server = self._swagger.servers[0]
        parsed = urlparse(server.url)
        if parsed.scheme == 0 or parsed.netloc == 0:
            raise ValueError(f"Invalid URI {server.url}: Scheme and netloc are required.")

        self._server = parsed.geturl()

    def extract(self):
        operations = []
        for path in self._swagger.paths:
            path_parameters = path.parameters

            for operation in path.operations:
                rest_op = RestOp(self._server, path.url, operation.method.name)

                if operation.description is not None and len(operation.description):
                    rest_op.description = operation.description

                # handle with input parameters
                for param in operation.parameters:
                    rest_param = self._extract_param(param)
                    rest_op.parameters.append(rest_param)

                if len(path_parameters) > 0:
                    for param in path_parameters:
                        rest_param = self._extract_param(param)
                        rest_op.parameters.append(rest_param)

                # handle request body
                if operation.request_body is not None:
                    if not len(operation.request_body.content) == 0:
                        rest_op.parameters.append(self._extract_body_param(operation.request_body))

                for r in operation.responses:
                    response = RestResponse(r.code, r.description)
                    if r.content is not None:
                        for c in r.content:
                            content_type = c.type
                            content = ParserV3._extract_factor("response", c.schema)
                            response.add_content(content, content_type)
                    rest_op.responses.append(response)
                operations.append(rest_op)
        return operations

    @staticmethod
    def _extract_body_param(body: RequestBody):
        content = body.content
        if len(content) > 1 or len(content) == 0:
            raise ValueError("no content is provided")

        content = content[0]

        factor: AbstractParam = ParserV3._extract_factor("body", content.schema)
        if body.description is not None and len(body.description) != 0:
            factor.description = body.description

        return BodyParam(factor, content.type.value)

    @staticmethod
    def _extract_param(param: Parameter):
        """
        extract parameter from swagger
        """
        # factor info: AbstractParam
        factor: AbstractParam = ParserV3._extract_factor(param.name, param.schema)

        if param.location is ParameterLocation.QUERY:
            rest_param = QueryParam(factor)
        elif param.location is ParameterLocation.HEADER:
            rest_param = HeaderParam(factor)
        elif param.location is ParameterLocation.PATH:
            rest_param = PathParam(factor)
        else:
            raise ValueError(f"Unsupported parameter location: {param.location}")
        return rest_param

    @staticmethod
    def _extract_factor(name: str, schema: Schema):
        if isinstance(schema, Null):
            raise ValueError(f"Parameter {name} has no schema")
        if len(schema.enum) > 0:
            factor = EnumParam(name, schema.enum)
        elif isinstance(schema, Boolean):
            factor = BoolParam(name)
        elif isinstance(schema, Integer):
            factor = ParserV3._build_integer_factor(name, schema)
        elif isinstance(schema, Number):
            factor = ParserV3._build_number_factor(name, schema)
        elif isinstance(schema, String):
            factor = ParserV3._build_string_factor(name, schema)
        elif isinstance(schema, Array):
            factor = ParserV3._build_array_factor(name, schema)
        elif isinstance(schema, Object):
            factor = ParserV3._build_object_factor(name, schema)
        else:
            raise ValueError(f"{name} -> Unsupported schema: {schema}")

        factor.required = not schema.nullable

        if schema.example is not None:
            factor.set_example(schema.example)
        if schema.default is not None:
            factor.set_default(schema.default)

        return factor

    @staticmethod
    def _build_object_factor(name: str, schema: Object):
        # todo: currently do not handle with anyOf and oneOf
        # todo: 没有见过 max_properties 和 min_properties，暂时不处理
        object_factor = ObjectParam(name)

        for p in schema.properties:
            p_factor = ParserV3._extract_factor(p.name, p.schema)
            if p_factor.name in schema.required:
                object_factor.set_required_property(p_factor)
            else:
                object_factor.set_optional_property(p_factor)

        return object_factor

    @staticmethod
    def _build_array_factor(name: str, schema: Array):
        min_items = schema.min_items if schema.min_items is not None else 1
        array = ArrayParam(name,
                           min_items=min_items,
                           max_items=schema.max_items if schema.max_items is not None else min_items,
                           unique_items=schema.unique_items if schema.unique_items is not None else False)

        if schema.items is None:
            raise ValueError(f"Parameter {name} has no items")
        item_factor = ParserV3._extract_factor("_item", schema.items)
        array.set_item(item_factor)
        return array

    @staticmethod
    def _build_string_factor(name: str, schema: String):
        if schema.pattern is not None:
            # todo: regex factor
            raise ValueError(f"Pattern {schema.pattern} is not supported")
        if schema.format is not None:
            if schema.format is StringFormat.DATE:
                return ParserV3._build_date_factor(name, schema)
            if schema.format is StringFormat.DATETIME:
                return ParserV3._build_datetime_factor(name, schema)
            if schema.format is StringFormat.BINARY:
                return ParserV3._build_binary_factor(name, schema)
            # todo: build factor based on format
            raise ValueError(f"Format {schema.format} is not supported")

        return StringParam(name,
                           min_length=schema.min_length if schema.min_length is not None else 1,
                           max_length=schema.max_length if schema.max_length is not None else 100)

    @staticmethod
    def _build_date_factor(name, schema: String):
        if schema.format is None or schema.format is not StringFormat.DATE:
            raise ValueError(f"Format {schema.format} is not date")

        return Date(name)

    @staticmethod
    def _build_datetime_factor(name, schema: String):
        if schema.format is None or schema.format is not StringFormat.DATETIME:
            raise ValueError(f"Format {schema.format} is not datetime")

        return DateTime(name)

    @staticmethod
    def _build_binary_factor(name, schema: String):
        if schema.format is None or schema.format is not StringFormat.BINARY:
            raise ValueError("fFormat {schema.format} is not binary")

        return BinaryParam(name, 1, 100)

    @staticmethod
    def _set_numerical_boundaries(schema: Union[Number, Integer],
                                  max_inf: Union[int, float],
                                  min_inf: Union[int, float]) \
            -> Tuple[Union[int, float], bool, Union[int, float], bool]:

        if max_inf < min_inf:
            raise ValueError(f"{max_inf} must be greater than {min_inf}")

        if schema.exclusive_maximum is not None:
            maximum = schema.exclusive_maximum
            exclusive_maximum = True
        elif schema.maximum is not None:
            maximum = schema.maximum
            exclusive_maximum = False
        else:
            maximum = max_inf
            exclusive_maximum = True

        if schema.exclusive_minimum is not None:
            minimum = schema.exclusive_minimum
            exclusive_minimum = True
        elif schema.minimum is not None:
            minimum = schema.minimum
            exclusive_minimum = False
        else:
            minimum = min_inf
            exclusive_minimum = True
        return maximum, exclusive_maximum, minimum, exclusive_minimum

    @staticmethod
    def _build_integer_factor(name: str, schema: Integer):
        if schema.format is None:
            max_inf = IntegerParam.INT_32_MAX
            min_inf = IntegerParam.INT_32_MIN
        elif schema.format is IntegerFormat.INT32:
            max_inf = IntegerParam.INT_32_MAX
            min_inf = IntegerParam.INT_32_MIN
        elif schema.format is IntegerFormat.INT64:
            max_inf = IntegerParam.INT_64_MAX
            min_inf = IntegerParam.INT_64_MIN
        else:
            max_inf = IntegerParam.INT_32_MAX
            min_inf = IntegerParam.INT_32_MIN

        maximum, exclusive_maximum, minimum, exclusive_minimum = ParserV3._set_numerical_boundaries(schema, max_inf,
                                                                                                    min_inf)

        factor = IntegerParam(
            name=name,
            min_value=minimum,
            max_value=maximum,
            exclusive_max_value=exclusive_maximum,
            exclusive_min_value=exclusive_minimum
        )

        if schema.multiple_of is not None:
            factor.set_multiple_of(schema.multiple_of)
        return factor

    @staticmethod
    def _build_number_factor(name: str, schema: Number):
        maximum, exclusive_maximum, minimum, exclusive_minimum = \
            ParserV3._set_numerical_boundaries(schema, FloatParam.FLOAT_MAX, FloatParam.FLOAT_MIN)

        factor = FloatParam(
            name=name,
            min_value=minimum,
            max_value=maximum,
            exclusive_max_value=exclusive_maximum,
            exclusive_min_value=exclusive_minimum
        )

        if schema.multiple_of is not None:
            factor.set_multiple_of(schema.multiple_of)
        return factor


if __name__ == '__main__':
    # 初始化ParserV3类
    parser = ParserV3("/Users/lixin/Workplace/Jupyter/work/swaggers/GitLab/Branch.json")
    operations = parser.extract()
    print(operations[0])
