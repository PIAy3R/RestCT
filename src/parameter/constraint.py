from typing import List

from src.parameter.meta import AbstractParam


class Constraint:
    def __init__(self):
        # A list of parameters that are involved in the constraint
        self._involved_params: List[AbstractParam] = []
        # A textual description of the constraint
        self.descriptive_text: str = ""

        # constraint导入计算过程，比如acts覆盖表生成，主要使用两种方式:
        # 1. acts约束公式形式
        self._pattern: str = ""
        # 2. 禁止元组
        self._forbidden_tuples = []
