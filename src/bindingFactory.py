"""
initialize factors' equivalences
"""
from typing import List

from src.factor import AbstractFactor
from src.factor.equivalence import AbstractBindings, EqualTo
from src.rest import RestOp, PathParam


class Builder:
    def __init__(self):
        self.op_groups: List[List[RestOp]] = []

    def initialize(self, operations: List[RestOp]):
        sorted_ops = sorted(operations, key=lambda x: len(x.path.elements), reverse=True)
        for op in sorted_ops:
            new_groups = True
            for group in self.op_groups:
                if any([op.path.is_ancestor_of(g_op.path) for g_op in group]):
                    group.append(op)
                    new_groups = False

            if new_groups:
                self.op_groups.append([op, ])

    def build_path_equivalences(self):
        """
        build equivalences for factors of op
        每个group中的operation的path都是结构一样的，例如 /projects, /projects/{id}, /projects/{id}/users...
        1) 找到最长的path，例如 /projects/{id}/users/{uid}, 然后遍历这个path中的每个element
        2）如果element是参数
        2.1） element = uid，则producers=[/projects/{id}/users, /projects/{id}/users/{uid}]
                              consumers = [/projects/{id}/users/{uid}, /projects/{id}/users/{uid}/comments, ...]
        3) 将consumers中每个uid都与producers中的每个response中的uid进行绑定
        todo: path中的uid可能与response中的uid取值不一样？为什么不直接绑定path中的uid
        """
        for group in self.op_groups:
            longest_path = max(group, key=lambda x: len(x.path.elements)).path
            for i, e in enumerate(longest_path.elements):
                if e.is_parameter:
                    producers: List[RestOp] = [op for op in group if len(op.path.elements) in (i, i + 1)]
                    consumers: List[RestOp] = [op for op in group if len(op.path.elements) > i]
                    if len(producers) != 0 and len(consumers) != 0:
                        self._match_parameter_in_response(producers, consumers, i)

    @staticmethod
    def _match_parameter_in_response(producers: List[RestOp], consumers: List[RestOp], element_index: int):
        """
        match factors in the responses based on param name
        """
        for p in producers:
            for response in p.responses:
                if response.status_code is None:
                    if next((c for c in response.contents if "json" in c[0].lower()), None) is None:
                        continue
                elif response.status_code < 200 or response.status_code >= 300:
                    continue
                filtered_contents = list(filter(lambda _: "json" in _[0].lower(), response.contents))
                if len(filtered_contents) == 0:
                    continue
                if len(filtered_contents) > 1:
                    raise ValueError(f"response {response.status_code} has more than one json content")
                _, content = filtered_contents[0]

                words = set()
                matched = False
                # 首先使用自己path中的名字进行尝试匹配
                if p.path.elements[-1].is_parameter:
                    for t in p.path.elements[element_index].tokens:
                        # 一个element只有一个token是参数
                        # todo: 多个参数token是否存在
                        if t.is_parameter:
                            words.add(t.name)
                            matched, matched_binding = response.match_binding(t.name)
                            if matched:
                                for c in consumers:
                                    if c == p:
                                        continue
                                    Builder._add_path_bindings(p, c, matched_binding, element_index)
                                break
                if not matched:
                    for c in consumers:
                        if c == p:
                            continue
                        for t in c.path.elements[element_index].tokens:
                            if t.is_parameter:
                                words.add(t.name)
                                matched, matched_binding = response.match_binding(t.name)
                                if matched:
                                    Builder._add_path_bindings(p, c, matched_binding, element_index)

    @staticmethod
    def _add_path_bindings(x: RestOp, y: RestOp, x_factor: AbstractFactor, path_element_index: int):
        """
        @param x: 产生path参数值的operation，比如 /projects 会产生 id
        @param y: 使用path参数值的operation, 比如 /projects/{id} 使用 id
        @param x_factor: x操作response中对应 id 的参数，y的path参数将与之绑定
        @param path_element_index: y的path参数的索引，用于查找该path参数在这个operation y中的实际参数名
        """
        element = y.path.elements[path_element_index]
        for t in element.tokens:
            if t.is_parameter:
                y_factor = next((f for f in y.parameters if isinstance(f, PathParam) and f.factor.name == t.name), None)
                if y_factor is None:
                    raise ValueError(f"Cannot find parameter '{t.name}' in {y.path}")

                equalTo = EqualTo(x.__str__(), x_factor.name, AbstractBindings.TYPES.INT)
                if equalTo not in y_factor.factor.equivalences:
                    y_factor.factor.equivalences.append(equalTo)


if __name__ == '__main__':
    from swagger import ParserV3

    parser = ParserV3("/Users/lixin/Workplace/Jupyter/work/swaggers/GitLab/Project.json")
    operations = parser.extract()

    builder = Builder()
    builder.initialize(operations)
    builder.build_path_equivalences()
    for i, group in enumerate(builder.op_groups):
        print(f"Group: {i}")
        for op in group:
            print(f"  {op.__str__()}")
            for parameter in op.parameters:
                if isinstance(parameter, PathParam):
                    print(f"    {parameter.factor.name}: {parameter.factor.equivalences}")
