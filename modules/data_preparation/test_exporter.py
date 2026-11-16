
from pathlib import Path

from modules.data_preparation.processor import run_pipeline
from modules.data_preparation.exporter import export_datasets


def main():

    project_root = Path(__file__).resolve().parents[2]

    results = run_pipeline(project_root)

    print("\nSTEP 5: EXPORTING DATA")

    output_data = export_datasets(
        normalized_datasets=results["normalized_datasets"],
        project_root=project_root,
        validation_result=results["validation"],
        input_datasets=results["cleaned_datasets"],
    )

    print("\nEXPORT SUMMARY")
    print("--------------")
    print("Module:", output_data["module"])
    print("Schema version:", output_data["schema_version"])
    print("Status:", output_data["status"])
    print("Candidates:", output_data["summary"]["candidate_count"])
    print("Jobs:", output_data["summary"]["job_count"])
    print("Applications:", output_data["summary"]["application_count"])
    print("Activity:", output_data["summary"]["activity_count"])
    print("Warnings:", output_data["summary"]["warning_count"])
    print(
        "Duplicate review pairs:",
        output_data["summary"]["possible_duplicate_pair_count"]
    )

    print("\nEXPORT TEST COMPLETED")


if __name__ == "__main__":
    main()
