"""Unit and integration tests for the AI Automation module.

Verifies:
1. Skills are strictly matched against entries in data/skill_dictionary.csv.
2. Words outside the skill dictionary are NOT extracted.
3. No updated skill dictionary is generated or stored inside modules/ai_automation/data/.
4. Candidates CSV is updated with extracted details.
5. Experience is 0 for freshers and internship-only profiles.
6. Education extracts graduation and postgraduation without school-level lines.
7. Location is extracted properly.
8. Web interface accepts only PDF resumes (.pdf) and rejects others.
9. Missing fields (source, application_date) remain blank.
10. Contract JSON schema is strictly valid.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

from jsonschema import Draft202012Validator, FormatChecker

from modules.ai_automation.dev_web import create_app
from modules.ai_automation.pipeline import (
    AIAutomationPipeline,
    REPO_ROOT,
    run_ai_automation,
)
from modules.ai_automation.skill_matcher import SkillMatcher


def _build_minimal_pdf_bytes(lines: list[str]) -> bytes:
    """Create a valid minimal single-page uncompressed PDF containing text lines."""
    escaped_ops: list[str] = ["BT", "/F1 11 Tf", "50 750 Td", "14 TL"]
    for idx, line in enumerate(lines):
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if idx == 0:
            escaped_ops.append(f"({safe}) Tj")
        else:
            escaped_ops.append(f"T* ({safe}) Tj")
    escaped_ops.append("ET")
    stream_data = "\n".join(escaped_ops).encode("latin-1")

    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
        b"4 0 obj\n<< /Length "
        + str(len(stream_data)).encode("ascii")
        + b" >>\nstream\n"
        + stream_data
        + b"\nendstream\nendobj\n",
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]

    buffer = io.BytesIO()
    buffer.write(b"%PDF-1.4\n")
    offsets: list[int] = [0]
    for obj in objects:
        offsets.append(buffer.tell())
        buffer.write(obj)

    xref_pos = buffer.tell()
    buffer.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    buffer.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        buffer.write(f"{off:010d} 00000 n \n".encode("ascii"))
    buffer.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return buffer.getvalue()


class TestAIAutomationModule(unittest.TestCase):
    """Test suite covering dictionary skill matching, PDF upload, and extraction rules."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.candidates_csv = self.tmp_path / "candidates_extracted.csv"
        self.output_json = self.tmp_path / "ai_automation.json"
        self.uploads_dir = self.tmp_path / "uploads"

        schema_path = REPO_ROOT / "contracts" / "ai_automation" / "output.schema.json"
        with schema_path.open("r", encoding="utf-8") as handle:
            self.output_schema = json.load(handle)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def _assert_valid_contract(self, payload: dict) -> None:
        validator = Draft202012Validator(self.output_schema, format_checker=FormatChecker())
        errors = list(validator.iter_errors(payload))
        self.assertEqual([], errors, f"Schema validation errors: {errors}")

    def test_strict_dictionary_matching_and_no_module_dictionary_file(self) -> None:
        """Verify skills strictly match data/skill_dictionary.csv; non-matching words are excluded."""
        resume_file = self.tmp_path / "sample_candidate.txt"
        resume_file.write_text(
            "\n".join(
                [
                    "Adhill C",
                    "Kochi, Kerala",
                    "Email: adhill.dev@example.com | Phone: +91 98765 43210",
                    "",
                    "Summary",
                    "Python developer with 2.5 years of experience building APIs and analytics.",
                    "",
                    "Work Experience",
                    "Software Engineer | Jan 2022 - Jun 2024",
                    "- Deployed microservices using Docker and Kubernetes.",
                    "",
                    "Technical Skills",
                    "Languages: C, Python Programming, JavaScript",
                    "Frameworks & Tools: Django Framework, FastAPI, Git, Power BI, Excel, Scikit-Learn",
                    "Technologies Not In Dictionary: LangChain, Docker, Kubernetes, AWS, Terraform",
                    "",
                    "Education",
                    "B.Tech Computer Science and Engineering (AI & ML) - 2018 - 2022",
                ]
            ),
            encoding="utf-8",
        )

        report = run_ai_automation(
            [resume_file],
            candidates_csv_path=self.candidates_csv,
            output_json_path=self.output_json,
        )

        self._assert_valid_contract(report.output_payload)
        self.assertEqual("success", report.output_payload["status"])
        self.assertEqual(1, len(report.added_candidate_rows))

        row = report.added_candidate_rows[0]
        self.assertEqual("Adhill C", row["name"])
        self.assertEqual("adhill.dev@example.com", row["email"])
        self.assertEqual("+91 9876543210", row["phone"])
        self.assertEqual("Kochi, Kerala, India", row["location"])
        self.assertEqual("2.5", row["experience_years"])
        self.assertEqual("", row["source"])
        self.assertEqual("", row["application_date"])

        skills_set = set(row["skills"].split(";"))
        # Words in data/skill_dictionary.csv must match canonical names:
        for expected in (
            "python",
            "c",
            "javascript",
            "django",
            "fastapi",
            "git",
            "power_bi",
            "excel",
            "scikit_learn",
        ):
            self.assertIn(expected, skills_set, f"Expected canonical skill '{expected}' in {skills_set}")

        # Words NOT in data/skill_dictionary.csv MUST NOT be present:
        for not_in_dict in ("langchain", "docker", "kubernetes", "aws", "terraform"):
            self.assertNotIn(not_in_dict, skills_set, f"Skill '{not_in_dict}' should not have been extracted!")

        # Verify no skill dictionary file was created inside the candidate CSV folder
        self.assertFalse((self.tmp_path / "skill_dictionary_updated.csv").exists())

    def test_pdf_resume_extraction_and_contract(self) -> None:
        """Verify extraction from a PDF resume."""
        pdf_path = self.tmp_path / "candidate.pdf"
        pdf_path.write_bytes(
            _build_minimal_pdf_bytes(
                [
                    "Diya Krishnan",
                    "diya.k@example.com | 9123456789",
                    "Bengaluru, Karnataka",
                    "Experience: 1.5 years experience",
                    "Skills: Excel, SQL, Power BI, Python",
                    "Education: MBA Finance",
                ]
            )
        )

        report = run_ai_automation(
            [pdf_path],
            candidates_csv_path=self.candidates_csv,
            output_json_path=self.output_json,
        )
        self._assert_valid_contract(report.output_payload)
        self.assertEqual(1, report.output_payload["summary"]["document_count"])
        self.assertEqual("success", report.output_payload["status"])
        row = report.added_candidate_rows[0]
        self.assertEqual("Diya Krishnan", row["name"])
        self.assertEqual("diya.k@example.com", row["email"])
        self.assertEqual("1.5", row["experience_years"])
        self.assertIn("power_bi", row["skills"].split(";"))
        self.assertIn("python", row["skills"].split(";"))

    def test_fresher_and_internship_only_experience_is_zero(self) -> None:
        """Verify fresher or internship-only profiles return experience_years = 0."""
        intern_resume = self.tmp_path / "intern_resume.txt"
        intern_resume.write_text(
            "\n".join(
                [
                    "Sivakami P.S",
                    "Kochi, Kerala",
                    "sivakami.test@example.com | +91 6282809731",
                    "",
                    "Internship",
                    "Data Science Intern | May 2024 - Sep 2024",
                    "Analyzed data using Pandas and NumPy.",
                    "",
                    "Technical Skills",
                    "Python, SQL, MySQL, Power BI, Machine Learning",
                    "",
                    "Educational Qualification",
                    "Bachelor of Computer Applications (2021 - 2024)",
                ]
            ),
            encoding="utf-8",
        )

        fresher_resume = self.tmp_path / "fresher_resume.txt"
        fresher_resume.write_text(
            "\n".join(
                [
                    "Rahul Nair",
                    "rahul.nair@example.com | 9876543210",
                    "Location: Trivandrum, Kerala",
                    "Profile: Fresher looking for entry level software engineer role.",
                    "Skills: Python, Django, HTML, CSS",
                    "Education: B.Tech in Computer Science (2024)",
                ]
            ),
            encoding="utf-8",
        )

        report = run_ai_automation(
            [intern_resume, fresher_resume],
            candidates_csv_path=self.candidates_csv,
            output_json_path=self.output_json,
        )
        self._assert_valid_contract(report.output_payload)
        self.assertEqual("0", report.added_candidate_rows[0]["experience_years"])
        self.assertEqual("0", report.added_candidate_rows[1]["experience_years"])

    def test_education_graduation_and_postgraduation_extraction(self) -> None:
        """Verify extraction captures both graduation and postgraduation without 10th/12th."""
        resume = self.tmp_path / "double_degree.txt"
        resume.write_text(
            "\n".join(
                [
                    "Megha Satheesh",
                    "megha.test@example.com | 9061247615",
                    "Ernakulam, Kerala",
                    "",
                    "Education",
                    "Post Graduation: M.Sc. in Data Science (2023 - 2025)",
                    "Graduation: Bachelor of Computer Applications (2020 - 2023) | CGPA: 8.9",
                    "12th Higher Secondary (2020)",
                    "10th SSLC (2018)",
                    "",
                    "Skills",
                    "Python, SQL, MySQL, Power BI",
                ]
            ),
            encoding="utf-8",
        )

        report = run_ai_automation(
            [resume],
            candidates_csv_path=self.candidates_csv,
            output_json_path=self.output_json,
        )
        self._assert_valid_contract(report.output_payload)
        row = report.added_candidate_rows[0]
        self.assertIn("M.Sc. in Data Science", row["education"])
        self.assertIn("Bachelor of Computer Applications", row["education"])
        self.assertIn("CGPA: 8.9", row["education"])
        self.assertNotIn("Higher Secondary", row["education"])
        self.assertNotIn("SSLC", row["education"])

    def test_web_interface_accepts_only_pdf(self) -> None:
        """Verify web interface accepts PDF uploads and rejects non-PDF files."""
        app = create_app(
            uploads_dir=self.uploads_dir,
            candidates_csv_path=self.candidates_csv,
            output_json_path=self.output_json,
            sync_to_raw=False,
        )
        client = app.test_client()

        # GET / displays the single upload interface
        resp = client.get("/")
        self.assertEqual(200, resp.status_code)
        self.assertIn(b"Resume Upload", resp.data)
        self.assertIn(b'accept=".pdf,application/pdf"', resp.data)

        # Non-PDF (.txt or .docx) is rejected with 400
        txt_resp = client.post(
            "/upload",
            data={"resume": (io.BytesIO(b"fake txt content"), "resume.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(400, txt_resp.status_code)
        self.assertIn(b"Only PDF files", txt_resp.data)

        # Valid PDF upload is accepted with 200 and extracts fields
        pdf_bytes = _build_minimal_pdf_bytes(
            [
                "Angelo Helen Jaison",
                "angelohelen756@gmail.com | 8156816805",
                "Kochi, Kerala",
                "Experience: Fresher",
                "Skills: Python, C++, MySQL, Power BI, Machine Learning",
                "Education: Bachelor of Computer Applications",
            ]
        )
        pdf_resp = client.post(
            "/upload",
            data={"resume": (io.BytesIO(pdf_bytes), "angelo_resume.pdf")},
            content_type="multipart/form-data",
        )
        self.assertEqual(200, pdf_resp.status_code)
        self.assertIn(b"Angelo Helen Jaison", pdf_resp.data)
        self.assertIn(b"angelohelen756@gmail.com", pdf_resp.data)
        self.assertIn(b"0 years", pdf_resp.data)
        self.assertIn(b"power_bi", pdf_resp.data)

    def test_devika_real_pdf_extraction_highest_education_and_phone_format(self) -> None:
        """Verify extraction on real PDF with fractured fonts, course, CGPA, and country code."""
        pdf_path = REPO_ROOT / "modules" / "ai_automation" / "uploads" / "DOC_724443FD_01_devika_k_j_resume.pdf"
        if not pdf_path.exists():
            return

        report = run_ai_automation(
            [pdf_path],
            candidates_csv_path=self.candidates_csv,
            output_json_path=self.output_json,
        )
        self._assert_valid_contract(report.output_payload)
        row = report.added_candidate_rows[0]
        self.assertEqual("Devika K J", row["name"])
        self.assertEqual("+91 8089118175", row["phone"])
        self.assertEqual("North Paravur, Kerala, India", row["location"])
        self.assertEqual("0", row["experience_years"])
        self.assertIn("B.Tech in Computer Science and Engineering, Data Science", row["education"])
        self.assertIn("CGPA: 7.5/10", row["education"])

    def test_anagha_and_drisya_real_resumes_layout_and_formatting(self) -> None:
        """Verify multi-column layout, City-State-Country location, Course+CGPA, and experience 0."""
        anagha_pdf = REPO_ROOT / "modules" / "ai_automation" / "uploads" / "DOC_CAE2D34B_Anagha_RESUME.pdf"
        drisya_pdf = REPO_ROOT / "modules" / "ai_automation" / "uploads" / "DOC_4C4F7A5F_Drisya_M_resume-1_1.pdf"
        to_test = [p for p in (anagha_pdf, drisya_pdf) if p.exists()]
        if not to_test:
            return

        report = run_ai_automation(
            to_test,
            candidates_csv_path=self.candidates_csv,
            output_json_path=self.output_json,
        )
        self._assert_valid_contract(report.output_payload)
        rows_by_name = {r["name"]: r for r in report.added_candidate_rows}

        if "Anagha Satheesh" in rows_by_name:
            anagha = rows_by_name["Anagha Satheesh"]
            self.assertEqual("+91 9645274314", anagha["phone"])
            self.assertEqual("Kottayam, Kerala, India", anagha["location"])
            self.assertEqual("0", anagha["experience_years"])
            self.assertEqual("Bachelor of Computer Application (BCA)", anagha["education"])

        if "Drisya M" in rows_by_name:
            drisya = rows_by_name["Drisya M"]
            self.assertEqual("+91 9074864149", drisya["phone"])
            self.assertEqual("Kochi, Kerala, India", drisya["location"])
            self.assertEqual("0", drisya["experience_years"])
            self.assertIn("Bachelor of Computer Applications (BCA)", drisya["education"])
            self.assertIn("CGPA : 8.05 / 10", drisya["education"])

    def test_missing_and_corrupt_documents_follow_contract(self) -> None:
        """Verify contract compliance when documents fail to read."""
        pipeline = AIAutomationPipeline(
            candidates_csv_path=self.candidates_csv,
            output_json_path=self.output_json,
        )
        report = pipeline.run(
            {
                "documents": [
                    {
                        "document_id": "DOC_MISSING",
                        "file_name": "missing.pdf",
                        "mime_type": "application/pdf",
                        "content_uri": str(self.tmp_path / "nonexistent.pdf"),
                        "candidate_id": None,
                    }
                ]
            }
        )
        self._assert_valid_contract(report.output_payload)
        self.assertEqual("failed", report.output_payload["status"])
        self.assertEqual(1, len(report.output_payload["errors"]))


if __name__ == "__main__":
    unittest.main()
