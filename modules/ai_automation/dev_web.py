"""Single-purpose resume PDF upload web interface for AI Automation.

Provides a clean, minimal interface exclusively for uploading PDF resumes.
Extracted candidate information is appended directly to the candidate CSV files
and contract JSON output.
"""

from __future__ import annotations

import os
from pathlib import Path
import uuid

import sys

from flask import Flask, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from modules.ai_automation.document_reader import infer_mime_type
    from modules.ai_automation.pipeline import (
        AIAutomationPipeline,
        DEFAULT_CANDIDATES_CSV_PATH,
        DEFAULT_OUTPUT_JSON_PATH,
        MODULE_DIR,
        REPO_ROOT,
    )
else:
    from .document_reader import infer_mime_type
    from .pipeline import (
        AIAutomationPipeline,
        DEFAULT_CANDIDATES_CSV_PATH,
        DEFAULT_OUTPUT_JSON_PATH,
        MODULE_DIR,
        REPO_ROOT,
    )


DEFAULT_UPLOADS_DIR = MODULE_DIR / "uploads"
ALLOWED_EXTENSIONS = {".pdf"}


def create_app(
    *,
    repo_root: Path = REPO_ROOT,
    uploads_dir: Path = DEFAULT_UPLOADS_DIR,
    candidates_csv_path: Path = DEFAULT_CANDIDATES_CSV_PATH,
    output_json_path: Path = DEFAULT_OUTPUT_JSON_PATH,
    sync_to_raw: bool = True,
) -> Flask:
    """Create and configure the minimal resume upload web app."""
    app = Flask(__name__, template_folder=str(MODULE_DIR / "templates"))
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max upload
    app.config["TEMPLATES_AUTO_RELOAD"] = True

    uploads_dir.mkdir(parents=True, exist_ok=True)

    @app.get("/")
    def index():
        return render_template("upload.html")

    @app.post("/upload")
    @app.post("/")
    def upload_resume():
        file = request.files.get("resume") or request.files.get("file")
        if not file or not file.filename:
            return (
                render_template(
                    "upload.html",
                    error_message="Please choose a PDF resume file to upload.",
                ),
                400,
            )

        clean_name = secure_filename(file.filename or "")
        ext = Path(clean_name).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            return (
                render_template(
                    "upload.html",
                    error_message=f"Only PDF files (.pdf) are supported. Received '{clean_name}'.",
                ),
                400,
            )

        doc_id = f"DOC_{uuid.uuid4().hex[:8].upper()}"
        saved_path = uploads_dir / f"{doc_id}_{clean_name}"
        file.save(saved_path)

        pipeline = AIAutomationPipeline(
            repo_root=repo_root,
            candidates_csv_path=candidates_csv_path,
            output_json_path=output_json_path,
            sync_to_raw=sync_to_raw,
        )

        try:
            report = pipeline.run(
                {
                    "documents": [
                        {
                            "document_id": doc_id,
                            "file_name": clean_name,
                            "mime_type": "application/pdf",
                            "content_uri": str(saved_path),
                        }
                    ]
                },
                base_dir=uploads_dir,
                append_to_csv=True,
            )
        except Exception as exc:
            return (
                render_template(
                    "upload.html",
                    error_message=f"Extraction failed: {exc}",
                ),
                500,
            )

        if report.output_payload.get("errors") and not report.added_candidate_rows:
            err_msg = report.output_payload["errors"][0]["message"]
            return render_template("upload.html", error_message=err_msg), 400

        added_row = report.added_candidate_rows[0] if report.added_candidate_rows else {}
        skills_str = added_row.get("skills", "")
        skills_list = [s.strip() for s in skills_str.split(";") if s.strip()]

        extracted_candidate = {
            "candidate_id": added_row.get("candidate_id", ""),
            "name": added_row.get("name", ""),
            "email": added_row.get("email", ""),
            "phone": added_row.get("phone", ""),
            "location": added_row.get("location", ""),
            "experience_years": added_row.get("experience_years", ""),
            "education": added_row.get("education", ""),
            "skills_list": skills_list,
        }

        success_msg = f"Resume '{clean_name}' successfully processed and added to candidate CSV."
        return render_template(
            "upload.html",
            success_message=success_msg,
            extracted_candidate=extracted_candidate,
        )

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Resume Upload Interface at http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
