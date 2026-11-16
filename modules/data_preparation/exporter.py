
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from jsonschema import Draft202012Validator, FormatChecker


# ==================================================
# 1. JSON VALUE CONVERSION
# ==================================================

def convert_value(value):
    """Convert Pandas and NumPy values into JSON-compatible values."""

    if value is None:
        return None

    if isinstance(value, (list, dict)):
        return value

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if hasattr(value, "item"):
        value = value.item()

    return value


def convert_records(dataframe, allowed_columns, nullable_columns=None):
    """Convert DataFrame rows into contract-compatible JSON records."""

    nullable_columns = nullable_columns or []

    records = []

    for record in dataframe.to_dict(orient="records"):

        normalized_record = {}

        for column in allowed_columns:

            if column not in record:
                continue

            value = convert_value(record[column])

            if (
                column in nullable_columns
                and isinstance(value, str)
                and value.strip() == ""
            ):
                value = None

            normalized_record[column] = value

        records.append(normalized_record)

    return records


# ==================================================
# 2. VALIDATION ISSUE CONVERSION
# ==================================================

def convert_validation_issues(validation_result, datasets):
    """Convert validation issues into the output schema format."""

    converted_issues = []

    for issue in validation_result.get("issues", []):

        dataset_name = issue.get("dataset", "unknown")
        column = issue.get("column")
        row_number = issue.get("row_number")

        record_id = None

        if (
            dataset_name in datasets
            and row_number is not None
        ):

            dataframe = datasets[dataset_name]
            dataframe_index = row_number - 2

            id_column = {
                "candidates": "candidate_id",
                "jobs": "job_id",
                "applications": "candidate_id",
                "activity": "candidate_id",
            }.get(dataset_name)

            if (
                id_column
                and id_column in dataframe.columns
                and 0 <= dataframe_index < len(dataframe)
            ):
                record_id = str(
                    dataframe.iloc[dataframe_index][id_column]
                )

        raw_value = issue.get("value")

        if raw_value is not None:
            raw_value = str(raw_value)

        converted_issues.append({
            "record_type": dataset_name,
            "record_id": record_id,
            "field": column,
            "issue_code": issue.get("issue", "unknown_issue"),
            "message": issue.get(
                "details",
                "Validation issue."
            ),
            "severity": issue.get("severity", "error"),
            "raw_value": raw_value,
        })

    return converted_issues


def build_error_list(validation_issues):
    """Build the top-level errors array using blocking errors only."""

    errors = []

    for issue in validation_issues:

        if issue["severity"] != "error":
            continue

        errors.append({
            "code": issue["issue_code"],
            "message": issue["message"],
            "record_id": issue["record_id"],
            "field": issue["field"],
        })

    return errors


# ==================================================
# 3. DUPLICATE REVIEW
# ==================================================

def load_duplicate_review(project_root):
    """Load duplicate pairs and initialize their status as Pending."""

    review_path = (
        Path(project_root)
        / "outputs"
        / "data_preparation"
        / "duplicate_review.csv"
    )

    if not review_path.exists():
        print("Duplicate review file not found. Using empty list.")
        return []

    dataframe = pd.read_csv(
        review_path,
        dtype=str,
        encoding="utf-8-sig",
        keep_default_na=False
    )

    required_columns = [
        "candidate_id_1",
        "candidate_id_2",
        "reason",
    ]

    missing_columns = [
        column for column in required_columns
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Duplicate review CSV is missing columns: {missing_columns}"
        )

    duplicate_records = []

    for _, row in dataframe.iterrows():

        duplicate_records.append({
            "candidate_id_1": row["candidate_id_1"].strip(),
            "candidate_id_2": row["candidate_id_2"].strip(),
            "reason": row["reason"].strip(),
            "review_status": "Pending",
        })

    return duplicate_records


# ==================================================
# 4. MISSING VALUE COUNTS
# ==================================================

def count_missing_values(datasets):
    """Count total missing cells for each dataset."""

    missing_counts = {}

    for dataset_name, dataframe in datasets.items():

        total_missing = 0

        for column in dataframe.columns:

            missing_mask = (
                dataframe[column].isna()
                | dataframe[column].astype(str).str.strip().eq("")
            )

            total_missing += int(missing_mask.sum())

        missing_counts[dataset_name] = total_missing

    return missing_counts


# ==================================================
# 5. PROCESSING METADATA
# ==================================================

def build_processing_metadata(
    input_datasets,
    normalized_datasets
):
    """Build processing counts required by the output schema."""

    required_input_names = [
        "candidates",
        "jobs",
        "applications",
        "activity",
        "skill_dictionary",
    ]

    required_output_names = [
        "candidates",
        "jobs",
        "applications",
        "activity",
    ]

    missing_input = [
        name for name in required_input_names
        if name not in input_datasets
    ]

    missing_output = [
        name for name in required_output_names
        if name not in normalized_datasets
    ]

    if missing_input:
        raise KeyError(
            f"Missing input datasets: {missing_input}"
        )

    if missing_output:
        raise KeyError(
            f"Missing normalized datasets: {missing_output}"
        )

    input_counts = {
        name: len(input_datasets[name])
        for name in required_input_names
    }

    output_counts = {
        name: len(normalized_datasets[name])
        for name in required_output_names
    }

    return {
        "input_record_counts": input_counts,
        "output_record_counts": output_counts,
        "missing_value_counts": count_missing_values(
            input_datasets
        ),
    }


# ==================================================
# 6. BUILD CONTRACT OUTPUT
# ==================================================

def build_contract_output(
    normalized_datasets,
    validation_result,
    duplicate_review,
    input_datasets,
):
    """Build the final JSON object following output.schema.json."""

    validation_issues = convert_validation_issues(
        validation_result,
        input_datasets
    )

    total_errors = sum(
        1 for issue in validation_issues
        if issue["severity"] == "error"
    )

    total_warnings = sum(
        1 for issue in validation_issues
        if issue["severity"] == "warning"
    )

    if total_errors > 0:
        status = "failed"
    elif total_warnings > 0:
        status = "partial_success"
    else:
        status = "success"

    # CANDIDATES

    candidates = convert_records(
        normalized_datasets["candidates"],
        [
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
        ],
        nullable_columns=[
            "email",
            "phone",
            "location",
            "experience_years",
            "education",
            "source",
            "application_date",
        ],
    )

    # JOBS

    jobs = convert_records(
        normalized_datasets["jobs"],
        [
            "job_id",
            "role",
            "required_skills",
            "min_experience",
            "max_experience",
        ],
    )

    # APPLICATIONS

    applications = convert_records(
        normalized_datasets["applications"],
        [
            "candidate_id",
            "job_id",
            "stage",
            "stage_date",
            "recruiter_id",
        ],
        nullable_columns=["recruiter_id"],
    )

    # ACTIVITY

    activity = convert_records(
        normalized_datasets["activity"],
        [
            "candidate_id",
            "event_type",
            "event_date",
        ],
    )

    processing_metadata = build_processing_metadata(
        input_datasets,
        normalized_datasets
    )

    errors = build_error_list(validation_issues)

    return {
        "module": "data_preparation",
        "schema_version": "0.1",
        "run_id": str(uuid.uuid4()),
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),

        "data": {
            "candidates": candidates,
            "jobs": jobs,
            "applications": applications,
            "activity": activity,
            "validation_issues": validation_issues,
            "duplicate_review_candidates": duplicate_review,
            "processing_metadata": processing_metadata,
        },

        "summary": {
            "candidate_count": len(candidates),
            "job_count": len(jobs),
            "application_count": len(applications),
            "activity_count": len(activity),
            "error_count": total_errors,
            "warning_count": total_warnings,
            "possible_duplicate_pair_count": len(
                duplicate_review
            ),
        },

        "errors": errors,
    }


# ==================================================
# 7. JSON SCHEMA VALIDATION
# ==================================================

def validate_output_schema(output_data, project_root):
    """Validate JSON against the project output schema."""

    schema_path = (
        Path(project_root)
        / "contracts"
        / "data_preparation"
        / "output.schema.json"
    )

    if not schema_path.is_file():
        raise FileNotFoundError(
            f"Output schema not found: {schema_path}"
        )

    with schema_path.open("r", encoding="utf-8") as file:
        schema = json.load(file)

    validator = Draft202012Validator(
        schema,
        format_checker=FormatChecker()
    )

    validation_errors = sorted(
        validator.iter_errors(output_data),
        key=lambda error: list(error.absolute_path)
    )

    if validation_errors:

        print("\nJSON SCHEMA VALIDATION FAILED")
        print("-----------------------------")

        for error in validation_errors:

            location = ".".join(
                str(part)
                for part in error.absolute_path
            )

            print(f"Location: {location or 'root'}")
            print(f"Problem: {error.message}")

        raise ValueError(
            f"Generated JSON has {len(validation_errors)} schema errors."
        )

    print("\nJSON SCHEMA VALIDATION PASSED")


# ==================================================
# 8. CSV EXPORT - FIXED FILENAMES
# ==================================================

def export_processed_csv(normalized_datasets, project_root):
    """Overwrite the official processed CSV files."""

    output_directory = (
        Path(project_root) / "data" / "processed"
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=True
    )

    export_names = [
        "candidates",
        "jobs",
        "applications",
        "activity",
    ]

    for dataset_name in export_names:

        if dataset_name not in normalized_datasets:
            raise KeyError(
                f"Missing normalized dataset: {dataset_name}"
            )

    output_paths = {
        dataset_name: (
            output_directory / f"{dataset_name}_cleaned.csv"
        )
        for dataset_name in export_names
    }

    for dataset_name in export_names:

        output_path = output_paths[dataset_name]

        normalized_datasets[dataset_name].to_csv(
            output_path,
            index=False,
            encoding="utf-8"
        )

        print(
            f"Updated CSV: {output_path.name} "
            f"({len(normalized_datasets[dataset_name])} records)"
        )


# ==================================================
# 9. JSON EXPORT - FIXED FILENAME
# ==================================================

def export_contract_json(output_data, project_root):
    """Validate and overwrite the official normalized JSON file."""

    output_directory = (
        Path(project_root)
        / "outputs"
        / "data_preparation"
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=True
    )

    output_path = output_directory / "normalized_data.json"

    # Validate the new JSON before writing it.
    validate_output_schema(
        output_data,
        project_root
    )

    # Write to a temporary file first.
    temporary_path = output_directory / "normalized_data.tmp"

    try:
        with temporary_path.open(
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                output_data,
                file,
                indent=4,
                ensure_ascii=False,
                allow_nan=False
            )

        # Replace the official JSON only after writing succeeds.
        temporary_path.replace(output_path)

    finally:
        if temporary_path.exists():
            temporary_path.unlink()

    print(f"Updated contract JSON: {output_path.name}")

    return output_path


# ==================================================
# 10. MAIN EXPORT FUNCTION
# ==================================================

def export_datasets(
    normalized_datasets,
    project_root=None,
    validation_result=None,
    input_datasets=None,
):
    """Export official processed CSV and JSON files."""

    if project_root is None:
        project_root = Path(__file__).resolve().parents[2]
    else:
        project_root = Path(project_root)

    if validation_result is None:
        raise ValueError(
            "validation_result must be provided."
        )

    if input_datasets is None:
        raise ValueError(
            "input_datasets must be provided."
        )

    print("\nSTEP 5: EXPORTING DATA")

    print("\nLOADING DUPLICATE REVIEW")

    duplicate_review = load_duplicate_review(
        project_root
    )

    print(
        "Duplicate pairs awaiting review: "
        f"{len(duplicate_review)}"
    )

    print("\nBUILDING CONTRACT OUTPUT")

    output_data = build_contract_output(
        normalized_datasets,
        validation_result,
        duplicate_review,
        input_datasets,
    )

    # Validate the JSON before updating any official files.
    print("\nVALIDATING CONTRACT OUTPUT")

    validate_output_schema(
        output_data,
        project_root
    )

    print("\nEXPORTING PROCESSED CSV FILES")
    print("-----------------------------")

    export_processed_csv(
        normalized_datasets,
        project_root
    )

    print("\nEXPORTING CONTRACT JSON")
    print("-----------------------")

    export_contract_json(
        output_data,
        project_root
    )

    print("\nDATA EXPORT COMPLETED")
    print("---------------------")

    return output_data


# ==================================================
# 11. DIRECT EXECUTION
# ==================================================

if __name__ == "__main__":

    from modules.data_preparation.processor import run_pipeline

    project_root = Path(__file__).resolve().parents[2]

    results = run_pipeline(project_root)

    export_datasets(
        normalized_datasets=results["normalized_datasets"],
        project_root=project_root,
        validation_result=results["validation"],
        input_datasets=results["cleaned_datasets"],
    )
