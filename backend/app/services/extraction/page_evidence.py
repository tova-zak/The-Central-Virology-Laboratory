"""Attach traceability to a freshly mapped page: per-field notes, review candidates, unmatched page warnings.

Only deterministic, content-preserving handling. Nothing is split, guessed or auto-selected, nothing is logged.
"""
from app.domain.models import ExtractionState, FieldCandidate, ReviewState

NOTE_LIMIT = 300
MAX_NOTES = 5
MAX_PAGE_WARNINGS = 10


def clip(text, limit: int = NOTE_LIMIT) -> str:
    return str(text).replace("\n", " ").strip()[:limit]


def _add_note(field, text) -> None:
    note = clip(text)
    if note and note not in field.extraction_notes and len(field.extraction_notes) < MAX_NOTES:
        field.extraction_notes.append(note)


def _add_candidate(field, value, source_label, reason) -> None:
    candidate = FieldCandidate(value=str(value), source_label=None if source_label is None else clip(source_label, 60), reason=reason)
    if candidate not in field.candidates:
        field.candidates.append(candidate)


def attach_page_evidence(commitment_field, page_fields: dict, fields: dict, warnings) -> list:
    """Mutates the given FieldValues; returns the record-level warnings that matched no field."""
    unmatched = []
    for warning in warnings or []:
        low = str(warning).lower()
        matched = False
        for name, field in page_fields.items():
            if name in low:
                _add_note(field, warning)
                matched = True
        if "commitment" in low:
            _add_note(commitment_field, warning)
            matched = True
        if not matched:
            text = clip(warning)
            if text and text not in unmatched:
                unmatched.append(text)

    types = {item.get("number"): item.get("label") for item in (fields.get("commitment_types") or []) if isinstance(item, dict)}
    accepted = fields.get("commitment_numbers") or []
    if not isinstance(accepted, list):
        accepted = [accepted]
    rejected = [c for c in (fields.get("commitment_candidates") or []) if isinstance(c, dict) and c.get("value")]
    if len(accepted) > 1:
        for number in accepted:
            _add_candidate(commitment_field, number, types.get(number), "multiple_commitments_on_page")
    for entry in rejected:
        _add_candidate(commitment_field, entry["value"], entry.get("source_label"), entry.get("reason") or "not_accepted")
    if not accepted and rejected and commitment_field.extraction_state == ExtractionState.missing:
        commitment_field.extraction_state = ExtractionState.uncertain
        commitment_field.review_state = ReviewState.needs_review
        _add_note(commitment_field, "%d number(s) were not accepted automatically; see candidates" % len(rejected))

    received = page_fields.get("received_date")
    if received is not None and received.raw_value:
        from app.services.validation.date_normalizer import assess_date
        assessment = assess_date(received.raw_value)
        if assessment.century_inferred:
            # 2000+YY policy: the value is set elsewhere and flagged; only a note here, no candidate, no value change.
            _add_note(received, "Two-digit year: century inferred as 20YY; confirm")
    first, last = page_fields.get("patient_first_name"), page_fields.get("patient_last_name")
    if first is not None and last is not None and first.raw_value and not last.raw_value and len(str(first.raw_value).split()) >= 2:
        # Possibly a full name in the first-name field. Hebrew names are ambiguous, so it is NOT split here.
        if first.extraction_state == ExtractionState.found:
            first.extraction_state = ExtractionState.uncertain
        first.review_state = ReviewState.needs_review
        _add_note(first, "Several words with no last name: may be a full name. Not split automatically; confirm manually.")
        _add_candidate(last, first.raw_value, "patient_first_name", "possible_full_name_in_first_name_field")
    return unmatched[:MAX_PAGE_WARNINGS]
