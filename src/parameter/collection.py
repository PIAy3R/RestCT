from typing import List, Optional

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

    def set_required_property(self, p: AbstractParam):
        self._properties.append(p)
        p.parent = self

    def set_optional_property(self, p: AbstractParam):
        self._additional_properties.append(p)
        p.parent = self
        p.required = False

    def get_leaves(self) -> tuple:
        result = []
        for p in self._properties:
            result.extend(p.get_leaves())
        for p in self._additional_properties:
            result.extend(p.get_leaves())
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
    def __init__(self, name, min_items: int = 1, max_items: int = 1, unique_items: bool = False):
        super(ArrayParam, self).__init__(name)

        self._min_items: int = min_items
        self._max_items: int = max_items
        self._unique_items: bool = unique_items

        self._item: Optional[AbstractParam] = None

    def init_equivalence(self):
        self._item.init_equivalence()

    def set_item(self, item_param: AbstractParam):
        self._item = item_param
        item_param.parent = self

    def get_leaves(self) -> tuple:
        return self._item,

    @property
    def printable_value(self):
        if self._item.printable_value == "__null__":
            return "__null__"
        else:
            return [self._item.printable_value, ]
