
from modules.data_preparation.loader import load_input_data
from modules.data_preparation.cleaner import clean_datasets


def main():

    raw_datasets = load_input_data()

    cleaned_datasets = clean_datasets(raw_datasets)

    print("\nCLEANING SUMMARY")
    print("----------------")

    for name, dataframe in cleaned_datasets.items():

        print(f"\n{name.upper()}")
        print("Rows:", len(dataframe))
        print("Columns:", list(dataframe.columns))
        print(dataframe.head(2))

    print("\nCleaning completed successfully.")


if __name__ == "__main__":
    main()
