import spacy
from spacy.tokens import Token, Doc, Span
from spacy.language import Language
from spacy.matcher import PhraseMatcher
from typing import Tuple, List, Dict, Any


@Language.factory("restct_param")
class RestctParamComponent:
    def __init__(self, nlp, name, op_id: str, param_names: Dict[str, str]):
        """
        @param op_id: operation identifier
        @param param_names: {name: global_name}
        """
        self.nlp = nlp
        self.name = "PARAMETER"

        # custom information to match
        self._op_id = op_id
        self._param_names = param_names

        # init matcher
        self.matcher = PhraseMatcher(nlp.vocab)
        self.matcher.add(self.name, [nlp.make_doc(p) for p in self._param_names])

        # set extension attributes
        Span.set_extension("op_id", default=None)
        if not Span.has_extension("prefix_string"):
            Span.set_extension("prefix_string", default=None)
        if not Span.has_extension("suffix_string"):
            Span.set_extension("suffix_string", default=None)
        if not Span.has_extension("global_name"):
            Span.set_extension("global_name", default=None)

        Doc.set_extension("count_parameters", getter=self.count_parameters)
        Doc.set_extension("get_parameters", getter=self.get_parameters)

    def __call__(self, doc: Doc) -> Doc:
        matches = self.matcher(doc)
        spans = []
        for _, start, end in matches:
            entity = Span(doc, start, end, label=self.name)
            entity._.op_id = self._op_id
            name = doc[start:end].text
            entity._.global_name = self._param_names[name]
            entity._.prefix_string = doc[:start].text
            entity._.suffix_string = doc[end:].text
            spans.append(entity)
        doc.ents = list(doc.ents) + spans
        return doc

    def count_parameters(self, doc: Doc) -> int:
        return len([e for e in doc.ents if e.label_ == self.name])

    def get_parameters(self, doc: Doc) -> list:
        return [ent for ent in doc.ents if ent.label_ == "PARAMETER"]


@Language.factory("restct_value")
class RestctValueComponent:
    def __init__(self, nlp, name, op_id: str, param_names: Dict[str, str], available_values: Dict[str, tuple]):
        """
        @param op_id: operation identifier
        @param available_values: {global_name: (v1,...)}
        """
        self.nlp = nlp
        self.name = "VALUE"

        # custom information to match
        self._op_id = op_id
        self._param_names = param_names
        self._available_values = available_values

        # init matcher
        self.matcher = PhraseMatcher(nlp.vocab)
        # make list[list] to list
        self.matcher.add(self.name, [nlp.make_doc(v) for t in self._available_values.values() for v in t])

        # set extension attributes
        Span.set_extension("value", default=None)
        if not Span.has_extension("prefix_string"):
            Span.set_extension("prefix_string", default=None)
        if not Span.has_extension("suffix_string"):
            Span.set_extension("suffix_string", default=None)
        if not Span.has_extension("global_name"):
            Span.set_extension("global_name", default=None)

        Doc.set_extension("count_values", getter=self.count_values)
        Doc.set_extension("get_values", getter=self.get_values)

    def __call__(self, doc: Doc) -> Doc:
        matches = self.matcher(doc)
        spans = []
        for _, start, end in matches:
            entity = Span(doc, start, end, label=self.name)
            value_token = doc[start:end][0]
            value_ancestor_list = [a.i for a in list(value_token.ancestors)]
            entity._.value = value
            entity._.prefix_string = doc[:start].text
            entity._.suffix_string = doc[end:].text

            # handle no parameter
            if doc._.count_parameters == 0:
                candidate_parameters = []
                for gn, vt in self._available_values.items():
                    if any([entity.text == str(v) for v in vt]):
                        candidate_parameters.append(gn)
                if len(candidate_parameters) == 1:
                    entity._.global_name = candidate_parameters[0]
                    spans.append(entity)
                elif len(candidate_parameters) > 1:
                    raise IndexError("more than one parameter can take this value")

            if doc._.count_parameters == 1:
                param_ent = doc._.get_parameters[0]
                param_token = doc[param_ent.start:param_ent.end][0]
                param_ancestor_list = [a.i for a in list(param_token.ancestors)]
                if param_ancestor_list == value_ancestor_list:
                    entity._.global_name = self._param_names[param_ent.text]
                spans.append(entity)

            # handle multiple params and values
            if doc._.count_parameters > 1:
                for param_ent in doc._.get_parameters:
                    param_token = doc[param_ent.start:param_ent.end][0]
                    param_ancestor_list = [a.i for a in list(param_token.ancestors)]
                    if param_ancestor_list == value_ancestor_list:
                        entity._.global_name = self._param_names[param_ent.text]
                spans.append(entity)

        doc.ents = list(doc.ents) + spans
        return doc

    def count_values(self, doc: Doc) -> int:
        return len([e for e in doc.ents if e.label_ == self.name])

    def get_values(self, doc: Doc) -> list:
        return [ent for ent in doc.ents if ent.label_ == "VALUE"]


if __name__ == "__main__":
    nlp = spacy.load("en_core_web_sm")

    param_names_dict = {"param1": "1param1", "param2": "1param2"}
    value = {"1param1": tuple(["www"]), "1param2": tuple(["wer"])}

    nlp.add_pipe("restct_param", None, config={"op_id": "test", "param_names": param_names_dict})
    nlp.add_pipe("restct_value", None,
                 config={"op_id": "test", "param_names": param_names_dict, "available_values": value})

    # 处理文本，生成 Doc 对象
    text1 = "This is an example text with param1 and param2."
    text2 = "param1 is www"
    doc = nlp(text2)

    # 访问文档级别的自定义属性
    param_count = doc._.count_parameters
    value_count = doc._.count_values
    print(f"Number of parameters: {param_count}")
    print(f"Number of values: {value_count}")

    # 遍历文档中的实体，打印参数信息
    for ent in doc.ents:
        if ent.label_ == "PARAMETER":
            print(
                f"Parameter: {ent.text}, Global Name: {ent._.global_name}, Prefix: {ent._.prefix_string}, Suffix: {ent._.suffix_string}")
        if ent.label_ == "VALUE":
            print(f"Value: {ent.text}, Global Name: {ent._.global_name}, Prefix: {ent._.prefix_string}, Suffix: {ent._.suffix_string}")