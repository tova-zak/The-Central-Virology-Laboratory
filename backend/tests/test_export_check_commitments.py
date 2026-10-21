"""Test the export eligibility gate with the one-page-one-commitment model.

Verifies:
- Correct blocking logic for pending/incomplete/unreviewed/missing fields
- Correct approval for fully reviewed commitments
- Reviewer-confirmed empty values (allowed only for the confirmable fields)
"""
from app.api.process import _check_export_eligibility_commitments

SCALAR_FIELDS = ("patient_first_name", "patient_last_name", "patient_id_number", "sender",
                 "received_date", "commitment_number")


def _field(value, review_state="human_verified"):
    return {
        "raw_value": value,
        "normalized_value": value,
        "reviewed_value": None,
        "extraction_state": "found",
        "review_state": review_state,
    }


def _record(record_id="cmt_001", status="complete", **overrides):
    record = {
        "commitment_record_id": record_id,
        "status": status,
        "patient_first_name": _field("FIRST"),
        "patient_last_name": _field("LAST"),
        "patient_id_number": _field("000000018"),
        "sender": _field("SENDER"),
        "received_date": _field("01/01/2026"),
        "central_numbers": _field(["100001"]),
        "commitment_number": _field("200001"),
    }
    record.update(overrides)
    return record


def test_export_check_all_approved():
    """Fully reviewed commitments can export."""
    can_export, blockers = _check_export_eligibility_commitments([_record()])
    assert can_export is True
    assert blockers == []


def test_export_check_no_records_blocks():
    can_export, blockers = _check_export_eligibility_commitments([])
    assert can_export is False
    assert blockers == ["no_commitment_records"]


def test_export_check_blocked_pending():
    """Pending commitments block export."""
    can_export, blockers = _check_export_eligibility_commitments([_record("cmt_pending", status="pending")])
    assert can_export is False
    assert "cmt_pending: incomplete_extraction" in blockers


def test_export_check_blocked_incomplete():
    """Incomplete commitments block export."""
    can_export, blockers = _check_export_eligibility_commitments([_record("cmt_incomplete", status="incomplete")])
    assert can_export is False
    assert "cmt_incomplete: incomplete_extraction" in blockers


def test_export_check_blocked_needs_review():
    """Fields that are not human_verified block export."""
    record = _record("cmt_review", patient_first_name=_field("FIRST", "needs_review"))
    can_export, blockers = _check_export_eligibility_commitments([record])
    assert can_export is False
    assert blockers == ["cmt_review: patient_first_name_unreviewed"]


def test_export_check_blocked_pending_review_state():
    record = _record("cmt_pending_field", patient_id_number=_field("000000018", "pending"))
    can_export, blockers = _check_export_eligibility_commitments([record])
    assert can_export is False
    assert "cmt_pending_field: patient_id_number_unreviewed" in blockers


def test_export_check_blocked_missing_value():
    """An empty required field blocks export even when marked verified."""
    record = _record("cmt_missing", patient_id_number=_field(None))
    can_export, blockers = _check_export_eligibility_commitments([record])
    assert can_export is False
    assert "cmt_missing: patient_id_number_missing" in blockers


def test_export_check_unresolved_relationship_blocks():
    record = _record("cmt_rel", relationship_status="unresolved_relationship")
    can_export, blockers = _check_export_eligibility_commitments([record])
    assert can_export is False
    assert "cmt_rel: unresolved_relationship" in blockers


def test_export_check_confirmed_empty_allowed_only_for_confirmable_fields():
    for name in ("patient_first_name", "patient_last_name", "sender", "received_date", "commitment_number"):
        record = _record(**{name: {"reviewed_value": "", "review_state": "human_verified"}})
        can_export, blockers = _check_export_eligibility_commitments([record])
        assert can_export is True, (name, blockers)
    for name, empty in (("patient_id_number", ""), ("central_numbers", [])):
        record = _record(**{name: {"reviewed_value": empty, "review_state": "human_verified"}})
        can_export, blockers = _check_export_eligibility_commitments([record])
        assert can_export is False
        assert f"cmt_001: {name}_missing" in blockers


def test_export_check_mixed_multiple_blockers():
    """Multiple commitments with multiple blockers."""
    records = [
        _record("cmt_ok"),
        _record("cmt_pending", status="pending"),
        _record("cmt_needs_review", sender=_field("SENDER", "needs_review")),
    ]
    can_export, blockers = _check_export_eligibility_commitments(records)
    assert can_export is False
    assert "cmt_pending: incomplete_extraction" in blockers
    assert "cmt_needs_review: sender_unreviewed" in blockers
    assert not any(b.startswith("cmt_ok") for b in blockers)
    assert len(blockers) == 2
