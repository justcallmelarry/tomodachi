import datetime
import pytz
from typing import List, Tuple, Dict, Union, Optional, Any  # noqa
from calendar import monthrange

cron_attributes = [
    ('minute', (0, 59), {}),
    ('hour', (0, 23), {}),
    ('day', (1, 31), {}),
    ('month', (1, 12), {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}),
    ('isoweekday', (0, 6), {'mon': 1, 'tue': 2, 'wed': 3, 'thu': 4, 'fri': 5, 'sat': 6, 'sun': 0}),
    ('year', (1970, 2099), {})
]  # type: List[Tuple[str, Tuple[int, int], Dict[str, int]]]
crontab_aliases = {
    '@yearly': '0 0 1 1 *',
    '@annually': '0 0 1 1 *',
    '@monthly': '0 0 1 * *',
    '@weekly': '0 0 * * 0',
    '@daily': '0 0 * * *',
    '@hourly': '0 * * * *',
    '@minutely': '* * * * *'
}  # type: Dict[str, str]


def get_next_datetime(crontab_notation: str, now_date: datetime.datetime) -> Optional[datetime.datetime]:
    crontab_notation = crontab_aliases.get(crontab_notation, crontab_notation)
    cron_parts = [c for c in crontab_notation.split() if c.strip()]
    cron_parts += ['*' for _ in range(len(cron_attributes) - len(cron_parts))]

    values = []
    last_day = False
    last_weekday = False
    for i, attr in enumerate(cron_attributes):
        cron_type, cron_range, aliases = attr  # type: str, Tuple, Dict[str, int]
        available_values = []  # type: Union[List[int], set]
        parts = cron_parts[i].lower().split(',')
        for part in parts:
            last = False
            possible_values = [x for x in range(cron_range[0], cron_range[1] + 1)]  # type: List[int]
            if '-' in part:
                a, b = part.split('-')  # type: Union[int, str], Union[int, str]
                if '/' in str(b):
                    b, _ = str(b).split('/')
                if 'l' in str(a)[0]:
                    last = True
                    a = str(a)[1:]
                a = int(aliases.get(str(a), a))
                b = int(aliases.get(str(b), b))
                possible_values = [x for x in possible_values if x >= min(a, b) and x <= max(a, b)]

            if '/' in part:
                a, b = part.split('/')
                try:
                    a = int(aliases.get(a, a))
                    b = int(b)
                    possible_values = [x for x in possible_values if x % b == (a % b)]
                except ValueError:
                    b = int(b)
                    if a in ['*', '?']:
                        possible_values = [x for x in possible_values if x % b == 0]
                    else:
                        a, _ = part.split('-')
                        a = int(aliases.get(str(a), a))
                        possible_values = [x for x in possible_values if x % b == (a % b)]

            try:
                if 'l' == part[0]:
                    last = True
                    part = part[1:]
                a = int(aliases.get(part, part))
                possible_values = [x for x in possible_values if x == a]
            except ValueError:
                pass

            if last and attr[0] == 'day':
                last_day = True
            if last and attr[0] == 'isoweekday':
                last_weekday = True

            if not possible_values:
                raise Exception('Invalid cron notation: invalid values for {}'.format(attr[0]))
            if isinstance(available_values, list):
                available_values += possible_values

        available_values = set(available_values)
        values.append(available_values)

    if min(values[2]) >= 28:
        if not any([monthrange(y, m)[1] >= min(values[2]) for y in values[5] for m in values[3]]):
            raise Exception('Invalid cron notation: days out of scope')

    def calculate_date(next_date: Optional[datetime.datetime], last_day: bool, last_weekday: bool) -> Optional[datetime.datetime]:
        if next_date:
            tz = next_date.tzinfo  # type: Any
            if tz is None:
                tz = pytz.UTC
        else:
            return None
        naive_date = not bool(next_date.tzinfo)

        while True:
            original_date = next_date
            for i, attr in enumerate(cron_attributes):
                if attr[0] == 'isoweekday':
                    continue
                value = getattr(next_date, attr[0])
                possible_values = [v for v in values[i] if v >= value]
                if not possible_values:
                    if attr[0] == 'year':
                        return None
                    next_date = None
                    break
                new_value = min(possible_values)
                try:
                    next_date = tz.localize(datetime.datetime(*[getattr(next_date, dv) if dv != attr[0] else new_value for dv in ['year', 'month', 'day', 'hour', 'minute']]))
                except ValueError:
                    next_date = None
                    break

            if next_date and (next_date.isoweekday() % 7) not in values[4]:
                next_date = None
            if next_date and last_day and next_date.day != monthrange(next_date.year, next_date.month)[1]:
                next_date = None
            if next_date and last_weekday:
                for i in range(next_date.day + 1, monthrange(next_date.year, next_date.month)[1] + 1):
                    if datetime.datetime(next_date.year, next_date.month, i).isoweekday() == next_date.isoweekday():
                        next_date = None
                        break
            if not next_date:
                next_date = original_date
                if next_date:
                    try:
                        next_date = tz.localize(datetime.datetime(next_date.year, next_date.month, next_date.day + 1))
                    except ValueError:
                        try:
                            if next_date:
                                next_date = tz.localize(datetime.datetime(next_date.year, next_date.month + 1, 1))
                        except ValueError:
                            if next_date:
                                next_date = tz.localize(datetime.datetime(next_date.year + 1, 1, 1))
            else:
                break

            if next_date and next_date.year >= 2100:
                return None

        if naive_date and next_date:
            return datetime.datetime(next_date.year, next_date.month, next_date.day, next_date.hour, next_date.minute, next_date.second, next_date.microsecond)
        return next_date

    tz = now_date.tzinfo  # type: Any
    calculated_dates = [calculate_date(tz.localize(d) if tz else d, last_day, last_weekday) for d in [
        now_date if now_date.second == 0 else None,
        datetime.datetime(now_date.year, now_date.month, now_date.day, now_date.hour, now_date.minute + 1) if now_date.minute < 60 - 1 else None,
        datetime.datetime(now_date.year, now_date.month, now_date.day, now_date.hour + 1) if now_date.hour < 24 - 1 else None,
        datetime.datetime(now_date.year, now_date.month, now_date.day + 1) if now_date.day < monthrange(now_date.year, now_date.month)[1] - 1 else None,
        datetime.datetime(now_date.year, now_date.month + 1, 1) if now_date.month < 12 - 1 else None,
        datetime.datetime(now_date.year + 1, 1, 1)
    ] if d]
    if not any(calculated_dates):
        return None
    return min([d for d in calculated_dates if d])
