"""
Utility functions for saving and loading data to/from JSON and CSV files.

Note: As of the integration of PostgreSQL, these functions are now primarily
intended for data export, temporary storage, or for use cases where a simple
file-based output is preferred over database storage. The main application
flow now uses PostgreSQL as its primary data store.
"""
import json
import csv
import os
from .logging_utils import setup_logger

logger = setup_logger(__name__)

def save_to_json(data, filepath, filename):
    """
    Saves data to a JSON file.

    Args:
        data (list or dict): Data to be saved.
        filepath (str): Directory to save the file in.
        filename (str): Name of the file (e.g., 'data.json').
    """
    try:
        os.makedirs(filepath, exist_ok=True)
        full_path = os.path.join(filepath, filename)
        with open(full_path, 'w') as f:
            json.dump(data, f, indent=4)
        logger.info(f"Successfully saved data to {full_path}")
    except IOError as e:
        logger.error(f"Error saving data to JSON file {full_path}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"An unexpected error occurred while saving to JSON {full_path}: {e}", exc_info=True)

def save_to_csv(data, filepath, filename):
    """
    Saves data to a CSV file.

    Args:
        data (list): List of dictionaries to be saved.
        filepath (str): Directory to save the file in.
        filename (str): Name of the file (e.g., 'data.csv').
    """
    try:
        os.makedirs(filepath, exist_ok=True)
        full_path = os.path.join(filepath, filename)

        if not data or not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
            msg = f"Data is empty or not in the expected format (list of dicts). Cannot save to CSV {full_path}."
            if isinstance(data, list) and not data: # if data is an empty list
                 try:
                    with open(full_path, 'w', newline='') as f:
                        # Create an empty csv file
                        csv.writer(f)
                    logger.info(f"Created an empty CSV file at {full_path} as data was an empty list.")
                 except IOError as e_io:
                    logger.error(f"Error creating empty CSV file {full_path}: {e_io}", exc_info=True)
                 except Exception as e_gen:
                    logger.error(f"Unexpected error creating empty CSV file {full_path}: {e_gen}", exc_info=True)
            else:
                logger.warning(msg)
            return

        with open(full_path, 'w', newline='') as f:
            # Assume all dicts in the list have the same keys as the first one for headers
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        logger.info(f"Successfully saved data to {full_path}")
    except IOError as e:
        logger.error(f"Error saving data to CSV file {full_path}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"An unexpected error occurred while saving to CSV {full_path}: {e}", exc_info=True)

def load_from_json(filepath, filename):
    """
    Loads data from a JSON file.

    Args:
        filepath (str): Directory where the file is located.
        filename (str): Name of the file (e.g., 'data.json').

    Returns:
        list or dict or None: Loaded data, or None if an error occurs.
    """
    full_path = os.path.join(filepath, filename)
    try:
        with open(full_path, 'r') as f:
            data = json.load(f)
        # logger.debug(f"Successfully loaded data from {full_path}") # Optional: too verbose for a load function
        return data
    except FileNotFoundError:
        logger.warning(f"JSON file not found: {full_path}") # Good to log this as a warning
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from file {full_path}: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading from JSON {full_path}: {e}", exc_info=True)
        return None

def load_from_csv(filepath, filename):
    """
    Loads data from a CSV file into a list of dictionaries.

    Args:
        filepath (str): Directory where the file is located.
        filename (str): Name of the file (e.g., 'data.csv').

    Returns:
        list or None: List of dictionaries loaded from CSV, or None if an error occurs.
    """
    full_path = os.path.join(filepath, filename)
    try:
        data = []
        with open(full_path, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(row)
        # logger.debug(f"Successfully loaded data from {full_path}") # Optional: too verbose
        if not data and os.path.getsize(full_path) > 0: # File was not empty but resulted in no data (e.g. only header)
            logger.info(f"CSV file {full_path} seems to contain only headers or is empty.")
            pass # Return empty list in this case, which is correct
        return data
    except FileNotFoundError:
        logger.warning(f"CSV file not found: {full_path}")
        return None
    except IOError as e:
        logger.error(f"Error loading data from CSV file {full_path}: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading from CSV {full_path}: {e}", exc_info=True)
        return None

if __name__ == '__main__':
    # Basic test cases
    # Note: The logger used here will be the module-level logger defined above.
    # If a separate logger for tests is needed, it can be set up like in other __main__ blocks.
    test_logger = setup_logger('storage_utils_test', log_file='storage_utils_test.log')
    test_logger.info("Running basic tests for storage_utils...")
    TEST_DATA_DIR = "test_storage_data" # Temporary directory for test files
    
    # Ensure the test directory is clean before testing
    if os.path.exists(TEST_DATA_DIR):
        import shutil
        shutil.rmtree(TEST_DATA_DIR)
    os.makedirs(TEST_DATA_DIR, exist_ok=True)

    sample_data_list_dict = [
        {"id": 1, "name": "Alice", "value": 100},
        {"id": 2, "name": "Bob", "value": 200},
    ]
    sample_data_dict = {"config": "test", "version": 1.0}
    empty_list_data = []

    # Test JSON save and load
    test_logger.info("Testing JSON operations...")
    save_to_json(sample_data_list_dict, TEST_DATA_DIR, "list_data.json")
    loaded_json_list = load_from_json(TEST_DATA_DIR, "list_data.json")
    assert loaded_json_list == sample_data_list_dict, "JSON list load/save failed"
    test_logger.info("JSON list save/load test PASSED.")

    save_to_json(sample_data_dict, TEST_DATA_DIR, "dict_data.json")
    loaded_json_dict = load_from_json(TEST_DATA_DIR, "dict_data.json")
    assert loaded_json_dict == sample_data_dict, "JSON dict load/save failed"
    test_logger.info("JSON dict save/load test PASSED.")

    # Test CSV save and load
    test_logger.info("Testing CSV operations...")
    save_to_csv(sample_data_list_dict, TEST_DATA_DIR, "data.csv")
    loaded_csv_data = load_from_csv(TEST_DATA_DIR, "data.csv")
    # CSV loads numbers as strings by default with DictReader, so we need to compare carefully
    expected_csv_data = [
        {"id": '1', "name": "Alice", "value": '100'}, # Values will be strings
        {"id": '2', "name": "Bob", "value": '200'},
    ]
    assert loaded_csv_data == expected_csv_data, f"CSV load/save failed. Expected {expected_csv_data}, got {loaded_csv_data}"
    test_logger.info("CSV save/load test PASSED.")

    # Test saving empty list to CSV
    test_logger.info("Testing saving empty list to CSV...")
    save_to_csv(empty_list_data, TEST_DATA_DIR, "empty.csv")
    loaded_empty_csv = load_from_csv(TEST_DATA_DIR, "empty.csv")
    assert loaded_empty_csv == [], f"CSV empty list load/save failed. Expected [], got {loaded_empty_csv}"
    test_logger.info("CSV empty list save/load test PASSED.")
    
    # Test saving unsuitable data to CSV (e.g. list of strings)
    test_logger.info("Testing saving unsuitable data to CSV...")
    unsuitable_data_csv = ["a", "b", "c"]
    save_to_csv(unsuitable_data_csv, TEST_DATA_DIR, "unsuitable.csv")
    # Expect console message and no file or empty file. Check if file exists.
    # If save_to_csv creates an empty file for unsuitable data, this needs adjustment.
    # Current implementation logs a message and returns.
    unsuitable_file_path = os.path.join(TEST_DATA_DIR, "unsuitable.csv")
    assert not os.path.exists(unsuitable_file_path) or os.path.getsize(unsuitable_file_path) == 0, \
        f"CSV unsuitable data test failed: File '{unsuitable_file_path}' was created for unsuitable data and is not empty."
    test_logger.info("CSV unsuitable data handling test PASSED (expected no file or empty file).")


    # Test loading non-existent files
    test_logger.info("Testing loading non-existent files...")
    assert load_from_json(TEST_DATA_DIR, "non_existent.json") is None, "JSON non-existent load failed"
    test_logger.info("JSON non-existent file load test PASSED.")
    assert load_from_csv(TEST_DATA_DIR, "non_existent.csv") is None, "CSV non-existent load failed"
    test_logger.info("CSV non-existent file load test PASSED.")

    test_logger.info("All basic tests for storage_utils completed.")
    
    # Clean up the test directory
    # import shutil # already imported
    # shutil.rmtree(TEST_DATA_DIR)
    # test_logger.info(f"Cleaned up test directory: {TEST_DATA_DIR}")
    # It might be better to leave the test_storage_data directory for inspection after the run.
    test_logger.info(f"Test files are in {TEST_DATA_DIR}. You may want to inspect or delete it manually.")
