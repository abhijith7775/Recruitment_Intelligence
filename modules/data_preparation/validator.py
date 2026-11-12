
from datetime import date

from modules.data_preparation.loader import load_input_data


# ==================================================
# 1. VALIDATION RULES
# ==================================================

REQUIRED_COLUMNS = {
    "candidates": [
        "candidate_id",
        "name",
        "experience_years",
        "skills",
    ],
    "jobs": [
        "job_id",
        "role",
        "required_skills",
        "min_experience",
        "max_experience",
    ],
    "applications": [
        "candidate_id",
        "job_id",
        "stage",
        "stage_date",
    ],
    "activity": [
        "candidate_id",
        "event_type",
        "event_date",
    ],
    "skill_dictionary": [
        "original_skill",
        "canonical_skill",
    ],
}

APPROVED_APPLICATION_STAGES = {
    "New",
    "Screened",
    "Shortlisted",
    "Interviewed",
    "Offered",
    "Hired",
    "Rejected",
}


# ==================================================
# 2. REQUIRED COLUMN VALIDATION
# ==================================================

def validate_required_columns(datasets):
    issues = []

    for dataset_name, required_columns in REQUIRED_COLUMNS.items():

        if dataset_name not in datasets:
            issues.append({
                "dataset": dataset_name,
                "issue": "missing_dataset",
                "details": f"Dataset '{dataset_name}' was not loaded."
            })
            continue

        dataframe = datasets[dataset_name]

        for column in required_columns:

            if column not in dataframe.columns:
                issues.append({
                    "dataset": dataset_name,
                    "issue": "missing_column",
                    "column": column,
                    "details": (
                        f"Required column '{column}' is missing."
                    )
                })

    return issues


# ==================================================
# 3. MISSING VALUE VALIDATION
# ==================================================


def validate_missing_values(datasets):
    issues = []

    optional_value_fields = {
        "candidates": ["experience_years", "skills"]
    }

    for dataset_name, required_columns in REQUIRED_COLUMNS.items():

        if dataset_name not in datasets:
            continue

        dataframe = datasets[dataset_name]

        for column in required_columns:

            if column not in dataframe.columns:
                continue

            missing_rows = dataframe.index[
                dataframe[column].astype(str).str.strip().eq("")
            ].tolist()

            for row_index in missing_rows:

                is_warning = column in optional_value_fields.get(
                    dataset_name, []
                )

                issues.append({
                    "dataset": dataset_name,
                    "issue": (
                        "missing_optional_value"
                        if is_warning
                        else "missing_required_value"
                    ),
                    "severity": "warning" if is_warning else "error",
                    "column": column,
                    "row_number": int(row_index) + 2,
                    "details": (
                        f"Optional value missing in column '{column}'."
                        if is_warning
                        else f"Required value missing in column '{column}'."
                    )
                })

    return issues



# ==================================================
# 4. APPLICATION REFERENCE VALIDATION
# ==================================================

def validate_application_references(datasets):
    issues = []

    candidates = datasets["candidates"]
    jobs = datasets["jobs"]
    applications = datasets["applications"]

    valid_candidate_ids = set(
        candidates["candidate_id"].astype(str).str.strip()
    )

    valid_job_ids = set(
        jobs["job_id"].astype(str).str.strip()
    )

    for index, row in applications.iterrows():

        candidate_id = str(row["candidate_id"]).strip()
        job_id = str(row["job_id"]).strip()

        if candidate_id not in valid_candidate_ids:
            issues.append({
                "dataset": "applications",
                "issue": "invalid_candidate_reference",
                "row_number": int(index) + 2,
                "value": candidate_id,
                "details": "Candidate ID does not exist."
            })

        if job_id not in valid_job_ids:
            issues.append({
                "dataset": "applications",
                "issue": "invalid_job_reference",
                "row_number": int(index) + 2,
                "value": job_id,
                "details": "Job ID does not exist."
            })

    return issues


# ==================================================
# 5. DATE VALIDATION
# ==================================================

def validate_dates(datasets):
    issues = []

    date_columns = {
        "candidates": ["application_date"],
        "applications": ["stage_date"],
        "activity": ["event_date"],
    }

    for dataset_name, columns in date_columns.items():

        if dataset_name not in datasets:
            continue

        dataframe = datasets[dataset_name]

        for column in columns:

            if column not in dataframe.columns:
                continue

            for index, value in dataframe[column].items():

                value = str(value).strip()

                if not value:
                    continue

                try:
                    parsed_date = date.fromisoformat(value)

                    if parsed_date.isoformat() != value:
                        raise ValueError("Incorrect date format")

                except ValueError:
                    issues.append({
                        "dataset": dataset_name,
                        "issue": "invalid_date",
                        "column": column,
                        "row_number": int(index) + 2,
                        "value": value,
                        "details": (
                            "Date must use YYYY-MM-DD format."
                        )
                    })

    return issues


# ==================================================
# 6. APPLICATION STAGE VALIDATION
# ==================================================

def validate_application_stages(datasets):
    issues = []

    if "applications" not in datasets:
        return issues

    applications = datasets["applications"]

    if "stage" not in applications.columns:
        return issues

    for index, value in applications["stage"].items():

        stage = str(value).strip()

        if not stage:
            continue

        if stage not in APPROVED_APPLICATION_STAGES:
            issues.append({
                "dataset": "applications",
                "issue": "invalid_application_stage",
                "column": "stage",
                "row_number": int(index) + 2,
                "value": stage,
                "details": (
                    "Application stage is not in the approved list."
                )
            })

    return issues


# ==================================================
# 7. EXPERIENCE VALIDATION
# ==================================================

def validate_experience_values(datasets):
    issues = []

    # Candidate experience
    if "candidates" in datasets:

        candidates = datasets["candidates"]

        if "experience_years" in candidates.columns:

            for index, value in candidates["experience_years"].items():

                value = str(value).strip()

                if not value:
                    continue

                try:
                    experience = float(value)

                    if experience < 0:
                        raise ValueError

                except ValueError:
                    issues.append({
                        "dataset": "candidates",
                        "issue": "invalid_experience_value",
                        "column": "experience_years",
                        "row_number": int(index) + 2,
                        "value": value,
                        "details": (
                            "Experience must be a non-negative number."
                        )
                    })

    # Job experience range
    if "jobs" in datasets:

        jobs = datasets["jobs"]

        required_columns = {
            "min_experience",
            "max_experience"
        }

        if required_columns.issubset(jobs.columns):

            for index, row in jobs.iterrows():

                min_value = str(row["min_experience"]).strip()
                max_value = str(row["max_experience"]).strip()

                if not min_value or not max_value:
                    continue

                try:
                    min_experience = float(min_value)
                    max_experience = float(max_value)

                    if min_experience < 0 or max_experience < 0:
                        raise ValueError

                    if min_experience > max_experience:
                        issues.append({
                            "dataset": "jobs",
                            "issue": "invalid_experience_range",
                            "row_number": int(index) + 2,
                            "min_experience": min_value,
                            "max_experience": max_value,
                            "details": (
                                "Minimum experience cannot exceed "
                                "maximum experience."
                            )
                        })

                except ValueError:
                    issues.append({
                        "dataset": "jobs",
                        "issue": "invalid_experience_value",
                        "row_number": int(index) + 2,
                        "details": (
                            "Job experience values must be "
                            "non-negative numbers."
                        )
                    })

    return issues


# ==================================================
# 8. SKILL VALIDATION
# ==================================================

def validate_skills(datasets):
    """
    Validate candidate skills, job-required skills
    and skill dictionary mappings.

    Checks:
    - Empty skill entries
    - Unknown skills
    - Duplicate skill entries
    - Incomplete skill mappings
    - Conflicting canonical mappings

    Does not modify or delete skills.
    """

    issues = []

    if "skill_dictionary" not in datasets:
        return [{
            "dataset": "skill_dictionary",
            "issue": "missing_skill_dictionary",
            "details": "Skill dictionary was not loaded."
        }]

    dictionary = datasets["skill_dictionary"]

    required_columns = {
        "original_skill",
        "canonical_skill"
    }

    if not required_columns.issubset(dictionary.columns):
        return [{
            "dataset": "skill_dictionary",
            "issue": "missing_dictionary_columns",
            "details": (
                "Required skill dictionary columns are missing."
            )
        }]

    skill_mappings = {}
    canonical_skills = set()

    # Build approved skill mappings
    for index, row in dictionary.iterrows():

        original = str(row["original_skill"]).strip().lower()
        canonical = str(row["canonical_skill"]).strip().lower()

        if not original or not canonical:
            issues.append({
                "dataset": "skill_dictionary",
                "issue": "incomplete_skill_mapping",
                "row_number": int(index) + 2,
                "details": (
                    "Original or canonical skill is missing."
                )
            })
            continue

        if original in skill_mappings:

            if skill_mappings[original] != canonical:
                issues.append({
                    "dataset": "skill_dictionary",
                    "issue": "conflicting_skill_mapping",
                    "row_number": int(index) + 2,
                    "value": original,
                    "details": (
                        "The same original skill has conflicting "
                        "canonical mappings."
                    )
                })

        else:
            skill_mappings[original] = canonical

        canonical_skills.add(canonical)

    # Accept original names and canonical names
    known_skills = set(skill_mappings.keys()) | canonical_skills

    # Validate candidate and job skill lists
    skill_columns = {
        "candidates": "skills",
        "jobs": "required_skills"
    }

    for dataset_name, column in skill_columns.items():

        if dataset_name not in datasets:
            continue

        dataframe = datasets[dataset_name]

        if column not in dataframe.columns:
            continue

        for index, value in dataframe[column].items():

            raw_value = str(value).strip()

            if not raw_value:
                continue

            tokens = raw_value.split(";")
            seen_skills = set()

            for token in tokens:

                skill = token.strip().lower()

                if not skill:
                    issues.append({
                        "dataset": dataset_name,
                        "issue": "empty_skill_entry",
                        "column": column,
                        "row_number": int(index) + 2,
                        "details": "An empty skill entry was found."
                    })
                    continue

                # Check repeated skill entries
                if skill in seen_skills:
                    issues.append({
                        "dataset": dataset_name,
                        "issue": "duplicate_skill_entry",
                        "column": column,
                        "row_number": int(index) + 2,
                        "value": skill,
                        "details": (
                            "The same skill appears more than once."
                        )
                    })
                else:
                    seen_skills.add(skill)

                # Check unknown skills
                if skill not in known_skills:
                    issues.append({
                        "dataset": dataset_name,
                        "issue": "unknown_skill",
                        "column": column,
                        "row_number": int(index) + 2,
                        "value": skill,
                        "details": (
                            "Skill is not present in the approved "
                            "skill dictionary."
                        )
                    })

    return issues


# ==================================================
# 9. RUN ALL VALIDATION CHECKS
# ==================================================


def run_validation(datasets):

    column_issues = validate_required_columns(datasets)

    missing_value_issues = validate_missing_values(datasets)

    reference_issues = []
    candidates = datasets.get("candidates")
    jobs = datasets.get("jobs")
    applications = datasets.get("applications")

    if (
        candidates is not None
        and jobs is not None
        and applications is not None
        and "candidate_id" in candidates.columns
        and "job_id" in jobs.columns
        and "candidate_id" in applications.columns
        and "job_id" in applications.columns
    ):
        reference_issues = validate_application_references(datasets)

    date_issues = validate_dates(datasets)
    stage_issues = validate_application_stages(datasets)
    experience_issues = validate_experience_values(datasets)
    skill_issues = validate_skills(datasets)

    all_issues = (
        column_issues
        + missing_value_issues
        + reference_issues
        + date_issues
        + stage_issues
        + experience_issues
        + skill_issues
    )

    warnings = [
        issue for issue in all_issues
        if issue.get("severity") == "warning"
    ]

    errors = [
        issue for issue in all_issues
        if issue.get("severity") != "warning"
    ]

    return {
        "status": "completed",
        "summary": {
            "total_errors": len(errors),
            "total_warnings": len(warnings),
            "total_issues": len(all_issues),
            "missing_column_issues": len(column_issues),
            "missing_required_values": sum(
                1 for issue in missing_value_issues
                if issue.get("severity") != "warning"
            ),
            "missing_optional_values": len(warnings),
            "invalid_application_references": len(reference_issues),
            "invalid_dates": len(date_issues),
            "invalid_application_stages": len(stage_issues),
            "invalid_experience_values": len(experience_issues),
            "skill_issues": len(skill_issues),
        },
        "issues": all_issues,
    }

# ==================================================
# 10. MAIN EXECUTION
# ==================================================

if __name__ == "__main__":

    datasets = load_input_data()

    result = run_validation(datasets)

    print("\nVALIDATION SUMMARY")
    print("------------------")

    for key, value in result["summary"].items():
        print(f"{key.replace('_', ' ').title()}: {value}")

    print("\nVALIDATION ISSUES")
    print("-----------------")

    if result["issues"]:

        for issue in result["issues"]:
            print(issue)

    else:
        print("No validation issues found.")

    print("\nValidation status:", result["status"])
