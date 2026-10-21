"""Offline ground-truth accuracy evaluation.

Usage (from backend/):
    python -m tools.eval_accuracy --truth <ground_truth.json> --extracted <extraction.json> [--out report.md]

The extraction file is produced outside this tool (e.g. from a real extraction run). This tool never imports the
extraction adapter and never opens a network connection. Exit code is 0 except for unreadable input (2).
"""
import argparse
import json
import re
import sys
from pathlib import Path

FIELDS = (
    "patient_first_name",
    "patient_last_name",
    "patient_id_number",
    "sender",
    "received_date",
    "central_numbers",
    "commitment_numbers",
)
LIST_FIELDS = ("central_numbers", "commitment_numbers")
NAME_FIELDS = ("patient_first_name", "patient_last_name", "sender")


def _is_absent(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set)):
        return all(_is_absent(v) for v in value)
    return False


def _digits(value) -> str:
    return re.sub(r"\D", "", str(value))


def _norm_scalar(field: str, value) -> str:
    text = " ".join(str(value).split())
    if field == "patient_id_number":
        return _digits(text)
    if field == "received_date":
        from app.services.validation.date_normalizer import assess_date

        normalized = assess_date(text).normalized
        return normalized or text
    if field in NAME_FIELDS:
        return text.casefold()
    return text


def _as_set(field: str, value) -> set:
    items = [value] if isinstance(value, str) else list(value or [])
    return {" ".join(str(v).split()) for v in items if not _is_absent(v)}


def compare_field(field: str, truth, extracted) -> dict:
    """Compare one field. Returns {status, precision, recall}.

    status: correct | wrong | false_extraction | missed. precision/recall are only set for list fields.
    """
    truth_absent, extracted_absent = _is_absent(truth), _is_absent(extracted)
    result = {"status": "correct", "precision": None, "recall": None}
    if truth_absent and extracted_absent:
        return result
    if truth_absent:
        result["status"] = "false_extraction"
        return result
    if extracted_absent:
        result["status"] = "missed"
        if field in LIST_FIELDS:
            result["precision"], result["recall"] = 1.0, 0.0
        return result
    if field in LIST_FIELDS:
        t, e = _as_set(field, truth), _as_set(field, extracted)
        hit = len(t & e)
        result["precision"] = hit / len(e) if e else 1.0
        result["recall"] = hit / len(t) if t else 1.0
        result["status"] = "correct" if t == e else "wrong"
        return result
    result["status"] = "correct" if _norm_scalar(field, truth) == _norm_scalar(field, extracted) else "wrong"
    return result


def _index_extracted(extracted) -> dict:
    if isinstance(extracted, dict):
        if isinstance(extracted.get("forms"), (list, dict)):
            return _index_extracted(extracted["forms"])
        return {k: v for k, v in extracted.items() if isinstance(v, dict)}
    if isinstance(extracted, list):
        return {item["form_id"]: item for item in extracted if isinstance(item, dict) and "form_id" in item}
    raise ValueError("extraction JSON must be a list or an object keyed by form_id")


def evaluate(truth_forms: list, extracted) -> dict:
    """Evaluate extraction against ground truth. Forms with manually_tagged false are skipped."""
    by_form = _index_extracted(extracted)
    stats = {f: {"correct": 0, "total": 0, "wrong": 0, "false_extraction": 0, "missed": 0,
                 "precision": [], "recall": []} for f in FIELDS}
    untagged, mismatches, evaluated = [], [], 0
    for form in truth_forms:
        form_id = form.get("form_id")
        if not form.get("manually_tagged"):
            untagged.append(form_id)
            continue
        evaluated += 1
        got = by_form.get(form_id, {})
        for field in FIELDS:
            res = compare_field(field, form.get(field), got.get(field))
            s = stats[field]
            s["total"] += 1
            s[res["status"]] += 1
            if res["precision"] is not None:
                s["precision"].append(res["precision"])
                s["recall"].append(res["recall"])
            if res["status"] != "correct":
                mismatches.append({"form_id": form_id, "field": field, "status": res["status"],
                                   "truth": form.get(field), "extracted": got.get(field)})
    total = sum(s["total"] for s in stats.values())
    correct = sum(s["correct"] for s in stats.values())
    return {
        "forms_evaluated": evaluated,
        "untagged": untagged,
        "fields": stats,
        "overall_correct": correct,
        "overall_total": total,
        "overall_accuracy": (100.0 * correct / total) if total else 0.0,
        "false_extractions": sum(s["false_extraction"] for s in stats.values()),
        "misses": sum(s["missed"] for s in stats.values()),
        "mismatches": mismatches,
    }


def _avg(values):
    return "%.2f" % (sum(values) / len(values)) if values else "-"


def render_report(result: dict) -> str:
    lines = [
        "# Accuracy evaluation",
        "",
        "Forms evaluated: %d, untagged (skipped): %d" % (result["forms_evaluated"], len(result["untagged"])),
        "",
        "| Field | Correct | Total | Accuracy % | Wrong | False extraction | Missed | Precision | Recall |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for field, s in result["fields"].items():
        acc = (100.0 * s["correct"] / s["total"]) if s["total"] else 0.0
        lines.append("| %s | %d | %d | %.1f | %d | %d | %d | %s | %s |" % (
            field, s["correct"], s["total"], acc, s["wrong"], s["false_extraction"], s["missed"],
            _avg(s["precision"]), _avg(s["recall"])))
    lines += [
        "",
        "Overall accuracy: %.1f%% (%d/%d)" % (result["overall_accuracy"], result["overall_correct"],
                                              result["overall_total"]),
        "False extractions: %d, misses: %d" % (result["false_extractions"], result["misses"]),
        "",
        "## Per-form mismatches",
    ]
    if not result["mismatches"]:
        lines.append("None")
    for m in result["mismatches"]:
        lines.append("- %s / %s [%s]: truth=%r extracted=%r" % (
            m["form_id"], m["field"], m["status"], m["truth"], m["extracted"]))
    if result["untagged"]:
        lines += ["", "## Untagged forms", ", ".join(str(u) for u in result["untagged"])]
    return "\n".join(lines) + "\n"


def _load(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Offline ground-truth accuracy evaluation")
    parser.add_argument("--truth", required=True)
    parser.add_argument("--extracted", required=True)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    try:
        truth = _load(args.truth)
        truth_forms = truth["forms"] if isinstance(truth, dict) else truth
        result = evaluate(truth_forms, _load(args.extracted))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("Unreadable input: %s" % exc, file=sys.stderr)
        return 2
    report = render_report(result)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
    sys.stdout.buffer.write(report.encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
