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
            value_ancestor_set = set()
            value_token_list = doc[start:end]
            for value_token in value_token_list:
                for a in list(value_token.ancestors):
                    value_ancestor_set.add(a.i)
                if value_token.i in value_ancestor_set:
                    value_ancestor_set.remove(value_token.i)
            entity._.value = entity.text
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
                param_ancestor_set = set()
                param_token_list = doc[param_ent.start:param_ent.end]
                for param_token in param_token_list:
                    for a in param_token.ancestors:
                        param_ancestor_set.add(a.i)
                        if param_token.i in param_ancestor_set:
                            param_ancestor_set.remove(param_token.i)
                if all(p in value_ancestor_set for p in param_ancestor_set):
                    entity._.global_name = self._param_names[param_ent.text]
                spans.append(entity)

            # handle multiple params and values
            if doc._.count_parameters > 1:
                for param_ent in doc._.get_parameters:
                    param_ancestor_set = set()
                    param_token_list = doc[param_ent.start:param_ent.end]
                    for param_token in param_token_list:
                        for a in param_token.ancestors:
                            param_ancestor_set.add(a.i)
                            if param_token.i in param_ancestor_set:
                                param_ancestor_set.remove(param_token.i)
                    if all(p in value_ancestor_set for p in param_ancestor_set):
                        entity._.global_name = self._param_names[param_ent.text]
                spans.append(entity)

        doc.ents = list(doc.ents) + spans
        return doc

    def count_values(self, doc: Doc) -> int:
        return len([e for e in doc.ents if e.label_ == self.name])

    def get_values(self, doc: Doc) -> list:
        return [ent for ent in doc.ents if ent.label_ == "VALUE"]


def parse_json(response, param_names: Dict[str, str], extra_noun: str = None) -> Dict[str, str]:
    dict_to_return = {}
    if isinstance(response, dict):
        for k, v in response.items():
            if k in param_names:
                dict_to_return.update(parse_json(v, param_names, k))
            elif extra_noun is not None:
                dict_to_return.update(parse_json(v, param_names, extra_noun))
            else:
                dict_to_return.update(parse_json(v, param_names))
    elif isinstance(response, list):
        if len(response) > 0:
            if extra_noun is not None:
                for l in response:
                    dict_to_return.update(parse_json(l, param_names, extra_noun))
            else:
                for l in response:
                    dict_to_return.update(parse_json(l, param_names))
    elif isinstance(response, str):
        dict_to_return.update({extra_noun: response})
    return dict_to_return


def parse_text(nlp, text, extra_noun):
    valid_sentence = []
    doc = nlp(text)
    for sentence in doc.sents:
        missing_subject, missing_object = is_complate(sentence)
        if missing_subject:
            new_text = f"{extra_noun} {text}"
        else:
            new_text = text
        sent_doc = nlp(new_text)
        if len(sent_doc.ents) > 0:
            valid_sentence.append(sent_doc)
    return valid_sentence


def is_complate(sentence):
    missing_subject = True
    missing_object = True
    for token in sentence:
        if token.dep_ == "nsubj" and token.head.dep_ == "ROOT":
            missing_subject = False
        if token.dep_ == "dobj" and token.head.dep_ == "ROOT":
            missing_object = False
    return missing_subject, missing_object


if __name__ == "__main__":
    nlp = spacy.load("en_core_web_sm")

    param_names_dict = {"language": "language", "param1": "param1","param2": "param2"}
    value = {"language": tuple(["en-US", "de-DE", "fr", "auto"]), "param1": tuple(["test1"]), "param2": tuple(["test1"])}

    nlp.add_pipe("restct_param", None, config={"op_id": "test", "param_names": param_names_dict})
    nlp.add_pipe("restct_value", None,
                 config={"op_id": "test", "param_names": param_names_dict, "available_values": value})

    # 处理文本，生成 Doc 对象
    text1 = "A language code like ‘en-US’, ‘de-DE’, ‘fr’ or ‘auto’."
    text2 = "param1 has value test1, and param2 also has value test1"
    doc = nlp(text2)

    # 遍历文档中的实体，打印参数信息
    for ent in doc.ents:
        if ent.label_ == "PARAMETER":
            print(
                f"Parameter: {ent.text}, Global Name: {ent._.global_name}, Prefix: {ent._.prefix_string}, Suffix: {ent._.suffix_string}")
        if ent.label_ == "VALUE":
            print(f"Value: {ent.text}, Global Name: {ent._.global_name}, Prefix: {ent._.prefix_string}, Suffix: {ent._.suffix_string}")
