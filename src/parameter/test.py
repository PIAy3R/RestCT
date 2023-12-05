import copy
from abc import ABCMeta


class AbstractNumericFactor(metaclass=ABCMeta):

    def __init__(self, value):
        self.value = value

    def __deepcopy__(self, memo):
        print("AbstractNumericFactor __deepcopy__")
        new_instance = self.__class__(value=self.value)
        return new_instance


class IntegerFactor(AbstractNumericFactor):
    def __init__(self, value):
        super().__init__(value)


# 创建一个 IntegerFactor 对象
original_instance = IntegerFactor(value=42)
t1 = AbstractNumericFactor(value=42)

# 使用 deepcopy 进行深复制
copied_instance = copy.deepcopy(original_instance)
c2 = copy.deepcopy(t1)

# 验证类型是否相同
print(type(original_instance))  # <class '__main__.IntegerFactor'>
print(type(copied_instance))
print(type(c2))  # <class '__main__.IntegerFactor'>
