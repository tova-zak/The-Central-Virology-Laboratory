"""Deterministic received-date assessment. Never modifies the extracted (raw) value.
Accepted: DD/MM/YYYY, DD.MM.YYYY, DD-MM-YYYY (same separator twice, 1-2 digit day/month) and YYYY-MM-DD.
Normalised form: DD/MM/YYYY.
Two-digit year policy (explicitly requested for this project): YY is read as TWO_DIGIT_YEAR_CENTURY + YY
(26 -> 2026, 24 -> 2024). The century is an INFERENCE: such dates return status "century_inferred" with
century_inferred=True and must be confirmed by a human. 26 is never silently read as 1926. Explicit four-digit
years (including 19xx) are preserved as written and carry no inference flag.
Future-date policy is unchanged: a date after today is an error ("future"). A two-digit year that lands in the
future (e.g. 99 -> 2099) is therefore rejected as future; it is never remapped to the past.
"""
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
_SEPARATED = re.compile(r"^(\d{1,2})([./-])(\d{1,2})\2(\d{4}|\d{2})$")
_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_MIN_YEAR = 1900
TWO_DIGIT_YEAR_CENTURY = 2000  # single place that defines how a two-digit year YY is read: 2000 + YY
@dataclass(frozen=True)
class DateAssessment:
    status: str  # ok | century_inferred | future | invalid_date | unrecognized | empty
    normalized: Optional[str] = None  # DD/MM/YYYY (also set for "future"); None when the date is unusable
    candidates: tuple = ()  # kept for backward compatibility; no longer produced
    reason: str = ""
    century_inferred: bool = False  # True when the source showed only two digits and the century was inferred
def _now() -> datetime:
    return datetime.now()
def _real_date(day: int, month: int, year: int) -> bool:
    try:
        datetime(year, month, day)
        return True
    except ValueError:
        return False
def _four_digit(day: int, month: int, year: int, today: datetime, inferred: bool = False) -> DateAssessment:
    if year < _MIN_YEAR or not _real_date(day, month, year):
        return DateAssessment("invalid_date", reason="not a real calendar date")
    normalized = "%02d/%02d/%04d" % (day, month, year)
    if datetime(year, month, day) > today:
        return DateAssessment("future", normalized, reason="date is in the future", century_inferred=inferred)
    if inferred:
        return DateAssessment("century_inferred", normalized, reason="two-digit year read as %d + YY" % TWO_DIGIT_YEAR_CENTURY, century_inferred=True)
    return DateAssessment("ok", normalized)
def assess_date(value, today: Optional[datetime] = None) -> DateAssessment:
    today = today or _now()
    text = "" if value is None else str(value).strip()
    if not text:
        return DateAssessment("empty", reason="Date is empty")
    iso = _ISO.match(text)
    if iso:
        year, month, day = (int(group) for group in iso.groups())
        return _four_digit(day, month, year, today)
    match = _SEPARATED.match(text)
    if not match:
        return DateAssessment("unrecognized", reason="unsupported date format")
    day, month, year_text = int(match.group(1)), int(match.group(3)), match.group(4)
    if len(year_text) == 4:
        return _four_digit(day, month, int(year_text), today)
    return _four_digit(day, month, TWO_DIGIT_YEAR_CENTURY + int(year_text), today, inferred=True)
