import pytest

from durations import DurationError, parse_duration


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0s", 0),
        ("45s", 45),
        ("2m", 120),
        ("1h30m", 5_400),
        ("1d", 86_400),
        ("1d2h3m4s", 86_400 + 7_200 + 180 + 4),
        ("90m", 5_400),
    ],
)
def test_parses_valid_durations(text: str, expected: int) -> None:
    assert parse_duration(text) == expected


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", r"^empty duration$"),
        ("abc", r"^invalid duration 'abc'$"),
        ("10", "invalid duration"),
        ("1h 30m", "invalid duration"),
        ("x1h", "invalid duration"),
        ("1h30", "invalid duration"),
        ("30m1h", "out of order"),
        ("1h1h", "out of order"),
        ("1y", "invalid duration"),
    ],
)
def test_rejects_invalid_durations(text: str, message: str) -> None:
    with pytest.raises(DurationError, match=message):
        parse_duration(text)


def test_error_is_value_error() -> None:
    assert issubclass(DurationError, ValueError)
