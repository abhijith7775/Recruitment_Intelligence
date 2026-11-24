# AI Automation Module

Resume PDF extraction, strict skill matching against the project dictionary, and minimal single-purpose upload interface for **Recruitment Intelligence**.

## Architecture & Responsibilities

- **Sole Skill Dictionary Source:**
  - Reads `data/skill_dictionary.csv` directly as the single source of truth.
  - Matches resume words (prioritizing the skills area) strictly against entries in this dictionary.
  - Words/technologies not in `data/skill_dictionary.csv` are **not** extracted.
  - No separate skill dictionary is created or stored inside `modules/ai_automation/data/`.
- **Candidate Field Extraction:**
  - `name`: Candidate's name.
  - `email`: Normalized email address.
  - `phone`: Standardized telephone number.
  - `location`: Candidate's location (city, state).
  - `experience_years`: Automatically set to `0` for freshers and candidates with only internships/training. Full-time work experience is calculated when present.
  - `education`: Captures graduation and postgraduation qualifications (e.g. B.Tech, M.Sc, BCA, MCA) while excluding school-level lines.
  - `skills`: Semicolon-separated canonical skill names strictly matched from `data/skill_dictionary.csv`.
  - Unavailable fields (`source`, `application_date`, `role`): Left blank without fabrication.
- **CSV Data Updates:**
  - Appends records to `modules/ai_automation/data/candidates_extracted.csv`.
  - Also updates `data/raw/candidates.csv` so other team modules have immediate access to newly uploaded candidates.
- **Contract Compliance:**
  - Emits JSON envelope validated against `contracts/ai_automation/output.schema.json` to `modules/ai_automation/outputs/ai_automation.json`.

## Module Files

- `document_reader.py`: Robust text extraction from `.pdf` resumes (via `pypdf` with fallback).
- `skill_matcher.py`: Fast, deterministic matcher against `data/skill_dictionary.csv`.
- `extractor.py`: Extracts name, contact, location, experience (0 for freshers/interns), education, and skills.
- `pipeline.py`: Coordinates document reading, field extraction, CSV appending, and schema-validated JSON emission.
- `dev_web.py`: Minimal Flask web server hosting the single upload interface.
- `templates/upload.html`: Clean single interface containing only a PDF file upload and extracted candidate feedback.
- `tests/test_ai_automation.py`: Complete automated test suite covering all functional rules and edge cases.

## How to Run

### 1. Run the Single PDF Upload Web Page

Run in PowerShell using Python 3.12:

```powershell
py -3.12 modules/ai_automation/dev_web.py
```

Then open `http://127.0.0.1:5000/` in your browser.

- Select or drop any candidate resume in PDF format (`.pdf`).
- Click **Upload & Extract Resume**.
- The candidate details are extracted, added to the CSV files, and displayed in the verification card.

### 2. Run the CLI Pipeline Directly

```powershell
py -3.12 -m modules.ai_automation.pipeline path\to\resume.pdf
```

### 3. Run Automated Tests

```powershell
py -3.12 -m unittest discover -s modules/ai_automation/tests -v
```
