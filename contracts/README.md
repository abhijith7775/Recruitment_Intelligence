# Recruitment Intelligence — Module Contracts v0.1 (Prototype)

These contracts are a starting point for parallel module development. They are based on the agreed cleaned CSV columns and project rules discussed by the team. They are **prototype contracts**, not a final stable API.

## Contract inventory

- `common/`: normalized candidate, job, application, activity, skill dictionary and common response envelope schemas; raw CSV-row schemas for Data Preparation ingestion.
- Each module directory contains `input.schema.json` and `output.schema.json`.

## Dataset-derived structures

- Candidates: `candidate_id,name,email,phone,location,experience_years,skills,education,source,application_date`
- Jobs: `job_id,role,required_skills,min_experience,max_experience`
- Applications: `candidate_id,job_id,stage,stage_date,recruiter_id`
- Activity: `candidate_id,event_type,event_date`
- Skill dictionary: `original_skill,canonical_skill`

## Representation rules

1. CSV cells arrive as strings. Data Preparation converts numeric/date fields to JSON number/date types.
2. CSV blank optional values become JSON `null` in normalized records.
3. CSV skills are semicolon-separated; normalized JSON skills are arrays of lowercase canonical skill strings.
4. Candidate IDs use `C001` style and job IDs use `J001` style.
5. Application stage values are `New`, `Screened`, `Shortlisted`, `Interviewed`, `Offered`, `Hired`, `Rejected`.
6. Application rows represent stage history. Preserve history; do not collapse rows during ingestion.
7. Activity `event_type` vocabulary is pending team approval. Preserve source values; do not invent an enum.
8. Missing values must not be guessed.
9. Email and phone may support duplicate detection only. They must not be used in candidate-job matching.
10. Duplicate detection flags pairs for human review; it must not merge or delete records.
11. AI-extracted values are unverified suggestions and must not silently overwrite verified candidate records.
12. Matching uses job-related skills and experience only. Do not use name, email, phone, location, source, education or protected/proxy characteristics for scoring.

## Common output envelope

All module outputs use the same outer fields: `module`, `schema_version`, `run_id`, `status`, `created_at`, `data`, `summary`, `errors`. `status` is `success`, `partial_success`, or `failed`. Module-specific results are in `data`.

## Module dependencies

- Data Preparation accepts raw CSV-row payloads and produces normalized records.
- Matching and Duplicate Detection consume normalized candidate/job data as defined in their input contracts.
- AI Automation accepts document references. Resume/document references are a proposed application-level input; they are not present in the current cleaned CSV dataset.
- Analytics consumes normalized records and optional module outputs. It must disclose unavailable sources and limitations.

## Change process

- Treat v0.1 as the shared prototype baseline.
- A developer proposing a field/type/requiredness change must notify affected module owners and update the relevant schema in a reviewed PR.
- Do not independently rename fields or alter types.
- Validate sample payloads against the relevant schema before integration.
- `additionalProperties: false` is used on defined record objects to catch accidental field drift. Propose new fields through schema review.

## Known decisions still requiring team confirmation

- Matching score formula, weights and thresholds.
- Whether `max_experience` is a hard upper bound or a preferred range.
- Activity event vocabulary.
- Duplicate comparison normalization and similarity method.
- AI extraction model, supported document processing, and confidence calibration.
- Analytics definitions, especially stage counts from historical application rows.
- Whether module output files are runtime-only or approved integration snapshots in Git.
