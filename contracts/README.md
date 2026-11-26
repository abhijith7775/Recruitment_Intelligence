# Recruitment Intelligence — Module Contracts v0.2

These reviewed-proposal contracts extend the v0.1 prototype to support both the existing CSV batch workflow and incremental application submissions. Changes are additive where possible; legacy candidate and application records remain valid.

## Contract inventory

- `common/`: normalized candidate, job, application, activity, skill dictionary and common response envelope schemas; raw CSV-row schemas for Data Preparation ingestion.
- `ai_automation/output.schema.json`: extraction output, including submission context.
- `data_preparation/input.schema.json`: batch CSV input and optional AI Automation output envelope.
- `data_preparation/output.schema.json`: normalized output and processing metadata.

## Incremental application flow

1. The application layer creates a stable `source_submission_id` for each submitted application. Retries of the same submission must reuse that identifier.
2. AI Automation extracts resume/document fields and returns them with `source_submission_id`, `document_id`, and optional `job_id` and `submitted_at`.
3. AI-extracted values remain unverified suggestions. AI Automation must not decide candidate identity or silently overwrite verified candidate data.
4. Data Preparation validates, cleans, and normalizes the AI Automation envelope using the same canonicalization and validation rules used for batch data.
5. Backend/Database Integration resolves candidate identity, assigns candidate and application IDs, applies idempotency, and persists accepted records.
6. Duplicate Detection flags possible duplicate candidates for human review. No automatic merge or deletion is permitted.

For an incremental Data Preparation request, set `input_mode` to `incremental`, provide the five existing CSV dataset arrays as empty arrays when they are not being supplied, and include `ai_automation_output`. For a batch request, set `input_mode` to `batch` and provide the CSV dataset arrays as before.

## Identity and history rules

- `candidate_id` remains a stable backend-assigned identifier. It is not optional in a normalized candidate record.
- `source_submission_id` identifies one application submission, not a person and not a document. It is the idempotency key for retry handling.
- `document_id` identifies an uploaded document and must not be treated as the candidate or application identifier.
- `application_id` is optional for legacy records. The backend should assign it to new applications; distinct applications may exist for the same candidate and job.
- Preserve every application stage transition as a separate history row.
- A candidate applying to another job does not automatically create another candidate profile.
- Data Preparation does not write directly to database tables or assign official candidate/application IDs.

## Dataset-derived structures

- Candidates: `candidate_id,name,email,phone,location,experience_years,skills,education,source,application_date`
- Jobs: `job_id,role,required_skills,min_experience,max_experience`
- Applications: `candidate_id,job_id,stage,stage_date,recruiter_id` plus optional `application_id` and `source_submission_id`
- Activity: `candidate_id,event_type,event_date`
- Skill dictionary: `original_skill,canonical_skill`

## Representation and safety rules

1. CSV cells arrive as strings. Data Preparation converts numeric/date fields to JSON number/date types.
2. CSV blank optional values become JSON `null` in normalized records.
3. CSV skills are semicolon-separated; normalized JSON skills are arrays of lowercase canonical skill strings.
4. Candidate IDs use `C001` style and job IDs use `J001` style.
5. Application stage values are `New`, `Screened`, `Shortlisted`, `Interviewed`, `Offered`, `Hired`, `Rejected`.
6. Application rows represent stage history. Preserve history; do not collapse rows during ingestion.
7. Activity `event_type` vocabulary is pending approval. Preserve source values; do not invent an enum.
8. Missing values must not be guessed.
9. Email and phone may support duplicate detection only. They must not be used in candidate-job matching.
10. Duplicate detection flags pairs for human review; it must not merge or delete records.
11. AI-extracted values are unverified suggestions and must not silently overwrite verified candidate records.
12. Matching uses job-related skills and experience only. Do not use name, email, phone, location, source, education or protected/proxy characteristics for scoring.
13. Data Preparation validates and normalizes; Backend/Database Integration owns persistence, official ID assignment, and transaction/idempotency handling.

## Versioning and change process

- v0.1 is the original prototype baseline. v0.2 adds incremental-submission context.
- A developer proposing a field/type/requiredness change must notify affected module owners and update the relevant schema in a reviewed PR.
- Do not independently rename fields or alter types.
- Validate sample payloads against the relevant schema before integration.
- `additionalProperties: false` is used on defined record objects to catch accidental field drift. Propose new fields through schema review.

## Decisions still requiring team confirmation

- Whether multiple applications by the same candidate to the same job are permitted and how re-applications are represented.
- Exact application-layer ownership and format of `source_submission_id`.
- Whether the backend or application layer generates `application_id`.
- Matching score formula, weights and thresholds.
- Whether `max_experience` is a hard upper bound or a preferred range.
- Activity event vocabulary.
- Duplicate comparison normalization and similarity method.
- AI extraction model, supported document processing, and confidence calibration.
- Analytics definitions, especially stage counts from historical application rows.
- Whether module output files are runtime-only or approved integration snapshots in Git.
