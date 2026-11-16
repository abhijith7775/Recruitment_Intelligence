
import pandas as pd


def build_skill_mapping(skill_dictionary):
    """Build a mapping from original skill names to canonical skill names."""

    mapping = {}

    for _, row in skill_dictionary.iterrows():
        original = str(row["original_skill"]).strip().lower()
        canonical = str(row["canonical_skill"]).strip().lower()

        if original and canonical:
            mapping[original] = canonical

    return mapping


def normalize_skills(value, skill_mapping):
    """Convert semicolon-separated skills into canonical skill names."""

    if pd.isna(value) or str(value).strip() == "":
        return []

    normalized_skills = []
    seen_skills = set()

    for skill in str(value).split(";"):
        original_skill = skill.strip().lower()

        if not original_skill:
            continue

        canonical_skill = skill_mapping.get(
            original_skill,
            original_skill
        )

        if canonical_skill not in seen_skills:
            normalized_skills.append(canonical_skill)
            seen_skills.add(canonical_skill)

    return normalized_skills


def normalize_date(value):
    """Preserve valid ISO dates and leave missing or invalid values unchanged."""

    if pd.isna(value) or str(value).strip() == "":
        return None

    value = str(value).strip()

    try:
        parsed_date = pd.to_datetime(
            value,
            format="%Y-%m-%d",
            errors="raise"
        )

        return parsed_date.strftime("%Y-%m-%d")

    except (ValueError, TypeError):
        return value


def normalize_number(value):
    """Convert valid numeric strings into numbers."""

    if pd.isna(value) or str(value).strip() == "":
        return None

    try:
        number = float(str(value).strip())

        if number.is_integer():
            return int(number)

        return number

    except (ValueError, TypeError):
        return value


def normalize_candidates(candidates, skill_mapping):

    normalized = candidates.copy()

    if "skills" in normalized.columns:
        normalized["skills"] = normalized["skills"].apply(
            lambda value: normalize_skills(value, skill_mapping)
        )

    if "experience_years" in normalized.columns:
        normalized["experience_years"] = (
            normalized["experience_years"].apply(normalize_number)
        )

    if "application_date" in normalized.columns:
        normalized["application_date"] = (
            normalized["application_date"].apply(normalize_date)
        )

    return normalized


def normalize_jobs(jobs, skill_mapping):

    normalized = jobs.copy()

    if "required_skills" in normalized.columns:
        normalized["required_skills"] = (
            normalized["required_skills"].apply(
                lambda value: normalize_skills(value, skill_mapping)
            )
        )

    for column in ["min_experience", "max_experience"]:
        if column in normalized.columns:
            normalized[column] = (
                normalized[column].apply(normalize_number)
            )

    return normalized


def normalize_applications(applications):

    normalized = applications.copy()

    if "stage_date" in normalized.columns:
        normalized["stage_date"] = (
            normalized["stage_date"].apply(normalize_date)
        )

    return normalized


def normalize_activity(activity):

    normalized = activity.copy()

    if "event_date" in normalized.columns:
        normalized["event_date"] = (
            normalized["event_date"].apply(normalize_date)
        )

    return normalized


def normalize_datasets(cleaned_datasets):

    skill_dictionary = cleaned_datasets["skill_dictionary"]

    skill_mapping = build_skill_mapping(skill_dictionary)

    normalized_datasets = {}

    for dataset_name, dataframe in cleaned_datasets.items():

        if dataset_name == "candidates":
            normalized_datasets[dataset_name] = normalize_candidates(
                dataframe, skill_mapping
            )

        elif dataset_name == "jobs":
            normalized_datasets[dataset_name] = normalize_jobs(
                dataframe, skill_mapping
            )

        elif dataset_name == "applications":
            normalized_datasets[dataset_name] = normalize_applications(
                dataframe
            )

        elif dataset_name == "activity":
            normalized_datasets[dataset_name] = normalize_activity(
                dataframe
            )

        else:
            normalized_datasets[dataset_name] = dataframe.copy()

        print(
            f"Normalized {dataset_name}: "
            f"{len(normalized_datasets[dataset_name])} records"
        )

    return normalized_datasets
