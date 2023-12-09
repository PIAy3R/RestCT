import abc
import copy
from enum import Enum
from typing import List, Tuple, Optional
from urllib.parse import quote

from src.factor import AbstractFactor, ArrayFactor, ObjectFactor
from src.nlp import word_similarity


class RestParam(metaclass=abc.ABCMeta):
    def __init__(self, factor: AbstractFactor):
        self.factor: AbstractFactor = factor

    def __deepcopy__(self, memo):
        return self.__class__(factor=copy.deepcopy(self.factor, memo))


class QueryParam(RestParam):
    pass
    # todo: encode query string


class ContentType(Enum):
    JSON = 'application/json'
    JSON_TEXT = 'text/json'
    JSON_ANY = 'application/*+json'
    XML = 'application/xml'
    FORM = 'application/x-www-form-urlencoded'
    MULTIPART_FORM = 'multipart/form-data'
    PLAIN_TEXT = 'text/plain'
    HTML = 'text/html'
    PDF = 'application/pdf'
    PNG = 'image/png'
    BINARY = 'application/octet-stream'
    ANY = '*/*'

    @classmethod
    def of(cls, s: str):
        if s.startswith('application/json'):
            return cls.JSON
        elif s.startswith('text/json'):
            return cls.JSON_TEXT
        elif s.startswith('application/*+json'):
            return cls.JSON_ANY
        elif s.startswith('application/xml'):
            return cls.XML
        elif s.startswith('application/x-www-form-urlencoded'):
            return cls.FORM
        elif s.startswith('multipart/form-data'):
            return cls.MULTIPART_FORM
        elif s.startswith('text/plain'):
            return cls.PLAIN_TEXT
        elif s.startswith('text/html'):
            return cls.HTML
        elif s.startswith('application/pdf'):
            return cls.PDF
        elif s.startswith('image/png'):
            return cls.PNG
        elif s.startswith('application/octet-stream'):
            return cls.BINARY
        elif s.startswith('*/*'):
            return cls.ANY
        else:
            raise ValueError(f'Unknown content type: {s}')


class BodyParam(RestParam):
    def __init__(self, factor: AbstractFactor, content_type: str):
        super().__init__(factor)

        self.content_type: ContentType = ContentType.of(content_type)

    def __deepcopy__(self, memo):
        ins = self.__class__(factor=copy.deepcopy(self._factor, memo), content_type=self.content_type.value)
        return ins


class PathParam(RestParam):
    pass


class HeaderParam(RestParam):
    pass


class RestPath:
    class Element:
        def __init__(self, tokens: list):
            self.tokens = tokens

        @property
        def is_parameter(self):
            return any([t.is_parameter for t in self.tokens])

        def __repr__(self):
            return "".join([t.__repr__() for t in self.tokens])

        def __str__(self):
            return self.__repr__()

        def __hash__(self):
            return hash(self.__repr__())

        def __eq__(self, other):
            if not isinstance(other, RestPath.Element):
                return False

            return all([t == other.tokens[i] for i, t in enumerate(self.tokens)])

    class Token:
        def __init__(self, name: str, is_parameter: bool):
            self.name = name
            self.is_parameter = is_parameter

        def __repr__(self):
            return "{" + self.name + "}" if self.is_parameter else self.name

        def __str__(self):
            return self.__repr__()

        def __eq__(self, other):
            if not isinstance(other, RestPath.Token):
                return False

            return self.name == other.name and self.is_parameter == self.is_parameter

    @staticmethod
    def _extract_element(s):
        tokens = []
        _next = 0
        while _next < len(s):
            current = _next
            if s[_next] == '{':
                closing = s.find("}", current)
                if closing < 0:
                    raise ValueError("Opening { but missing closing } in: " + s)
                _next = closing + 1

                tokens.append(RestPath.Token(s[current + 1:_next - 1], True))
            else:
                _next = s.find("{", current)
                _next = len(s) if _next < 0 else _next
                tokens.append(RestPath.Token(s[current:_next], False))
        return RestPath.Element(tokens)

    def __init__(self, path: str):
        if "?" in path or "#" in path:
            raise ValueError("The path contains invalid characters. "
                             "Are you sure you didn't pass a full URI?\n" + path)

        self.elements = [self._extract_element(element) for element in path.split("/") if element != ""]

        self.computed_to_string = "/" + "/".join(
            ["".join([str(t).replace("[\\[\\],]", "") for t in e.tokens]) for e in self.elements])

    def resolve(self, param: List[RestParam]):
        path = self.resolve_path_param(param)
        query = self.resolve_query_param(param)
        if len(query) > 0:
            path = path + "?" + "&".join(query)
        return path

    def resolve_path_param(self, path_params: List[RestParam]) -> str:
        path = ""

        for e in self.elements:
            path += "/"

            for t in e.tokens:
                if not t.is_parameter:
                    path += t.name
                else:
                    p = next((p for p in path_params if isinstance(p, PathParam) and p.factor.name == t.name), None)

                    if p is None:
                        raise ValueError(f"Cannot resolve path parameter '{t.name}'")

                    value = p.factor.value

                    if not value.strip():
                        """
                        We should avoid having path params that are blank,
                        as they would easily lead to useless 404/405 errors

                        TODO handle this case better, eg avoid having blank in
                        the first place
                        """
                        value = "1"

                    path += value

        """
        Reserved characters need to be encoded.
        https://tools.ietf.org/html/rfc3986#section-2.2

        Why not using URI also for the Query part???
        It seems unclear how to properly build it as a single string...
        """
        return path

    @staticmethod
    def resolve_query_param(params: List[RestParam]) -> List[str]:
        usable_query_params = filter(lambda p: isinstance(p, QueryParam) and p.factor.is_active, params)

        def encode(value):
            return quote(value, safe='-')

        def get_query_string(param: RestParam):
            name = encode(param.factor.name)

            if isinstance(param.factor, ArrayFactor):
                elements: Tuple[AbstractFactor] = param.factor.get_leaves()
                return "&".join(f"{name}={encode(e.printable_value)}" for e in elements if e.is_active)
            else:
                value = encode(param.factor.printable_value)
                return f"{name}={value}"

        return [get_query_string(q) for q in usable_query_params]

    def is_ancestor_of(self, other):
        if len(self.elements) > len(other.elements):
            return False
        return all([e == other.elements[i] for i, e in enumerate(self.elements)])

    def is_directly_parent_of(self, other):
        if len(self.elements) + 1 != len(other.elements):
            return False
        return all([e == other.elements[i] for i, e in enumerate(self.elements)])

    def __repr__(self):
        return f"{self.computed_to_string}"

    def __eq__(self, other):
        if not isinstance(other, RestPath):
            return False

        return self.computed_to_string == other.computed_to_string


class Method(Enum):
    POST = "post"
    GET = "get"
    DELETE = "delete"
    PUT = "put"

    @classmethod
    def of(cls, text: str):
        text_lower = text.lower()
        for member in cls.__members__.values():
            if member.value.lower() == text_lower:
                return member
        else:
            raise ValueError(f"Unknown method: {text}")


class RestOp:
    def __init__(self, host: str, path: str, verb: str):
        self._host = host
        self.path = RestPath(path)
        self.verb = Method.of(verb)
        self.description: Optional[str] = None

        # self.constraints: List[Constraint] = []
        self.parameters: List[RestParam] = []

        self.responses: List[RestResponse] = []

    def __repr__(self):
        return f"{self.verb.value}:{self.path}"

    def __str__(self):
        return f"{self.verb.value}:{self.path}"

    def __hash__(self):
        return hash(self.__repr__())

    def __eq__(self, other):
        if not isinstance(other, RestOp):
            return False

        return self.verb == other.verb and self.path == other.path


class RestResponse:
    def __init__(self, status_code: Optional[int] = None, description: Optional[str] = None):
        self.status_code: Optional[int] = status_code
        self.description: Optional[str] = description

        # 目前支持一个content
        self.contents: List[Tuple[str, AbstractFactor]] = []

    def add_content(self, content: AbstractFactor, content_type: str):
        self.contents.append((content_type, content))

    def match_binding(self, name: str) -> Tuple[bool, Optional[AbstractFactor]]:
        """
        :param name:
        :return:
        """
        similarity = 0
        matched: Optional[AbstractFactor] = None
        for _, c in self.contents:
            if isinstance(c, ArrayFactor):
                c = c.item

            if isinstance(c, ObjectFactor):
                for p in c.properties:
                    s = word_similarity(name, p.name)
                    if s > similarity:
                        similarity = s
                        matched = p
                    if similarity == 1:
                        return True, matched
        if similarity < 0.5:
            return False, None
        return True, matched

    def __repr__(self):
        return f"{self.status_code}:{self.description}"