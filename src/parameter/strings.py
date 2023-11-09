from src.parameter.meta import AbstractParam


class StringParam(AbstractParam):

    def __init__(self, name: str, description: str, min_length=0, max_length=20):
        super().__init__(name, description)

        self.min_length = min_length
        self.max_length = max_length
