from datetime import datetime, timedelta
from enum import Enum, unique

from src.factor import ComparableFactor
from src.factor.equivalence import DateTimeBetween, TimeBetween, DateBetween, Enumerated


@unique
class TimeFormat(Enum):
    ISO_LOCAL_TIME_FORMAT = "%H:%M:%S",
    TIME_WITH_MILLISECONDS = "%H:%M:%S.%fZ"


class TimeFactor(ComparableFactor):
    def __init__(self, name):
        super().__init__(name)
        self.format: TimeFormat = TimeFormat.TIME_WITH_MILLISECONDS

        # boundary value of time
        self.min = datetime(year=2023, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        self.max = datetime(year=2023, month=1, day=1, hour=23, minute=59, second=59, microsecond=999999)

    def init_equivalences(self):
        super().init_equivalences()
        self.equivalences.append(Enumerated(self.min))
        self.equivalences.append(Enumerated(self.max))
        self.equivalences.append(TimeBetween(self.min, self.max))

    @property
    def printable_value(self):
        return self.value.strftime(self.format)


@unique
class DateFormat(Enum):
    ISO_LOCAL_DATE_FORMAT = "%Y-%m-%d"


class DateFactor(ComparableFactor):
    def __init__(self, name):
        super(DateFactor, self).__init__(name)

        self.format: DateFormat = DateFormat.ISO_LOCAL_DATE_FORMAT
        # boundary value of time
        self.min = datetime(year=1970, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        self.max = datetime.now() + timedelta(days=365 * 100)

    def init_equivalences(self):
        super().init_equivalences()
        self.equivalences.append(Enumerated(self.min))
        self.equivalences.append(Enumerated(self.max))
        self.equivalences.append(DateBetween(self.min, self.max))

    @property
    def printable_value(self):
        return self.value.strftime(self.format)


@unique
class DateTimeFormat(Enum):
    ISO_LOCAL_DATE_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S",
    DEFAULT_DATE_TIME = "%Y-%m-%d %H:%M:%S"


class DateTimeFactor(ComparableFactor):
    def __init__(self, name):
        super(DateTimeFactor, self).__init__(name)

        self.format: DateTimeFormat = DateTimeFormat.DEFAULT_DATE_TIME

        # boundary value of time
        self.min = datetime(year=1970, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        self.max = datetime.now() + timedelta(days=365 * 100)

    def init_equivalences(self):
        super().init_equivalences()
        self.equivalences.append(Enumerated(self.min))
        self.equivalences.append(Enumerated(self.max))
        self.equivalences.append(DateTimeBetween(self.min, self.max))

    @property
    def printable_value(self):
        return self.value.strftime(self.format)
