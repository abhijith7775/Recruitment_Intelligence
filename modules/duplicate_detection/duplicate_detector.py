import csv
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path


def optional_value(value):
    value = (value or "").strip()
    return value if value else None


def normalize_email(value):
    value = optional_value(value)
    return value.lower() if value else None


def normalize_phone(value):
    value = optional_value(value)

    if not value:
        return None

    # Handles Excel-style phone values such as 910000000007.0
    if value.endswith(".0"):
        value = value[:-2]

    digits = re.sub(r"\D", "", value)
    return digits if digits else None


def parse_experience(value):
    value = optional_value(value)
    return float(value) if value is not None else None


def parse_skills(value):
    skills = []

    for skill in (value or "").split(";"):
        skill = skill.strip().lower()

        if skill and skill not in skills:
            skills.append(skill)

    return skills


# INPUT SECTION:
# Converts candidates_cleaned.csv into the JSON input expected by the module.
def load_duplicate_detection_input(csv_path):
    candidates = []

    with open(csv_path, mode="r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            candidates.append(
                {
                    "candidate_id": row["candidate_id"].strip(),
                    "name": row["name"].strip(),
                    "email": normalize_email(row.get("email")),
                    "phone": normalize_phone(row.get("phone")),
                    "location": optional_value(row.get("location")),
                    "experience_years": parse_experience(
                        row.get("experience_years")
                    ),
                    "skills": parse_skills(row.get("skills")),
                    "education": optional_value(row.get("education")),
                    "source": optional_value(row.get("source")),
                    "application_date": optional_value(
                        row.get("application_date")
                    ),
                }
            )

    return {
        "candidates": candidates,
        "detection_config": {
            "compare_email": True,
            "compare_phone": True,
            "similarity_threshold": 1.0
        }
    }


# OUTPUT SECTION:
# Detects exact duplicate email/phone values and creates the required JSON output.
def detect_duplicates(input_data, run_id="DUPLICATE-001"):
    candidates = input_data["candidates"]
    config = input_data.get("detection_config", {})

    compare_email = config.get("compare_email", True)
    compare_phone = config.get("compare_phone", True)

    email_groups = defaultdict(list)
    phone_groups = defaultdict(list)
    pair_evidence = defaultdict(list)
    errors = []

    if not compare_email and not compare_phone:
        errors.append(
            {
                "code": "NO_COMPARISON_METHOD_ENABLED",
                "message": "Enable email and/or phone comparison.",
                "record_id": None,
                "field": None
            }
        )

    for candidate in candidates:
        candidate_id = candidate["candidate_id"]

        if compare_email and candidate["email"]:
            email_groups[candidate["email"]].append(candidate_id)

        if compare_phone and candidate["phone"]:
            phone_groups[candidate["phone"]].append(candidate_id)

    # Find pairs with the same email.
    if compare_email:
        for candidate_ids in email_groups.values():
            if len(candidate_ids) > 1:
                for first, second in combinations(sorted(candidate_ids), 2):
                    pair_evidence[(first, second)].append(
                        {
                            "field": "email",
                            "comparison_result": (
                                "Normalized email values are equal."
                            ),
                            "confidence": 1.0
                        }
                    )

    # Find pairs with the same phone.
    if compare_phone:
        for candidate_ids in phone_groups.values():
            if len(candidate_ids) > 1:
                for first, second in combinations(sorted(candidate_ids), 2):
                    pair_evidence[(first, second)].append(
                        {
                            "field": "phone",
                            "comparison_result": (
                                "Normalized phone values are equal."
                            ),
                            "confidence": 1.0
                        }
                    )

    duplicate_pairs = []

    for number, ((first, second), evidence) in enumerate(
        sorted(pair_evidence.items()),
        start=1
    ):
        if len(evidence) > 1:
            reason = "multiple_fields"
        elif evidence[0]["field"] == "email":
            reason = "same_email"
        else:
            reason = "same_phone"

        duplicate_pairs.append(
            {
                "pair_id": f"PAIR{number:03d}",
                "candidate_id_1": first,
                "candidate_id_2": second,
                "evidence": evidence,
                "reason": reason,
                "review_status": "Pending",
                "reviewer_id": None
            }
        )

    records_without_comparable_contact = []

    for candidate in candidates:
        no_email = not compare_email or not candidate["email"]
        no_phone = not compare_phone or not candidate["phone"]

        if no_email and no_phone:
            records_without_comparable_contact.append(
                candidate["candidate_id"]
            )

    status = "partial_success" if errors else "success"

    return {
        "module": "duplicate_detection",
        "schema_version": "0.1",
        "run_id": run_id,
        "status": status,
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "data": {
            "duplicate_pairs": duplicate_pairs,
            "records_without_comparable_contact": (
                records_without_comparable_contact
            )
        },
        "summary": {
            "candidate_count": len(candidates),
            "pair_count": len(duplicate_pairs),
            "pending_review_count": len(duplicate_pairs)
        },
        "errors": errors
    }


def save_output(output_data, output_path):
    with open(output_path, mode="w", encoding="utf-8") as file:
        json.dump(output_data, file, indent=2)


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[2]

    input_data = load_duplicate_detection_input(
        project_root / "data" / "processed" / "candidates_cleaned.csv"
    )

    output_data = detect_duplicates(
        input_data,
        run_id="DUPLICATE-001"
    )

    save_output(
        output_data,
        project_root / "outputs" / "duplicate_detection" / "duplicates.json"
    )