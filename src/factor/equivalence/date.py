from datetime import datetime, timedelta
from random import randint

from src.factor.equivalence import AbstractEquivalence


class DateTimeBetween(AbstractEquivalence):
    def __init__(self, begin: datetime, end: datetime):
        self.begin = begin
        self.end = end

    def check(self, value: datetime) -> bool:
        return self.begin <= value <= self.end

    def generate(self) -> datetime:
        """generate a datetime between begin and end"""
        # 计算时间差
        time_difference = self.end - self.begin

        # 生成随机的时间差
        random_time_delta = timedelta(seconds=randint(0, int(time_difference.total_seconds())))

        # 计算随机时间
        return self.begin + random_time_delta
