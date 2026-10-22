"""Exception-only review, recall fixes and source page (offline, mocked extractor output)."""
from app.domain.models import ReviewState
from app.services.extraction.commitment_classifier import classify_commitments, COMMITMENT
from app.services.extraction.extractor import ExtractionResult
from app.services.extraction.gemini_adapter import CommitmentFormExtraction, _coerce_raw_fields
from app.services.processing.background import BackgroundProcessor
from app.services.review_rules import annotate_record, field_review_reasons, source_page_of


def _page(page_index=0, warnings=(), **overrides):
    fields = {
        "patient_first_name": "Dana", "patient_last_name": "Levi", "patient_id_number": "012345674",
        "sender": "Clalit", "received_date": "15/03/2024", "central_numbers": ["946621"],
        "commitment_numbers": ["730578626"], "commitment_types": [{"number": "730578626", "label": COMMITMENT}],
        "commitment_candidates": [],
    }
    fields.update(overrides)
    result = ExtractionResult("1", fields, list(warnings), "synthetic", "test", 0.0)
    return object.__new__(BackgroundProcessor)._create_commitment_from_page(result, "doc", page_index)


def test_clean_page_is_auto_accepted_never_human_verified():
    record = _page()
    for name in ("patient_first_name", "patient_last_name", "patient_id_number", "sender",
                 "received_date", "central_numbers", "commitment_number"):
        assert getattr(record, name).review_state == ReviewState.auto_accepted
    data = annotate_record(record.model_dump(mode="json"))
    assert data["review_required"] is False
    assert all(not data[n]["review_required"] for n in ("sender", "commitment_number"))


def test_flagged_fields_carry_precise_hebrew_reasons():
    data = annotate_record(_page(patient_id_number="12345678", received_date="15/03/24",
                                 warnings=["patient_first_name: handwriting unreadable"]).model_dump(mode="json"))
    assert "תעודת הזהות מכילה 8 ספרות במקום 9." in data["patient_id_number"]["review_reasons_he"]
    assert any("שנה דו־ספרתית שהורחבה ל־2024" in r for r in data["received_date"]["review_reasons_he"])
    assert data["patient_first_name"]["review_required"] is True
    assert data["patient_last_name"]["review_required"] is False
    assert data["review_required"] is True


def test_missing_commitment_and_checksum_reasons():
    data = annotate_record(_page(patient_id_number="123456789", commitment_numbers=[],
                                 commitment_types=[]).model_dump(mode="json"))
    assert data["commitment_number"]["review_reasons_he"] == ["לא זוהה מספר התחייבות במסמך."]
    assert data["patient_id_number"]["review_reasons_he"] == ["מספר תעודת הזהות אינו עובר בדיקת ספרת ביקורת."]


def test_several_accepted_commitments_are_not_ambiguity_but_unlabeled_stays_pending():
    types = [{"number": "1001", "label": COMMITMENT}, {"number": "1002", "label": COMMITMENT}]
    clean = _page(commitment_numbers=["1001", "1002"], commitment_types=types)
    assert field_review_reasons("commitment_number", clean.commitment_number.model_dump(mode="json")) == []
    unlabeled = classify_commitments(["1001", "1003"], types[:1] + [{"number": "1003", "label": None}], [], "Clalit")
    record = _page(commitment_numbers=unlabeled.accepted, commitment_candidates=unlabeled.candidates,
                   commitment_types=types[:1] + [{"number": "1003", "label": None}], warnings=unlabeled.warnings)
    assert field_review_reasons("commitment_number", record.commitment_number.model_dump(mode="json"))


def test_source_page_is_one_based_from_real_metadata():
    assert _page(page_index=0).source_page == 1
    assert _page(page_index=4).source_page == 5
    legacy = {"form_id": "doc_page_2"}
    assert source_page_of(legacy) == 3
    assert source_page_of({"form_id": "x"}) is None


def test_number_without_label_details_is_kept_with_warning():
    result = classify_commitments(["1001", "1002"], [{"number": "1001", "label": COMMITMENT}], [], "Clalit")
    assert result.accepted == ["1001", "1002"]
    assert any("1002" in w for w in result.warnings)


def test_single_unlabeled_number_stays_visible_as_uncertain_value():
    types = [{"number": "1001", "label": None}]
    classification = classify_commitments(["1001"], types, [], "Clalit")
    record = _page(commitment_numbers=classification.accepted, commitment_types=types,
                   commitment_candidates=classification.candidates, warnings=classification.warnings)
    assert record.commitment_number.raw_value == "1001"
    assert record.commitment_number.extraction_state.value == "uncertain"
    assert record.commitment_number.review_state == ReviewState.needs_review


def test_lenient_coercion_keeps_page_instead_of_discarding_it():
    raw = {"patient_first_name": "Dana", "patient_last_name": None, "patient_id_number": 12345,
           "sender": None, "received_date": None, "central_numbers": None, "commitment_numbers": "1001",
           "commitment_types": None, "warnings": None}
    parsed = CommitmentFormExtraction.model_validate(_coerce_raw_fields(raw), strict=True)
    assert parsed.patient_id_number == "12345" and parsed.central_numbers == []
    assert parsed.commitment_numbers == ["1001"] and parsed.commitment_types == []
