import abc


class AbstractValueGenerator(metaclass=abc.ABCMeta):
    def __repr__(self): return f"value generator"

    @abc.abstractmethod
    def random(self): pass

    @abc.abstractmethod
    def has_instance(self, value): pass
