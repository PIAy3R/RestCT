from typing import List, Optional, Union

from src.factor.meta import AbstractFactor


class ObjectFactor(AbstractFactor):
    def __init__(self, name):
        super(ObjectFactor, self).__init__(name)

        self._properties: List[AbstractFactor] = []
        self._additional_properties: List[AbstractFactor] = []

    def init_equivalence(self):
        for p in self._properties:
            p.init_equivalence()

        for p in self._additional_properties:
            p.init_equivalence()

    def set_required_property(self, p: AbstractFactor):
        self._properties.append(p)
        p.parent = self

    def set_optional_property(self, p: AbstractFactor):
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

    def _spilt_example(self, example) -> Union[list, None]:
        if example is None:
            return None
        if isinstance(example, list):
            for e in example:
                if not isinstance(e, dict):
                    return None
                self._spilt_example(e)
            return None
        elif isinstance(example, dict):
            for p_name, p_example in example.items():
                target_p_list = [p for p in self._properties if p.name == p_name]
                if len(target_p_list) == 0:
                    continue
                target_p = target_p_list[0]
                target_p.set_example(p_example)
            return None
        else:
            raise ValueError("ObjectFactor's example must be list or dict")


class ArrayFactor(AbstractFactor):
    def __init__(self, name, min_items: int = 1, max_items: int = 1, unique_items: bool = False):
        super(ArrayFactor, self).__init__(name)

        self._min_items: int = min_items
        self._max_items: int = max_items
        self._unique_items: bool = unique_items

        self._item: Optional[AbstractFactor] = None

    def init_equivalence(self):
        self._item.init_equivalence()

    def set_item(self, item_param: AbstractFactor):
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

    def _spilt_example(self, example) -> Union[list, None]:
        if example is None:
            return None
        if isinstance(example, list):
            for e in example:
                self._item.set_example(e)
            return None
        else:
            raise ValueError("ArrayFactor's example must be a list")
