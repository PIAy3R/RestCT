from src.factor import AbstractFactor
from src.factor.equivalence import Empty, FixedLength, VariableLength


class StringFactor(AbstractFactor):

    def __init__(self, name: str, min_length=1, max_length=100):
        super().__init__(name)

        self.min_length = min_length if min_length > 0 else 1
        self.max_length = max_length if max_length > 0 else 100

    def init_equivalences(self):
        super().init_equivalences()

        # 初始化等价关系
        self.equivalences.append(Empty())
        self.equivalences.append(FixedLength(self.min_length))
        self.equivalences.append(FixedLength(self.max_length))

        if self.max_length - self.min_length > 1:
            self.equivalences.append(VariableLength(self.min_length, self.max_length))

    def __deepcopy__(self, memo):
        ins = super().__deepcopy__(memo)
        ins.min_length = self.min_length
        ins.max_length = self.max_length
        return ins


class BinaryFactor(StringFactor):
    pass
