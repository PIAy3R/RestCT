from typing import List

from src.parameter.meta import AbstractParam


class ObjectParam(AbstractParam):
    def __init__(self, name):
        super(ObjectParam, self).__init__(name)

        self._properties: List[AbstractParam] = []
        self._additional_properties: List[AbstractParam] = []

    def init_equivalence(self):
        for p in self._properties:
            p.init_equivalence()

        for p in self._additional_properties:
            p.init_equivalence()

    def flat_view(self) -> tuple:
        result = [self, ]
        for p in self._properties:
            result.extend(p.flat_view())
        for p in self._additional_properties:
            result.extend(p.flat_view())
        return tuple(result)

    @property
    def printable_value(self):
        v = {}
        for p in self._properties:
            if p.printable_value == "__null__":
                continue
            v[p.name] = p.printable_value
        for p in self._additional_properties:
            if p.printable_value == "__null__":
                continue
            v[p.name] = p.printable_value
        if len(v.keys()) == 0:
            return "__null__"
        else:
            return v


class ArrayParam(AbstractParam):
    def __init__(self, name):
        super(ArrayParam, self).__init__(name)

        # 目前只设置一个item
        self._item: AbstractParam = None

    def init_equivalence(self):
        self._item.init_equivalence()

    def flat_view(self) -> tuple:
        return self, self._item

    @property
    def printable_value(self):
        if self._item.printable_value == "__null__":
            return "__null__"
        else:
            return [self._item.printable_value, ]
