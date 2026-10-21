"""Saved-batch history and search (read-only).

Both endpoints are authenticated (registered with require_access in main.py) and return
lightweight metadata only. Search is a POST so patient identifiers never reach URLs/access logs.

Search approach: the JSONB column cannot be indexed for these nested/normalised fields without a
schema change, so we scan ALL batches server-side in bounded chunks (newest first), keep only the
requested page window in memory, and count every match. Older matches are therefore never hidden;
the cost is O(total batches) per request. Query text and results are never logged.

Status mapping (existing record statuses from calculate_record_status):
  approved         <- "אושר ידנית"
  needs_correction <- "לא תקין", "דורש השלמה"
  pending          <- everything else ("דורש בדיקה", "תקין", unknown)
Batch status: approved only if it has >=1 record and ALL records are approved; otherwise
needs_correction if any record needs correction; otherwise pending. A status filter matches the
derived batch status, so a mixed batch is never listed as approved.
"""
import logging
import re
from typing import Any, Dict, Iterable, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.api import process
from app.domain.models import CommitmentRecord, TestRecord

router = APIRouter(prefix="/api", tags=["history"])

MAX_LIMIT = 50
StatusFilter = Literal["all", "pending", "needs_correction", "approved"]

_APPROVED = {"אושר ידנית"}
_NEEDS_CORRECTION = {"לא תקין", "דורש השלמה"}


class SearchRequest(BaseModel):
    query: str = Field("", max_length=100)
    status: StatusFilter = "all"
    limit: int = Field(20, ge=1, le=MAX_LIMIT)
    offset: int = Field(0, ge=0)


def _value(field: Any) -> Any:
    if not isinstance(field, dict):
        return field
    for key in ("reviewed_value", "normalized_value", "raw_value"):
        if field.get(key) is not None:
            return field[key]
    return None


def _as_list(value: Any) -> List[str]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(v).strip() for v in value if v is not None and str(v).strip()]
    return [str(value).strip()]


def _digits(text: str) -> str:
    """Normalise identifiers: drop separators/whitespace, lower-case (keeps digits and letters)."""
    return re.sub(r"[\W_]", "", (text or "").lower())


def _record_status_bucket(record: Dict[str, Any], commitments: List[CommitmentRecord]) -> str:
    from app.services.classification.classifier import calculate_record_status
    try:
        status = calculate_record_status(TestRecord(**record), commitments)
    except Exception:
        return "pending"
    if status in _APPROVED:
        return "approved"
    if status in _NEEDS_CORRECTION:
        return "needs_correction"
    return "pending"


_PAGE_FIELDS = ("patient_first_name", "patient_last_name", "patient_id_number",
                "sender", "received_date", "central_numbers", "commitment_number")


def _page_status_bucket(record: Dict[str, Any]) -> str:
    """One-page-one-commitment model (the active flow). Approved == the same condition that lets
    the page pass the existing export check (every required field human-verified)."""
    ok, blockers = process._check_export_eligibility_commitments([record])
    if ok:
        return "approved"
    for name in _PAGE_FIELDS:
        field = record.get(name) or {}
        if field.get("review_state") == "human_verified":
            continue
        if field.get("extraction_state") == "invalid" or field.get("validation_issues"):
            return "needs_correction"
    if any(b.endswith("_missing") for b in blockers):
        return "needs_correction"
    return "pending"


def summarize_batch(batch_id: str, created_at: str, data: Dict[str, Any]) -> Dict[str, Any]:
    counts = {"approved": 0, "needs_correction": 0, "pending": 0}
    senders: List[str] = []
    pages = data.get("commitment_records") or []
    if pages:
        records = pages
        for record in records:
            counts[_page_status_bucket(record)] += 1
    else:  # legacy form-based batches
        commitments: List[CommitmentRecord] = []
        records = data.get("test_records") or []
        for record in records:
            counts[_record_status_bucket(record, commitments)] += 1
    for record in records:
        sender = str(_value(record.get("sender")) or "").strip()
        if sender and sender not in senders:
            senders.append(sender)
    total = len(records)
    if total and counts["approved"] == total:
        batch_status = "approved"
    elif counts["needs_correction"]:
        batch_status = "needs_correction"
    else:
        batch_status = "pending"
    return {
        "batch_id": batch_id,
        "created_at": created_at or None,
        "processing_status": data.get("status"),
        "document_count": len(data.get("documents") or []),
        "record_count": total,
        "approved_count": counts["approved"],
        "needs_correction_count": counts["needs_correction"],
        "pending_count": counts["pending"],
        "batch_status": batch_status,
        "senders": senders[:3],
    }


def _search_fields(batch_id: str, data: Dict[str, Any]):
    """Return (text_fields, number_fields) for matching, from fields actually stored."""
    texts: List[str] = [batch_id]
    numbers: List[str] = []
    for r in data.get("test_records") or []:
        first, last = _value(r.get("patient_first_name")), _value(r.get("patient_last_name"))
        full = f"{first or ''} {last or ''}".strip()
        texts += [str(x) for x in (first, last, full, _value(r.get("sender"))) if x]
        numbers += _as_list(_value(r.get("patient_id_number"))) + _as_list(_value(r.get("central_numbers")))
    for c in data.get("commitment_records") or []:
        first, last = _value(c.get("patient_first_name")), _value(c.get("patient_last_name"))
        full = f"{first or ''} {last or ''}".strip()
        texts += [str(x) for x in (first, last, full, _value(c.get("sender"))) if x]
        numbers += _as_list(_value(c.get("patient_id_number")))
        numbers += _as_list(_value(c.get("central_numbers")))
        numbers += _as_list(c.get("central_number_refs"))
        # commitment_number may itself hold several numbers
        numbers += _as_list(_value(c.get("commitment_number")))
    return [t.lower() for t in texts if t], [_digits(n) for n in numbers if _digits(n)]


def matches_query(batch_id: str, data: Dict[str, Any], query: str) -> bool:
    tokens = [t for t in query.lower().split() if t]
    if not tokens:
        return True
    texts, numbers = _search_fields(batch_id, data)
    for token in tokens:
        if any(token in t for t in texts):
            continue
        digits = _digits(token)
        # Separator-insensitive identifier comparison: exact, or substring for 4+ chars (avoids "1" matching all).
        if digits and any(
            n == digits or (len(digits) >= 4 and digits in n) for n in numbers
        ):
            continue
        return False
    return True


def run_query(rows: Iterable, query: str, status: str, limit: int, offset: int) -> Dict[str, Any]:
    """Scan every row; keep only the requested page window; count all matches."""
    status_counts = {"all": 0, "pending": 0, "needs_correction": 0, "approved": 0}
    items: List[Dict[str, Any]] = []
    matched = 0
    query = (query or "").strip()
    for batch_id, created_at, data in rows:
        if not isinstance(data, dict) or not matches_query(batch_id, data, query):
            continue
        summary = summarize_batch(batch_id, created_at, data)
        status_counts["all"] += 1
        status_counts[summary["batch_status"]] += 1
        if status != "all" and summary["batch_status"] != status:
            continue
        if offset <= matched < offset + limit:
            items.append(summary)
        matched += 1
    return {"items": items, "total": matched, "limit": limit, "offset": offset,
            "has_more": offset + len(items) < matched, "status_counts": status_counts}


def _execute(query: str, status: str, limit: int, offset: int) -> Dict[str, Any]:
    try:
        return run_query(process._storage.iter_batch_rows(), query, status, limit, offset)
    except Exception:
        # Never expose provider errors, credentials, or query/patient values.
        logging.getLogger(__name__).error("Saved records lookup failed")
        raise HTTPException(503, "לא ניתן לטעון את הרשומות השמורות כרגע. נסו שוב מאוחר יותר.")


@router.get("/batches/history")
def batch_history(limit: int = Query(20, ge=1, le=MAX_LIMIT), offset: int = Query(0, ge=0),
                  status: StatusFilter = "all"):
    return _execute("", status, limit, offset)


@router.post("/batches/search")
def search_batches(body: SearchRequest):
    return _execute(body.query, body.status, body.limit, body.offset)

