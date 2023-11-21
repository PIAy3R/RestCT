from datetime import datetime
from enum import Enum, unique

from src.parameter.meta import ComparableParam


@unique
class TimeFormat(Enum):
    ISO_LOCAL_TIME_FORMAT = "%H:%M:%S",
    TIME_WITH_MILLISECONDS = "%H:%M:%S.%fZ"


class Time(ComparableParam):
    def __init__(self, name):
        super().__init__(name)
        self.format: TimeFormat = TimeFormat.TIME_WITH_MILLISECONDS

    @property
    def now(self):
        return datetime.now()

    @property
    def printable_value(self):
        return self._value.strftime(self.format)


@unique
class DateFormat(Enum):
    ISO_LOCAL_DATE_FORMAT = "%Y-%m-%d"


class Date(ComparableParam):
    def __init__(self, name):
        super(Date, self).__init__(name)

        self.format: DateFormat = DateFormat.ISO_LOCAL_DATE_FORMAT

    @property
    def printable_value(self):
        return self._value.strftime(self.format)


@unique
class DateTimeFormat(Enum):
    ISO_LOCAL_DATE_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S",
    DEFAULT_DATE_TIME = "%Y-%m-%d %H:%M:%S"


class DateTime(ComparableParam):
    def __init__(self, name):
        super(DateTime, self).__init__(name)

        self.format: DateTimeFormat = DateTimeFormat.DEFAULT_DATE_TIME

    @property
    def printable_value(self):
        return self._value.strftime(self.format)
