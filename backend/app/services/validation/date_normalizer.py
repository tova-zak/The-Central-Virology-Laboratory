"""Deterministic received-date assessment. Never guesses a century and never modifies the extracted (raw) value.

Accepted: DD/MM/YYYY, DD.MM.YYYY, DD-MM-YYYY (same separator twice, 1-2 digit day/month) and YYYY-MM-DD.
Normalised form: DD/MM/YYYY. Two-digit years are recognised but NOT resolved: status "ambiguous_year" with the
plausible full dates offered only as review hints.
"""
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

_SEPARATED = re.compile(r"^(\d{1,2})([./-])(\d{1,2})\2(\d{4}|\d{2})$")
_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_MIN_YEAR = 1900


@dataclass(frozen=True)
class DateAssessment:
    status: str  # ok | future | ambiguous_year | invalid_date | unrecognized | empty
    normalized: Optional[str] = None  # DD/MM/YYYY (also set for "future"); None when the year is ambiguous or unusable
    candidates: tuple = ()  # review hints for ambiguous_year only; never applied automatically
    reason: str = ""


def _real_date(day: int, month: int, year: int) -> bool:
    try:
        datetime(year, month, day)
        return True
    except ValueError:
        return False


def _four_digit(day: int, month: int, year: int, today: datetime) -> DateAssessment:
    if year < _MIN_YEAR or not _real_date(day, month, year):
        return DateAssessment("invalid_date", reason="not a real calendar date")
    normalized = "%02d/%02d/%04d" % (day, month, year)
    if datetime(year, month, day) > today:
        return DateAssessment("future", normalized, reason="date is in the future")
    return DateAssessment("ok", normalized)


def assess_date(value, today: Optional[datetime] = None) -> DateAssessment:
    today = today or datetime.now()
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
    short = int(year_text)
    possible = [year for year in (2000 + short, 1900 + short) if _real_date(day, month, year)]
    if not possible:
        return DateAssessment("invalid_date", reason="not a real calendar date in any century")
    hints = tuple("%02d/%02d/%04d" % (day, month, year) for year in possible if datetime(year, month, day) <= today)
    return DateAssessment("ambiguous_year", None, hints, "two-digit year: century is not assumed")
