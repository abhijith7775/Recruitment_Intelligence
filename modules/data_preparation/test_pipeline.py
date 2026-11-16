
import unittest
from pathlib import Path

from modules.data_preparation.processor import run_pipeline
from modules.data_preparation.exporter import (
    build_contract_output,
    load_duplicate_review,
    validate_output_schema,
)


class TestDataPreparationPipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.project_root = Path(__file__).resolve().parents[2]
        cls.results = run_pipeline(cls.project_root)

        cls.raw_datasets = cls.results["raw_datasets"] if (
            "raw_datasets" in cls.results
        ) else cls.results["cleaned_datasets"]

        cls.cleaned_datasets = cls.results["cleaned_datasets"]
        cls.normalized_datasets = cls.results["normalized_datasets"]
        cls.validation = cls.results["validation"]

    def test_pipeline_completed(self):
        self.assertEqual(self.results["status"], "completed")

    def test_candidate_record_count(self):
        self.assertEqual(
            len(self.normalized_datasets["candidates"]), 73
        )

    def test_job_record_count(self):
        self.assertEqual(
            len(self.normalized_datasets["jobs"]), 2
        )

    def test_application_record_count(self):
        self.assertEqual(
            len(self.normalized_datasets["applications"]), 29
        )

    def test_activity_record_count(self):
        self.assertEqual(
            len(self.normalized_datasets["activity"]), 79
        )

    def test_skill_dictionary_record_count(self):
        self.assertEqual(
            len(self.cleaned_datasets["skill_dictionary"]), 80
        )

    def test_validation_has_no_errors(self):
        self.assertEqual(
            self.validation["summary"]["total_errors"], 0
        )

    def test_validation_warning_count(self):
        self.assertEqual(
            self.validation["summary"]["total_warnings"], 3
        )

    def test_candidate_skills_are_lists(self):
        for _, candidate in self.normalized_datasets["candidates"].iterrows():
            self.assertIsInstance(candidate["skills"], list)

    def test_job_skills_are_lists(self):
        for _, job in self.normalized_datasets["jobs"].iterrows():
            self.assertIsInstance(job["required_skills"], list)

    def test_application_history_preserved(self):
        self.assertEqual(
            len(self.normalized_datasets["applications"]), 29
        )

    def test_duplicate_review_pairs_are_pending(self):
        duplicates = load_duplicate_review(self.project_root)

        self.assertEqual(len(duplicates), 2)

        for duplicate in duplicates:
            self.assertEqual(
                duplicate["review_status"], "Pending"
            )

    def test_contract_output_schema(self):
        duplicates = load_duplicate_review(self.project_root)

        output = build_contract_output(
            self.normalized_datasets,
            self.validation,
            duplicates,
            self.cleaned_datasets,
        )

        validate_output_schema(output, self.project_root)

    def test_contract_summary_counts(self):
        duplicates = load_duplicate_review(self.project_root)

        output = build_contract_output(
            self.normalized_datasets,
            self.validation,
            duplicates,
            self.cleaned_datasets,
        )

        summary = output["summary"]

        self.assertEqual(summary["candidate_count"], 73)
        self.assertEqual(summary["job_count"], 2)
        self.assertEqual(summary["application_count"], 29)
        self.assertEqual(summary["activity_count"], 79)
        self.assertEqual(summary["error_count"], 0)
        self.assertEqual(summary["warning_count"], 3)
        self.assertEqual(summary["possible_duplicate_pair_count"], 2)

    def test_contract_status(self):
        duplicates = load_duplicate_review(self.project_root)

        output = build_contract_output(
            self.normalized_datasets,
            self.validation,
            duplicates,
            self.cleaned_datasets,
        )

        self.assertEqual(output["status"], "partial_success")


if __name__ == "__main__":
    unittest.main(verbosity=2)
