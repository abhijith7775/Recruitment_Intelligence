
from modules.data_preparation.loader import load_input_data
from modules.data_preparation.cleaner import clean_datasets
from modules.data_preparation.normalizer import normalize_datasets


def main():

    raw_datasets = load_input_data()

    cleaned_datasets = clean_datasets(raw_datasets)

    normalized_datasets = normalize_datasets(cleaned_datasets)

    print("\nNORMALIZATION SUMMARY")
    print("---------------------")

    for name, dataframe in normalized_datasets.items():

        print(f"\n{name.upper()}")
        print("Rows:", len(dataframe))
        print("Columns:", list(dataframe.columns))
        print(dataframe.head(2))

    print("\nNormalization completed successfully.")


if __name__ == "__main__":
    main()
