"""Offline tests for tools.eval_accuracy (synthetic data only)."""
from tools.eval_accuracy import compare_field, evaluate, main


def _form(form_id, tagged=True, **fields):
    base = {
        "form_id": form_id, "manually_tagged": tagged,
        "patient_first_name": "FIRST", "patient_last_name": "LAST", "patient_id_number": "000000018",
        "sender": "SENDER", "received_date": "18/06/2026",
        "central_numbers": ["100001"], "commitment_numbers": ["200001"],
    }
    base.update(fields)
    return base


def test_exact_match_and_case_insensitive_names():
    assert compare_field("patient_first_name", "First", " first ")["status"] == "correct"


def test_date_format_difference_is_correct():
    assert compare_field("received_date", "18/06/2026", "18-06-2026")["status"] == "correct"


def test_id_leading_zeros_kept():
    assert compare_field("patient_id_number", "000000018", "000000018")["status"] == "correct"
    assert compare_field("patient_id_number", "000000018", "18")["status"] == "wrong"


def test_list_set_equality_and_partial_recall():
    assert compare_field("central_numbers", ["1", "2"], ["2", "1"])["status"] == "correct"
    res = compare_field("central_numbers", ["1", "2"], ["1"])
    assert res["status"] == "wrong" and res["recall"] == 0.5 and res["precision"] == 1.0


def test_absent_vs_absent_false_extraction_and_miss():
    assert compare_field("sender", None, "")["status"] == "correct"
    assert compare_field("central_numbers", [], None)["status"] == "correct"
    assert compare_field("sender", None, "X")["status"] == "false_extraction"
    assert compare_field("sender", "X", None)["status"] == "missed"


def test_evaluate_three_form_fixture():
    truth = [
        _form("f1"),
        _form("f2", sender=None),
        _form("f3", received_date=None, central_numbers=["1", "2"]),
        _form("f4", tagged=False),
    ]
    extracted = {
        "f1": _form("f1"),
        "f2": _form("f2", sender="INVENTED"),
        "f3": _form("f3", received_date=None, central_numbers=["1"], patient_last_name=None),
        "f4": _form("f4", sender="IGNORED"),
    }
    result = evaluate(truth, extracted)
    assert result["forms_evaluated"] == 3
    assert result["untagged"] == ["f4"]
    assert result["fields"]["sender"]["correct"] == 2 and result["fields"]["sender"]["total"] == 3
    assert result["fields"]["central_numbers"]["correct"] == 2
    assert result["fields"]["patient_last_name"]["missed"] == 1
    assert result["false_extractions"] == 1 and result["misses"] == 1
    assert result["overall_total"] == 21 and result["overall_correct"] == 18
    assert round(result["overall_accuracy"], 1) == 85.7


def test_cli_unreadable_input_returns_2(tmp_path):
    assert main(["--truth", str(tmp_path / "nope.json"), "--extracted", str(tmp_path / "nope2.json")]) == 2
