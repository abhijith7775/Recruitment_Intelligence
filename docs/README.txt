Recruitment Intelligence - CSV Starter Pack
Schema baseline: Version 1.1

Contents:
- data/raw/candidates.csv
- data/raw/jobs.csv
- data/raw/applications.csv
- data/raw/activity.csv
- data/skill_dictionary.csv

Important:
1. The four raw CSVs are copies of the files supplied for inspection, renamed to the approved canonical filenames.
2. Raw values are preserved. In particular, phone values ending in .0 have NOT been changed here.
   Apply the approved phone normalization in the Data Preparation processing step, keeping phone values as strings.
3. The skill dictionary contains only examples explicitly listed in DATA_SCHEMA.md v1.1.
   Extend it through team review; do not assume it covers every skill in the datasets.
4. Activity event vocabulary is pending project-lead approval. Existing event_type values are preserved as supplied.
5. Do not overwrite raw files. Write processed outputs to data/processed/.
