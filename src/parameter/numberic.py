from src.parameter.meta import AbstractParam


class AbstractNumericParam(AbstractParam):
    def __init__(self, name, description):
        super().__init__(name, description)
