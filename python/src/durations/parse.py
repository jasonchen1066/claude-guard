import re

_UNIT_SECONDS = {"d": 86_400, "h": 3_600, "m": 60, "s": 1}
_PART = re.compile(r"(\d+)([dhms])")


class DurationError(ValueError):
    pass


def parse_duration(text: str) -> int:
    if not text:
        msg = "empty duration"
        raise DurationError(msg)

    total = 0
    pos = 0
    last_rank = -1
    for match in _PART.finditer(text):
        if match.start() != pos:
            msg = f"invalid duration {text!r}"
            raise DurationError(msg)
        value, unit = match.groups()
        rank = list(_UNIT_SECONDS).index(unit)
        if rank <= last_rank:
            msg = f"units out of order or repeated in {text!r}"
            raise DurationError(msg)
        last_rank = rank
        total += int(value) * _UNIT_SECONDS[unit]
        pos = match.end()

    if pos != len(text):
        msg = f"invalid duration {text!r}"
        raise DurationError(msg)
    return total
