from src.parameter.meta import AbstractParam, AbstractValueGenerator


# Abstract class for numeric parameters
class AbstractNumericParam(AbstractParam):
    # Initialize the parent class
    def __init__(self, name, exclusive_min_value, exclusive_max_value):
        super().__init__(name)

        # Set the exclusive min and max values
        self.exclusive_min_value = exclusive_min_value
        self.exclusive_max_value = exclusive_max_value

    def flat_view(self) -> tuple:
        pass


# Integer parameter class
class IntegerParam(AbstractNumericParam):
    # Initialize the parent class
    def __init__(self, name, min_value, max_value, exclusive_min_value=True, exclusive_max_value=True):
        super().__init__(name, exclusive_min_value, exclusive_max_value)
        # Set the min and max values
        self.min_value = min_value
        self.max_value = max_value


# Float parameter class
class FloatParam(AbstractNumericParam):
    # Initialize the parent class
    def __init__(self, name, min_value, max_value, exclusive_min_value=True, exclusive_max_value=True,
                 precision=2):
        super().__init__(name, exclusive_min_value, exclusive_max_value)
        # Set the min and max values
        self.min_value = min_value
        self.max_value = max_value

        # Set the precision
        self.precision = precision


# Double parameter class
class DoubleParam(AbstractNumericParam):
    # Initialize the parent class
    def __init__(self, name, min_value, max_value, exclusive_min_value=True, exclusive_max_value=True,
                 precision=8):
        super().__init__(name, exclusive_min_value, exclusive_max_value)
        # Set the min and max values
        self.min_value = min_value
        self.max_value = max_value

        # Set the precision
        self.precision = precision


class BetweenGenerator(AbstractValueGenerator):
    def __init__(self, min_value, max_value, exclusive_min, exclusive_max):
        super().__init__()
        self.min_value = min_value
        self.max_value = max_value
        self.exclusive_min = exclusive_min
        self.exclusive_max = exclusive_max
