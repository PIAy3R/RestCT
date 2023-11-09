from enum import Enum, unique

from src.parameter.meta import AbstractParam
from src.parameter.numberic import IntegerParam


@unique
class TimeFormat(Enum):
    ISO_LOCAL_TIME_FORMAT = "{:0>2d}:{:0>2d}:{:0>2d}",
    TIME_WITH_MILLISECONDS = "{:0>2d}:{:0>2d}:{:0>2d}.000Z"


class Time(AbstractParam):
    def __init__(self, name):
        super().__init__(name)

        self._sec = IntegerParam("sec", 0, 60, False, True)
        self._min = IntegerParam("min", 0, 60, False, True)
        self._hour = IntegerParam("hour", 0, 24, False, True)

        self.format: TimeFormat = TimeFormat.TIME_WITH_MILLISECONDS

    @property
    def value(self):
        return self.format.format(self._hour.value, self._min.value, self._sec.value)


@unique
class DateFormat(Enum):
    ISO_LOCAL_DATE_FORMAT = "{:0>4d}-{:0>2d}-{:0>2d}"


class Date(AbstractParam):
    def __init__(self, name):
        super(Date, self).__init__(name)

        self._year = IntegerParam("year", 1900, 2100, False, True)
        self._month = IntegerParam("month", 1, 12, False, True)
        self._day = IntegerParam("day", 1, 31, False, True)

        self.format: DateFormat = DateFormat.ISO_LOCAL_DATE_FORMAT

    @property
    def value(self):
        return self.format.format(self._year.value, self._month.value, self._day.value)


@unique
class DateTimeFormat(Enum):
    ISO_LOCAL_DATE_TIME_FORMAT = "{date}T{time}",
    DEFAULT_DATE_TIME = "{date} {time}"


class DateTime(AbstractParam):
    def __init__(self, name):
        super(DateTime, self).__init__(name)

        self._date = Date("date")
        self._time = Time("time")

        self.format: DateTimeFormat = DateTimeFormat.DEFAULT_DATE_TIME

    @property
    def value(self):
        return self.format.format(self._date.value, self._time.value)
