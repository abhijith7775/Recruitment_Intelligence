"""Contract-compliant AI Automation execution pipeline.

Reads resume documents described by ``contracts/ai_automation/input.schema.json``,
extracts structured candidate fields, updates the module's skill dictionary
and extracted-candidates CSV inside ``modules/ai_automation/``, and emits a
schema-validated ``ai_automation.json`` output envelope.

Important: Raw repository files in ``data/`` and other modules' folders are
strictly read-only and never modified by this pipeline.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date, datetime
import json
import os
from pathlib import Path
import re
import tempfile
import threading
from typing import Any, Optional
import uuid

import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from modules.ai_automation.document_reader import infer_mime_type, read_resume_document, resolve_content_path
    from modules.ai_automation.extractor import FieldExtraction, ResumeExtractionResult, extract_resume_fields
    from modules.ai_automation.skill_matcher import SkillMatcher
else:
    from .document_reader import infer_mime_type, read_resume_document, resolve_content_path
    from .extractor import FieldExtraction, ResumeExtractionResult, extract_resume_fields
    from .skill_matcher import SkillMatcher


MODULE_DIR = Path(__file__).resolve().parent
REPO_ROOT = MODULE_DIR.parent.parent

DEFAULT_CANDIDATES_CSV_PATH = MODULE_DIR / "data" / "candidates_extracted.csv"
DEFAULT_SKILL_DICTIONARY_PATH = REPO_ROOT / "data" / "skill_dictionary.csv"
DEFAULT_OUTPUT_JSON_PATH = MODULE_DIR / "outputs" / "ai_automation.json"

CANDIDATE_CSV_COLUMNS = [
    "candidate_id",
    "name",
    "email",
    "phone",
    "location",
    "experience_years",
    "skills",
    "education",
    "source",
    "application_date",
]

ALL_EXTRACTED_FIELDS = [
    "name",
    "email",
    "phone",
    "experience_years",
    "skills",
    "education",
]

_WRITE_LOCK = threading.Lock()


@dataclass
class PipelineRunReport:
    """In-memory summary of a pipeline execution for callers and UI views."""

    output_payload: dict[str, Any]
    output_json_path: Path
    candidates_csv_path: Path
    skill_dictionary_path: Path
    added_candidate_rows: list[dict[str, str]]
    newly_added_skills: list[dict[str, str]]
    duplicate_alerts: list[dict[str, str]]
    schema_validated: bool


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f"{path.stem}_", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _atomic_write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f"{path.stem}_", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _get_candidate_columns(raw_candidates_path: Path) -> list[str]:
    """Read exact CSV header from data/raw/candidates.csv when available."""
    if raw_candidates_path.exists():
        with raw_candidates_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
            if header and "candidate_id" in header:
                return header
    return list(CANDIDATE_CSV_COLUMNS)


def _load_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _max_candidate_number(rows: list[dict[str, str]]) -> int:
    max_num = 0
    for row in rows:
        cid = (row.get("candidate_id") or "").strip()
        match = re.fullmatch(r"C(\d+)", cid, re.IGNORECASE)
        if match:
            max_num = max(max_num, int(match.group(1)))
    return max_num


def _format_experience_csv(value: Any) -> str:
    if value is None or value == "":
        return ""
    num = float(value)
    if num.is_integer():
        return str(int(num))
    return str(round(num, 1))


def _phone_tail(phone_value: str) -> str:
    digits = re.sub(r"\D", "", phone_value or "")
    return digits[-10:] if len(digits) >= 10 else digits


def _find_duplicate_matches(
    *,
    email: Optional[str],
    phone: Optional[str],
    existing_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Identify potential duplicates for human review without blocking or merging."""
    alerts: list[dict[str, str]] = []
    norm_email = (email or "").strip().lower()
    norm_phone = _phone_tail(phone or "")

    for row in existing_rows:
        existing_cid = (row.get("candidate_id") or "").strip()
        existing_name = (row.get("name") or "").strip()
        row_email = (row.get("email") or "").strip().lower()
        row_phone = _phone_tail(row.get("phone") or "")

        reasons: list[str] = []
        if norm_email and row_email and norm_email == row_email:
            reasons.append("same_email")
        if norm_phone and row_phone and norm_phone == row_phone:
            reasons.append("same_phone")

        if reasons:
            alerts.append(
                {
                    "matched_candidate_id": existing_cid,
                    "matched_name": existing_name,
                    "reason": ",".join(reasons),
                }
            )
    return alerts


def validate_contract_payload(payload: dict[str, Any], schema_path: Path) -> None:
    """Validate a JSON payload against its JSON Schema draft 2020-12 contract."""
    if not schema_path.exists():
        return
    try:
        import jsonschema  # type: ignore
        from jsonschema import Draft202012Validator, FormatChecker  # type: ignore
    except ImportError:
        return

    with schema_path.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    if errors:
        first = errors[0]
        location = ".".join(str(p) for p in first.path) or "<root>"
        raise jsonschema.ValidationError(
            f"Contract validation failed against '{schema_path.name}' at {location}: {first.message}"
        )


def _failed_extraction_entry(document_id: str, candidate_id: Optional[str]) -> dict[str, Any]:
    empty_field = FieldExtraction(
        value=None,
        confidence=None,
        source_text=None,
        review_required=True,
    ).to_contract_dict()
    return {
        "document_id": document_id,
        "candidate_id": candidate_id,
        "name": dict(empty_field),
        "email": dict(empty_field),
        "phone": dict(empty_field),
        "experience_years": dict(empty_field),
        "skills": [],
        "education": [],
        "missing_fields": list(ALL_EXTRACTED_FIELDS),
        "processing_status": "failed",
    }


def _build_run_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = uuid.uuid4().hex[:6].upper()
    return f"AI_AUTOMATION-{timestamp}-{suffix}"


class AIAutomationPipeline:
    """Coordinates resume extraction, CSV generation, dictionary updates, and contract JSON."""

    def __init__(
        self,
        *,
        repo_root: Path = REPO_ROOT,
        candidates_csv_path: Path = DEFAULT_CANDIDATES_CSV_PATH,
        skill_dictionary_path: Path = DEFAULT_SKILL_DICTIONARY_PATH,
        output_json_path: Path = DEFAULT_OUTPUT_JSON_PATH,
        start_after_raw: bool = True,
        sync_to_raw: bool = False,
    ) -> None:
        self.repo_root = repo_root
        self.raw_candidates_path = repo_root / "data" / "raw" / "candidates.csv"
        self.input_schema_path = repo_root / "contracts" / "ai_automation" / "input.schema.json"
        self.output_schema_path = repo_root / "contracts" / "ai_automation" / "output.schema.json"
        self.candidates_csv_path = candidates_csv_path
        self.skill_dictionary_path = skill_dictionary_path
        self.output_json_path = output_json_path
        self.start_after_raw = start_after_raw
        self.sync_to_raw = sync_to_raw

    def run(
        self,
        input_payload: dict[str, Any],
        *,
        base_dir: Optional[Path] = None,
        source: Optional[str] = None,
        application_date: Optional[str] = None,
        append_to_csv: bool = True,
        run_id: Optional[str] = None,
    ) -> PipelineRunReport:
        """Process a contract-formatted input payload and persist module outputs."""
        validate_contract_payload(input_payload, self.input_schema_path)

        documents = input_payload.get("documents", [])
        extraction_config = input_payload.get("extraction_config")
        app_date_str = application_date or ""
        source_str = source or ""

        with _WRITE_LOCK:
            skill_matcher = SkillMatcher(
                dictionary_path=self.skill_dictionary_path,
                repo_root=self.repo_root,
            )

            columns = _get_candidate_columns(self.raw_candidates_path)
            existing_extracted_rows = _load_csv_rows(self.candidates_csv_path)
            raw_rows = _load_csv_rows(self.raw_candidates_path)

            next_num = _max_candidate_number(existing_extracted_rows)
            if self.start_after_raw:
                next_num = max(next_num, _max_candidate_number(raw_rows))

            reference_rows_for_dups = raw_rows + existing_extracted_rows

            extractions_json: list[dict[str, Any]] = []
            errors: list[dict[str, Any]] = []
            added_candidate_rows: list[dict[str, str]] = []
            newly_added_skills: list[dict[str, str]] = []
            duplicate_alerts: list[dict[str, str]] = []

            successful_count = 0
            partial_count = 0
            failed_count = 0

            for doc in documents:
                doc_id = doc["document_id"]
                file_name = doc["file_name"]
                mime_type = doc["mime_type"]
                content_uri = doc.get("content_uri")
                supplied_cid = doc.get("candidate_id")

                resolved_path = resolve_content_path(
                    content_uri=content_uri,
                    file_name=file_name,
                    base_dir=base_dir or self.repo_root,
                )

                if resolved_path is None:
                    failed_count += 1
                    extractions_json.append(_failed_extraction_entry(doc_id, supplied_cid))
                    errors.append(
                        {
                            "code": "DOCUMENT_NOT_FOUND",
                            "message": f"Could not resolve readable file for '{file_name}' (uri={content_uri}).",
                            "record_id": doc_id,
                            "field": "content_uri",
                        }
                    )
                    continue

                read_res = read_resume_document(resolved_path, mime_type=mime_type)
                if not read_res.ok:
                    failed_count += 1
                    extractions_json.append(_failed_extraction_entry(doc_id, supplied_cid))
                    errors.append(
                        {
                            "code": read_res.error_code or "READ_FAILED",
                            "message": read_res.error_message or f"Failed to read '{file_name}'.",
                            "record_id": doc_id,
                            "field": "content_uri",
                        }
                    )
                    continue

                if supplied_cid:
                    assigned_cid = supplied_cid
                else:
                    next_num += 1
                    assigned_cid = f"C{next_num:03d}"

                extraction: ResumeExtractionResult = extract_resume_fields(
                    document_id=doc_id,
                    resume_text=read_res.text,
                    skill_matcher=skill_matcher,
                    candidate_id=assigned_cid,
                    extraction_config=extraction_config,
                    persist_skill_updates=False,
                )

                if extraction.processing_status == "success":
                    successful_count += 1
                elif extraction.processing_status == "partial_success":
                    partial_count += 1
                else:
                    failed_count += 1

                extractions_json.append(extraction.to_contract_dict())
                newly_added_skills.extend(extraction.newly_added_dictionary_entries)

                # Check potential duplicates against reference records (non-blocking warning).
                dups = _find_duplicate_matches(
                    email=extraction.email.value,
                    phone=extraction.phone.value,
                    existing_rows=reference_rows_for_dups,
                )
                for dup in dups:
                    duplicate_alerts.append(
                        {
                            "new_candidate_id": assigned_cid,
                            "file_name": file_name,
                            **dup,
                        }
                    )

                csv_row = {col: "" for col in columns}
                csv_row["candidate_id"] = assigned_cid
                csv_row["name"] = str(extraction.name.value or "")
                csv_row["email"] = str(extraction.email.value or "")
                csv_row["phone"] = str(extraction.phone.value or "")
                csv_row["location"] = str(extraction.location or "")
                csv_row["experience_years"] = _format_experience_csv(extraction.experience_years.value)
                csv_row["skills"] = ";".join(extraction.canonical_skills())
                csv_row["education"] = extraction.education_summary()
                csv_row["source"] = source_str
                csv_row["application_date"] = app_date_str

                added_candidate_rows.append(csv_row)
                reference_rows_for_dups.append(csv_row)

            # Persist updated candidates CSV inside modules/ai_automation/data/
            if append_to_csv:
                all_rows = existing_extracted_rows + added_candidate_rows
            else:
                all_rows = added_candidate_rows
            _atomic_write_csv(self.candidates_csv_path, columns, all_rows)

            # Optionally update data/raw/candidates.csv so other modules have access to newly uploaded candidates
            if self.sync_to_raw and self.raw_candidates_path.exists() and added_candidate_rows:
                raw_cids = {r.get("candidate_id") for r in raw_rows}
                raw_to_append = [r for r in added_candidate_rows if r.get("candidate_id") not in raw_cids]
                if raw_to_append:
                    _atomic_write_csv(self.raw_candidates_path, columns, raw_rows + raw_to_append)

            total_docs = len(documents)
            if total_docs == 0 or failed_count == total_docs:
                overall_status = "failed"
            elif failed_count > 0:
                overall_status = "partial_success"
            else:
                overall_status = "success"

            output_payload: dict[str, Any] = {
                "module": "ai_automation",
                "schema_version": "0.1",
                "run_id": run_id or _build_run_id(),
                "status": overall_status,
                "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "data": {
                    "extractions": extractions_json,
                },
                "summary": {
                    "document_count": total_docs,
                    "successful_count": successful_count,
                    "partial_count": partial_count,
                    "failed_count": failed_count,
                },
                "errors": errors,
            }

            validate_contract_payload(output_payload, self.output_schema_path)
            _atomic_write_json(self.output_json_path, output_payload)

            return PipelineRunReport(
                output_payload=output_payload,
                output_json_path=self.output_json_path,
                candidates_csv_path=self.candidates_csv_path,
                skill_dictionary_path=self.skill_dictionary_path,
                added_candidate_rows=added_candidate_rows,
                newly_added_skills=newly_added_skills,
                duplicate_alerts=duplicate_alerts,
                schema_validated=self.output_schema_path.exists(),
            )


def run_ai_automation(
    resume_paths: list[str | Path],
    *,
    candidates_csv_path: Path = DEFAULT_CANDIDATES_CSV_PATH,
    skill_dictionary_path: Path = DEFAULT_SKILL_DICTIONARY_PATH,
    output_json_path: Path = DEFAULT_OUTPUT_JSON_PATH,
    append_to_csv: bool = True,
    application_date: Optional[str] = None,
) -> PipelineRunReport:
    """Convenience function to process a list of local resume files."""
    documents = []
    for idx, raw_path in enumerate(resume_paths, start=1):
        path = Path(raw_path).resolve()
        documents.append(
            {
                "document_id": f"DOC{idx:03d}",
                "file_name": path.name,
                "mime_type": infer_mime_type(path.name),
                "content_uri": str(path),
                "candidate_id": None,
            }
        )

    pipeline = AIAutomationPipeline(
        candidates_csv_path=candidates_csv_path,
        skill_dictionary_path=skill_dictionary_path,
        output_json_path=output_json_path,
    )
    return pipeline.run(
        {"documents": documents},
        application_date=application_date,
        append_to_csv=append_to_csv,
    )


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Run AI Automation resume extraction pipeline."
    )
    parser.add_argument(
        "resumes",
        nargs="*",
        help="Paths to PDF, DOCX, DOC, or TXT resume files.",
    )
    parser.add_argument(
        "--input-json",
        type=Path,
        default=None,
        help="Path to a contract-compliant ai_automation input JSON file.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=DEFAULT_OUTPUT_JSON_PATH,
        help="Where to write ai_automation.json (defaults inside modules/ai_automation/outputs).",
    )
    parser.add_argument(
        "--candidates-csv",
        type=Path,
        default=DEFAULT_CANDIDATES_CSV_PATH,
        help="Where to write extracted candidates CSV.",
    )
    parser.add_argument(
        "--skill-dictionary-csv",
        type=Path,
        default=DEFAULT_SKILL_DICTIONARY_PATH,
        help="Path to project skill dictionary CSV (data/skill_dictionary.csv).",
    )
    parser.add_argument(
        "--overwrite-csv",
        action="store_true",
        help="Overwrite extracted candidates CSV instead of appending.",
    )
    args = parser.parse_args()

    pipeline = AIAutomationPipeline(
        candidates_csv_path=args.candidates_csv,
        skill_dictionary_path=args.skill_dictionary_path,
        output_json_path=args.output_json,
    )

    if args.input_json:
        with args.input_json.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        report = pipeline.run(
            payload,
            base_dir=args.input_json.parent,
            append_to_csv=not args.overwrite_csv,
        )
    elif args.resumes:
        report = run_ai_automation(
            args.resumes,
            candidates_csv_path=args.candidates_csv,
            skill_dictionary_path=args.skill_dictionary_path,
            output_json_path=args.output_json,
            append_to_csv=not args.overwrite_csv,
        )
    else:
        parser.error("Provide one or more resume file paths or --input-json.")

    print(json.dumps(report.output_payload, indent=2))
    print(f"\nSaved JSON: {report.output_json_path}")
    print(f"Saved Candidates CSV: {report.candidates_csv_path}")
    print(f"Saved Skill Dictionary CSV: {report.skill_dictionary_path}")


if __name__ == "__main__":
    _main()
