"""Commitment-number classification with label normalisation. Candidates are preserved, never auto-selected.

A number is accepted only when its (normalised) label is a commitment/request label, or a sample label for Leumit.
Everything else is returned as a CANDIDATE with its source label and the reason, so a human can decide.
"""
import re
from dataclasses import dataclass, field

_NIKUD = re.compile(r"[\u0591-\u05c7]")
COMMITMENT = "\u05d4\u05ea\u05d7\u05d9\u05d9\u05d1\u05d5\u05ea"
REQUEST = "\u05d3\u05e8\u05d9\u05e9\u05d4"
SAMPLE = "\u05d3\u05d2\u05d9\u05de\u05d4"
LEUMIT = "\u05dc\u05d0\u05d5\u05de\u05d9\u05ea"
_HE_THE = "\u05d4"
_FORMS = {
    COMMITMENT: {COMMITMENT, "\u05d4\u05ea\u05d7\u05d9\u05d1\u05d5\u05ea", "\u05d4\u05ea\u05d7\u05d9\u05d9\u05d1\u05d5\u05d9\u05d5\u05ea", "commitment", "commitments"},
    REQUEST: {REQUEST, "\u05d3\u05e8\u05d9\u05e9\u05ea", "\u05d3\u05e8\u05d9\u05e9\u05d5\u05ea"},
    SAMPLE: {SAMPLE, "\u05d3\u05d2\u05d9\u05de\u05ea", "\u05d3\u05d2\u05d9\u05de\u05d5\u05ea"},
}
LABEL_LIMIT = 60


def _tokens(label) -> list:
    text = _NIKUD.sub("", str(label))
    text = re.sub(r"[^\w\s]|_", " ", text)  # quotes, colons, geresh, hyphens, slashes become separators
    return text.lower().split()


def _category(token: str):
    for category, forms in _FORMS.items():
        if token in forms or (token.startswith(_HE_THE) and token[1:] in forms):
            return category
    return None


def normalize_commitment_label(label):
    """Return (canonical_label_or_None, status) with status in none | unrecognized | ambiguous | recognized."""
    if label is None or not str(label).strip():
        return None, "none"
    categories = {c for c in (_category(t) for t in _tokens(label)) if c}
    if not categories:
        return None, "unrecognized"
    if categories <= {COMMITMENT, REQUEST}:
        return (COMMITMENT if COMMITMENT in categories else REQUEST), "recognized"
    if categories == {SAMPLE}:
        return SAMPLE, "recognized"
    return None, "ambiguous"


@dataclass
class CommitmentClassification:
    accepted: list = field(default_factory=list)
    candidates: list = field(default_factory=list)  # {"value", "source_label", "reason"}
    warnings: list = field(default_factory=list)


def classify_commitments(commitment_numbers, commitment_types, central_numbers, sender) -> CommitmentClassification:
    sender = sender or ""
    is_leumit = LEUMIT in sender or "leumit" in sender.lower()
    central = set(central_numbers or [])
    result = CommitmentClassification()

    def candidate(number, label, reason):
        entry = {"value": str(number), "source_label": None if label is None else str(label)[:LABEL_LIMIT], "reason": reason}
        if entry not in result.candidates:
            result.candidates.append(entry)

    def accept(number):
        if number not in result.accepted:
            result.accepted.append(number)

    numbers = list(commitment_numbers or [])
    if not commitment_types:
        # Old format (no labels): only overlaps with central numbers are excluded.
        excluded = [n for n in numbers if n in central]
        for number in numbers:
            if number in central:
                candidate(number, None, "overlaps_central_number")
            else:
                accept(number)
        if excluded:
            result.warnings.append("commitment_numbers: %s also appear in central_numbers, excluded" % (excluded,))
        return result

    labels = {item.get("number"): item.get("label") for item in commitment_types if isinstance(item, dict)}
    for number in numbers:
        label = labels.get(number)
        if number in central:
            result.warnings.append("commitment_numbers: \x27%s\x27 also appears in central_numbers, excluded" % number)
            candidate(number, label, "overlaps_central_number")
            continue
        canonical, status = normalize_commitment_label(label)
        if canonical in (COMMITMENT, REQUEST):
            accept(number)
        elif canonical == SAMPLE:
            if is_leumit:
                accept(number)
            else:
                result.warnings.append("commitment_numbers: \x27%s\x27 labeled \x27%s\x27 but sender is not Leumit, excluded" % (number, SAMPLE))
                candidate(number, label, "sample_label_requires_leumit")
        elif status == "ambiguous":
            result.warnings.append("commitment_numbers: \x27%s\x27 has an ambiguous label, kept as a candidate for review" % number)
            candidate(number, label, "ambiguous_label")
        else:
            result.warnings.append("commitment_numbers: \x27%s\x27 has no recognized label, excluded (likely test number)" % number)
            candidate(number, label, "no_recognized_label")
    return result
