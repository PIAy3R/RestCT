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
    BODY_EXPLANATION = """There is a body parameter, it contains other parameters, the following description will give 
        the information of the body parameter. 
        Body parameter info: {}\n"""
    FAKER = "Your are a helpful assisent, helping to handle some problem about RESTful APIs." \
            "When testing a RESTful API, tools always select parameters and assign them. When assigning a value to a " \
            "parameter, it is usually necessary to take a random value. The parameter name and description may imply " \
            "that the parameter may have some value format. However, it is usually difficult for testing tools to " \
            "process this information about natural language and give corresponding responses. Obtain random values " \
            "that meet the requirements, and obtaining random values requires a large number of targeted methods, " \
            "which makes it difficult to obtain values in testing." \
            "The Faker library in Python can solve the problem of random values. It can give some random values that " \
            "are close to reality. It has a variety of methods to generate different types of random values." \
            "But how to select the corresponding faker library based on the parameter information is a difficult " \
            "point, so I will give the relevant information about the parameters and the name of the callable " \
            "function of the faker library. Please give us the function and parameters of the faker library function " \
            "that you know. Find out which method of the library should be called with the corresponding parameter to " \
            "generate a random value. Assume that the variable name of the instantiated object of the faker class is " \
            "fake. The form of your answer only needs to give a function call such as fake.url().\n" \
            "Callable method list：['aba', 'add_provider', 'address', 'administrative_unit', 'am_pm', " \
            "'android_platform_token', 'ascii_company_email', 'ascii_email', 'ascii_free_email', 'ascii_safe_email', " \
            "'bank_country', 'basic_phone_number', 'bban', 'binary', 'boolean', 'bothify', 'bs', 'building_number', " \
            "'catch_phrase', 'century', 'chrome', 'city', 'city_prefix', 'city_suffix', 'color', 'color_hsl', " \
            "'color_hsv', 'color_name', 'color_rgb', 'color_rgb_float', 'company', 'company_email', 'company_suffix', " \
            "'coordinate', 'country', 'country_calling_code', 'country_code', 'credit_card_expire', " \
            "'credit_card_full', 'credit_card_number', 'credit_card_provider', 'credit_card_security_code', " \
            "'cryptocurrency', 'cryptocurrency_code', 'cryptocurrency_name', 'csv', 'currency', 'currency_code', " \
            "'currency_name', 'currency_symbol', 'current_country', 'current_country_code', 'date', 'date_between', " \
            "'date_between_dates', 'date_object', 'date_of_birth', 'date_this_century', 'date_this_decade', " \
            "'date_this_month', 'date_this_year', 'date_time', 'date_time_ad', 'date_time_between', " \
            "'date_time_between_dates', 'date_time_this_century', 'date_time_this_decade', 'date_time_this_month', " \
            "'date_time_this_year', 'day_of_month', 'day_of_week', 'del_arguments', 'dga', 'domain_name', " \
            "'domain_word', 'dsv', 'ean', 'ean13', 'ean8', 'ein', 'email', 'emoji', 'enum', 'file_extension', " \
            "'file_name', 'file_path', 'firefox', 'first_name', 'first_name_female', 'first_name_male', " \
            "'first_name_nonbinary', 'fixed_width', 'format', 'free_email', 'free_email_domain', 'future_date', " \
            "'future_datetime', 'get_arguments', 'get_formatter', 'get_providers', 'hex_color', 'hexify', 'hostname', " \
            "'http_method', 'iana_id', 'iban', 'image', 'image_url', 'internet_explorer', 'invalid_ssn', " \
            "'ios_platform_token', 'ipv4', 'ipv4_network_class', 'ipv4_private', 'ipv4_public', 'ipv6', 'isbn10', " \
            "'isbn13', 'iso8601', 'items', 'itin', 'job', 'json', 'json_bytes', 'language_code', 'language_name', " \
            "'last_name', 'last_name_female', 'last_name_male', 'last_name_nonbinary', 'latitude', 'latlng', " \
            "'lexify', 'license_plate', 'linux_platform_token', 'linux_processor', 'local_latlng', 'locale', " \
            "'localized_ean', 'localized_ean13', 'localized_ean8', 'location_on_land', 'longitude', 'mac_address', " \
            "'mac_platform_token', 'mac_processor', 'md5', 'military_apo', 'military_dpo', 'military_ship', " \
            "'military_state', 'mime_type', 'month', 'month_name', 'msisdn', 'name', 'name_female', 'name_male', " \
            "'name_nonbinary', 'nic_handle', 'nic_handles', 'null_boolean', 'numerify', 'opera', 'paragraph', " \
            "'paragraphs', 'parse', 'passport_dates', 'passport_dob', 'passport_full', 'passport_gender', " \
            "'passport_number', 'passport_owner', 'password', 'past_date', 'past_datetime', 'phone_number', " \
            "'port_number', 'postalcode', 'postalcode_in_state', 'postalcode_plus4', 'postcode', 'postcode_in_state', " \
            "'prefix', 'prefix_female', 'prefix_male', 'prefix_nonbinary', 'pricetag', 'profile', 'provider', 'psv', " \
            "'pybool', 'pydecimal', 'pydict', 'pyfloat', 'pyint', 'pyiterable', 'pylist', 'pyobject', 'pyset', " \
            "'pystr', 'pystr_format', 'pystruct', 'pytimezone', 'pytuple', 'random_choices', 'random_digit', " \
            "'random_digit_above_two', 'random_digit_not_null', 'random_digit_not_null_or_empty', " \
            "'random_digit_or_empty', 'random_element', 'random_elements', 'random_int', 'random_letter', " \
            "'random_letters', 'random_lowercase_letter', 'random_number', 'random_sample', " \
            "'random_uppercase_letter', 'randomize_nb_elements', 'rgb_color', 'rgb_css_color', 'ripe_id', 'safari', " \
            "'safe_color_name', 'safe_domain_name', 'safe_email', 'safe_hex_color', 'sbn9', 'secondary_address', " \
            "'seed_instance', 'seed_locale', 'sentence', 'sentences', 'set_arguments', 'set_formatter', 'sha1', " \
            "'sha256', 'simple_profile', 'slug', 'ssn', 'state', 'state_abbr', 'street_address', 'street_name', " \
            "'street_suffix', 'suffix', 'suffix_female', 'suffix_male', 'suffix_nonbinary', 'swift', 'swift11', " \
            "'swift8', 'tar', 'text', 'texts', 'time', 'time_delta', 'time_object', 'time_series', 'timezone', 'tld', " \
            "'tsv', 'unix_device', 'unix_partition', 'unix_time', 'upc_a', 'upc_e', 'uri', 'uri_extension', " \
            "'uri_page', 'uri_path', 'url', 'user_agent', 'user_name', 'uuid4', 'vin', 'windows_platform_token', " \
            "'word', 'words', 'xml', 'year', 'zip', 'zipcode', 'zipcode_in_state', 'zipcode_plus4']\n"


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
