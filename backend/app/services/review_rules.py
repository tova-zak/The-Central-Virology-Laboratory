"""Exception-only review: the single source of truth for "does this field need a human?".

Product rule: a field with a valid extracted value and NO validation error, NO extraction warning/uncertainty,
NO pending candidate and NO unresolved conflict is auto-accepted (never labelled "human verified") and must not
block export. Anything else is review-required and carries a precise Hebrew reason.

Works on the persisted dict form of a FieldValue so the API response, the export gate and the saved-records
summary all agree.
"""
import re
import hashlib
import json
from typing import Any, Optional

REVIEW_FIELDS = ("patient_first_name", "patient_last_name", "patient_id_number",
                 "sender", "received_date", "central_numbers", "commitment_number")

# Candidate reasons that are accepted extra numbers, not ambiguity (each becomes its own export row).
ACCEPTED_CANDIDATE_REASONS = frozenset({"multiple_commitments_on_page"})

_LABEL_HE = {
    "patient_first_name": "השם הפרטי",
    "patient_last_name": "שם המשפחה",
    "patient_id_number": "תעודת הזהות",
    "sender": "הגורם השולח",
    "received_date": "תאריך קבלת הדגימה",
    "central_numbers": "המספר המרכזי",
    "commitment_number": "מספר ההתחייבות",
}
_MISSING_HE = {
    "patient_first_name": "השם הפרטי לא זוהה במסמך.",
    "patient_last_name": "שם המשפחה לא זוהה במסמך.",
    "patient_id_number": "מספר תעודת הזהות לא זוהה במסמך.",
    "sender": "הגורם השולח לא זוהה או אינו ברשימה המאושרת.",
    "received_date": "תאריך קבלת הדגימה לא זוהה במסמך.",
    "central_numbers": "לא זוהה מספר מרכזי במסמך.",
    "commitment_number": "לא זוהה מספר התחייבות במסמך.",
}
_WARNING_HE = {
    "patient_first_name": "השם בכתב היד אינו קריא באופן ברור.",
    "patient_last_name": "שם המשפחה בכתב היד אינו קריא באופן ברור.",
    "patient_id_number": "מספר תעודת הזהות אינו קריא או אינו חד-משמעי במסמך.",
    "sender": "הגורם השולח אינו חד-משמעי במסמך.",
    "received_date": "התאריך אינו ברור או אינו חד-משמעי במסמך.",
    "central_numbers": "המספר המרכזי אינו ברור או אינו חד-משמעי במסמך.",
    "commitment_number": "מספר ההתחייבות אינו ברור או אינו חד-משמעי במסמך.",
}
_CANDIDATE_HE = {
    "patient_last_name": "ייתכן ששם מלא הוזן בשדה השם הפרטי — נדרשת בדיקה ידנית.",
    "central_numbers": "זוהו שתי אפשרויות למספר המרכזי — נדרשת בחירה ידנית.",
    "commitment_number": "זוהה מספר נוסף שלא סווג אוטומטית כהתחייבות — נדרשת בחירה ידנית.",
}


def effective_value(field: dict) -> Any:
    """Human correction wins, then normalized, then raw (same order as the export gate)."""
    for key in ("reviewed_value", "normalized_value", "raw_value"):
        if field.get(key) is not None:
            return field[key]
    return None


def is_empty_value(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip()) or value == []


def relationship_review_required(record: dict) -> bool:
    """Both persisted relationship representations must be free of unresolved ambiguity."""
    return (record.get("relation_status") == "ambiguous" or
            record.get("relationship_status") in ("unresolved_relationship", "unknown", "ambiguous"))


def has_blank_item(value: Any) -> bool:
    return isinstance(value, list) and any(not str(v or "").strip() for v in value)


def pending_candidates(field: dict) -> list:
    return [c for c in field.get("candidates") or []
            if c.get("status", "pending") != "rejected" and c.get("reason") not in ACCEPTED_CANDIDATE_REASONS]


def _id_reason(field: dict, issue: dict) -> str:
    message = str(issue.get("message", "")).lower()
    digits = "".join(ch for ch in str(effective_value(field) or "") if ch.isdigit())
    if "non-digit" in message:
        return "תעודת הזהות מכילה תווים שאינם ספרות."
    if "zeros" in message:
        return "מספר תעודת הזהות אינו תקין (כל הספרות אפס)."
    if digits and len(digits) != 9:
        return f"תעודת הזהות מכילה {len(digits)} ספרות במקום 9."
    return "מספר תעודת הזהות אינו עובר בדיקת ספרת ביקורת."


def _date_reason(field: dict, issue: dict) -> str:
    message = str(issue.get("message", "")).lower()
    if issue.get("code") == "century_inferred":
        value = str(effective_value(field) or "")
        year = value[-4:] if len(value) >= 4 and value[-4:].isdigit() else "20YY"
        return f"התאריך כולל שנה דו־ספרתית שהורחבה ל־{year} — נדרש אישור."
    if "future" in message:
        return "התאריך עתידי — יש לתקן או לאשר."
    return "התאריך אינו תקין."


def _issue_reason(name: str, field: dict, issue: dict) -> str:
    if name == "patient_id_number":
        return _id_reason(field, issue)
    if name == "received_date":
        return _date_reason(field, issue)
    if name == "central_numbers":
        return "זוהו מספרים מרכזיים סותרים — נדרשת בחירה ידנית."
    return f"נמצאה בעיית תקינות ב{_LABEL_HE.get(name, 'שדה')}."


def field_review_reasons(name: str, field: Optional[dict]) -> list:
    """Hebrew reasons why this field still needs a human. Empty list == clean (auto-accepted or already resolved).

    A human-verified field (including a confirmed-empty one) is resolved: no reasons.
    """
    field = field or {}
    if field.get("review_state") == "human_verified":
        return []
    reasons: list = []

    def add(text: str) -> None:
        if text not in reasons:
            reasons.append(text)

    value = effective_value(field)
    if is_empty_value(value):
        add(_MISSING_HE.get(name, "הערך חסר."))
    elif has_blank_item(value):
        add(f"{_LABEL_HE.get(name, 'השדה')} כולל ערך ריק.")
    for issue in field.get("validation_issues") or []:
        add(_issue_reason(name, field, issue))
    if pending_candidates(field):
        add(_CANDIDATE_HE.get(name, "זוהו אפשרויות נוספות — נדרשת בחירה ידנית."))
    if field.get("extraction_notes") and not any(i.get("code") == "century_inferred" for i in field.get("validation_issues") or []):
        add(_WARNING_HE.get(name, "זוהתה אזהרת חילוץ בשדה."))
    state = field.get("extraction_state")
    if not reasons and state in ("uncertain", "conflicting", "invalid"):
        add(_WARNING_HE.get(name, "זוהתה אזהרת חילוץ בשדה."))
    if not reasons and field.get("review_state") in ("needs_review", "rejected"):
        add(f"{_LABEL_HE.get(name, 'השדה')} סומן לבדיקה ידנית.")
    return reasons


def field_review_required(name: str, field: Optional[dict]) -> bool:
    return bool(field_review_reasons(name, field))


def is_auto_accepted(name: str, field: Optional[dict]) -> bool:
    """Clean and not touched by a human: valid value, nothing to review."""
    field = field or {}
    return field.get("review_state") != "human_verified" and not field_review_reasons(name, field)


def source_page_of(record: dict) -> Optional[int]:
    """1-based source page: the stored source_page, else parsed ONCE here from form_id "<doc>_page_<0-based index>"."""
    stored = record.get("source_page")
    if isinstance(stored, int) and stored >= 1:
        return stored
    match = re.search(r"_page_(\d+)$", str(record.get("form_id") or ""))
    return int(match.group(1)) + 1 if match else None


def record_review_token(record: dict) -> str:
    """Hash review-relevant data only; derived UI flags and storage timestamps are excluded."""
    field_keys = ("extraction_state", "validation_issues", "extraction_notes", "candidates")
    snapshot = {}
    for name in REVIEW_FIELDS:
        field = record.get(name) or {}
        snapshot[name] = {key: field.get(key) for key in field_keys}
        snapshot[name]["value"] = effective_value(field)
        snapshot[name]["review_reasons"] = field_review_reasons(name, field)
    for key in ("commitment_record_id", "form_id", "source_page", "relationship_status",
                "relation_status", "central_number_refs", "sample_ids", "test_id", "page_warnings", "status"):
        snapshot[key] = record.get(key)
    snapshot["source_page"] = source_page_of(record)
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def final_review_confirmed(record: dict) -> bool:
    return bool(record.get("final_review_confirmed_at") and
                record.get("final_review_fingerprint") == record_review_token(record))


def invalidate_changed_final_review(record: dict) -> None:
    if record.get("final_review_fingerprint") and not final_review_confirmed(record):
        record["final_review_fingerprint"] = None
        record["final_review_confirmed_at"] = None


def annotate_record(record: dict) -> dict:
    """Add derived review_required / review_reasons_he to each field plus record-level flags (in place)."""
    any_required = False
    record_reasons: list = []
    for name in REVIEW_FIELDS:
        field = record.get(name)
        if not isinstance(field, dict):
            continue
        reasons = field_review_reasons(name, field)
        field["review_required"] = bool(reasons)
        field["review_reasons_he"] = reasons
        any_required = any_required or bool(reasons)
    record["relationship_review_required"] = relationship_review_required(record)
    if record["relationship_review_required"]:
        any_required = True
        record_reasons.append("הקשר בין המספרים המרכזיים להתחייבות לא נפתר.")
    record["source_page"] = source_page_of(record)
    record["final_review_token"] = record_review_token(record)
    record["final_review_confirmed"] = final_review_confirmed(record)
    record["review_required"] = any_required
    record["review_reasons_he"] = record_reasons
    return record


def mark_auto_accepted(commitment) -> None:
    """At record creation: clean, still-pending fields of a CommitmentRecord get review_state auto_accepted."""
    from app.domain.models import ReviewState
    for name in REVIEW_FIELDS:
        field = getattr(commitment, name, None)
        if field is None or field.review_state != ReviewState.pending:
            continue
        if not field_review_reasons(name, field.model_dump(mode="json")):
            field.review_state = ReviewState.auto_accepted
