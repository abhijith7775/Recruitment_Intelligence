
import re
import pandas as pd


def clean_text(value):
    """Remove leading and trailing whitespace without guessing missing values."""
    if pd.isna(value):
        return value

    cleaned_value = str(value).strip()

    return cleaned_value


def clean_skills(value):
    """
    Normalize skill tokens:
    - Trim whitespace
    - Convert to lowercase
    - Remove duplicate tokens
    - Preserve original skill names for dictionary normalization later
    """
    if pd.isna(value):
        return value

    skills = str(value).split(";")

    cleaned_skills = []
    seen_skills = set()

    for skill in skills:
        skill = skill.strip().lower()

        if skill and skill not in seen_skills:
            cleaned_skills.append(skill)
            seen_skills.add(skill)

    return ";".join(cleaned_skills)


def clean_phone(value):
    """Remove whitespace and unnecessary numeric .0 suffix."""
    if pd.isna(value):
        return value

    cleaned_value = str(value).strip()

    if re.fullmatch(r"\d+\.0", cleaned_value):
        cleaned_value = cleaned_value[:-2]

    return cleaned_value


def clean_experience(value):
    """Normalize valid numeric experience values without guessing missing data."""
    if pd.isna(value) or str(value).strip() == "":
        return value

    cleaned_value = str(value).strip()

    try:
        number = float(cleaned_value)

        if number < 0:
            return cleaned_value

        if number.is_integer():
            return str(int(number))

        return str(number)

    except ValueError:
        return cleaned_value


def clean_dataframe(dataframe, dataset_name):
    """Clean a copy of a dataset while preserving its original records."""

    cleaned_df = dataframe.copy()

    # Clean whitespace in text columns.
    for column in cleaned_df.columns:
        cleaned_df[column] = cleaned_df[column].map(clean_text)

    # Dataset-specific cleaning.
    if dataset_name == "candidates":

        if "skills" in cleaned_df.columns:
            cleaned_df["skills"] = cleaned_df["skills"].map(clean_skills)

        if "phone" in cleaned_df.columns:
            cleaned_df["phone"] = cleaned_df["phone"].map(clean_phone)

        if "experience_years" in cleaned_df.columns:
            cleaned_df["experience_years"] = (
                cleaned_df["experience_years"].map(clean_experience)
            )

    elif dataset_name == "jobs":

        if "required_skills" in cleaned_df.columns:
            cleaned_df["required_skills"] = (
                cleaned_df["required_skills"].map(clean_skills)
            )

        for column in ["min_experience", "max_experience"]:
            if column in cleaned_df.columns:
                cleaned_df[column] = (
                    cleaned_df[column].map(clean_experience)
                )

    return cleaned_df


def clean_datasets(datasets):
    """Clean all loaded datasets and return new DataFrames."""

    cleaned_datasets = {}

    for dataset_name, dataframe in datasets.items():
        cleaned_datasets[dataset_name] = clean_dataframe(
            dataframe,
            dataset_name
        )

        print(
            f"Cleaned {dataset_name}: "
            f"{len(cleaned_datasets[dataset_name])} records"
        )

    return cleaned_datasets
