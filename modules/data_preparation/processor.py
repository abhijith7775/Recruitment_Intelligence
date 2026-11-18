
from pathlib import Path

from modules.data_preparation.loader import load_input_data
from modules.data_preparation.validator import run_validation
from modules.data_preparation.cleaner import clean_datasets
from modules.data_preparation.normalizer import normalize_datasets


def run_pipeline(project_root=None):
    """
    Execute the complete Data Preparation pipeline.

    Workflow:
    1. Load raw datasets.
    2. Validate raw datasets.
    3. Stop if blocking errors exist.
    4. Clean datasets.
    5. Normalize datasets.
    6. Return the processing results.

    This function does not modify raw CSV files or write output files.
    """

    print("\nDATA PREPARATION PIPELINE")
    print("=========================")

    # Step 1: Load datasets
    print("\nSTEP 1: LOADING DATA")

    raw_datasets = load_input_data(project_root)

    # Step 2: Validate datasets
    print("\nSTEP 2: VALIDATING DATA")

    validation_result = run_validation(raw_datasets)

    summary = validation_result["summary"]

    print("\nVALIDATION SUMMARY")
    print("------------------")
    print("Total Errors:", summary["total_errors"])
    print("Total Warnings:", summary["total_warnings"])
    print("Total Issues:", summary["total_issues"])

    # Stop processing if blocking errors exist.
    if summary["total_errors"] > 0:
        raise ValueError(
            "Data preparation stopped because blocking validation "
            "errors were found."
        )

    # Step 3: Clean datasets
    print("\nSTEP 3: CLEANING DATA")

    cleaned_datasets = clean_datasets(raw_datasets)

    # Step 4: Normalize datasets
    print("\nSTEP 4: NORMALIZING DATA")

    normalized_datasets = normalize_datasets(cleaned_datasets)

    print("\nDATA PREPARATION PIPELINE COMPLETED")
    print("-----------------------------------")

    return {
        "status": "completed",
        "validation": validation_result,
        "cleaned_datasets": cleaned_datasets,
        "normalized_datasets": normalized_datasets,
    }


if __name__ == "__main__":

    results = run_pipeline()

    print("\nFINAL DATASET COUNTS")
    print("--------------------")

    for name, dataframe in results["normalized_datasets"].items():
        print(f"{name}: {len(dataframe)} records")
