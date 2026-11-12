
from pathlib import Path

import pandas as pd


def get_project_root():
    """
    Locate the Recruitment_Intelligence project root.
    """
    return Path(__file__).resolve().parents[2]


def load_input_data(project_root=None):
    """
    Load all raw recruitment CSV files.

    This function only reads the files.
    It does not clean, modify, or overwrite source data.

    Returns:
        dict: Dataset names mapped to pandas DataFrames.
    """

    if project_root is None:
        project_root = get_project_root()
    else:
        project_root = Path(project_root)

    file_paths = {
        "candidates": project_root / "data" / "raw" / "candidates.csv",
        "jobs": project_root / "data" / "raw" / "jobs.csv",
        "applications": project_root / "data" / "raw" / "applications.csv",
        "activity": project_root / "data" / "raw" / "activity.csv",
        "skill_dictionary": project_root / "data" / "skill_dictionary.csv",
    }

    # Check that all required input files exist.
    missing_files = [
        str(path)
        for path in file_paths.values()
        if not path.is_file()
    ]

    if missing_files:
        raise FileNotFoundError(
            "The following input files are missing:\n"
            + "\n".join(missing_files)
        )

    datasets = {}

    # Load every CSV without modifying the original files.
    for dataset_name, file_path in file_paths.items():

        try:
            dataframe = pd.read_csv(
                file_path,
                dtype=str,
                encoding="utf-8-sig",
                keep_default_na=False
            )

            datasets[dataset_name] = dataframe

            print(
                f"Loaded {dataset_name}: "
                f"{len(dataframe)} records"
            )

        except pd.errors.EmptyDataError as error:
            raise ValueError(
                f"The CSV file is empty or has no header: {file_path}"
            ) from error

        except UnicodeDecodeError as error:
            raise ValueError(
                f"Unable to decode CSV file as UTF-8: {file_path}"
            ) from error

        except pd.errors.ParserError as error:
            raise ValueError(
                f"Unable to parse CSV file: {file_path}"
            ) from error

    return datasets


if __name__ == "__main__":

    data = load_input_data()

    print("\nDATA LOADING SUMMARY")
    print("--------------------")

    for name, dataframe in data.items():
        print(f"\n{name.upper()}")
        print("Rows:", len(dataframe))
        print("Columns:", list(dataframe.columns))
        print(dataframe.head(2))
