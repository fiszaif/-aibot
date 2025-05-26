import unittest
from unittest.mock import patch, MagicMock
import os
import logging

# Functions to be tested
from src.binance_tracker.utils.database_utils import get_database_url
from src.binance_tracker.utils.logging_utils import setup_logger

# Mock the logger used in database_utils to prevent console output during tests
@patch('src.binance_tracker.utils.database_utils.logger', MagicMock())
class TestDatabaseUtils(unittest.TestCase):

    @patch.dict(os.environ, {
        "DB_HOST": "testhost",
        "DB_PORT": "1234",
        "DB_USER": "testuser",
        "DB_PASSWORD": "testpassword",
        "DB_NAME": "testdbname"
    }, clear=True) # clear=True ensures only these vars are set for this test
    def test_get_database_url_from_components(self):
        """Test DB URL construction from individual components."""
        expected_url = "postgresql://testuser:testpassword@testhost:1234/testdbname"
        self.assertEqual(get_database_url(), expected_url)

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://env_user:env_pass@env_host:5432/env_db"}, clear=True)
    def test_get_database_url_from_database_url_env(self):
        """Test DB URL is prioritized from DATABASE_URL environment variable."""
        expected_url = "postgresql://env_user:env_pass@env_host:5432/env_db"
        self.assertEqual(get_database_url(), expected_url)

    @patch.dict(os.environ, {}, clear=True) # Ensure environment is empty for this test
    def test_get_database_url_defaults(self):
        """Test DB URL falls back to default values when no env vars are set."""
        # Default values as per get_database_url implementation
        expected_url = "postgresql://your_db_user:your_db_password@localhost:5432/binance_tracker_db"
        self.assertEqual(get_database_url(), expected_url)

    @patch.dict(os.environ, {
        "DATABASE_URL": "env_url", # This should be prioritized
        "DB_HOST": "component_host", # These should be ignored
        "DB_USER": "component_user"
    }, clear=True)
    def test_get_database_url_priority_of_database_url_env(self):
        """Test DATABASE_URL is prioritized over individual components."""
        expected_url = "env_url"
        self.assertEqual(get_database_url(), expected_url)


class TestLoggingUtils(unittest.TestCase):

    def test_setup_logger_creates_logger(self):
        """Test setup_logger creates and configures a logger instance."""
        logger_name = "test_app_logger"
        log_file = "test_app.log"
        log_level = logging.DEBUG

        # Call the function to test
        logger = setup_logger(name=logger_name, log_file=log_file, level=log_level)

        # Assertions
        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.name, logger_name)
        self.assertEqual(logger.level, log_level)

        # Check if handlers are attached (at least one file and one stream handler expected)
        self.assertTrue(any(isinstance(h, logging.FileHandler) for h in logger.handlers))
        self.assertTrue(any(isinstance(h, logging.StreamHandler) for h in logger.handlers))
        
        # Check if log file was created (basic check)
        # Note: setup_logger creates log_file in a 'logs/' subdirectory.
        log_file_path = os.path.join("logs", log_file)
        self.assertTrue(os.path.exists(log_file_path))

        # Clean up: remove the created log file and directory if empty
        if os.path.exists(log_file_path):
            try:
                os.remove(log_file_path)
                # Try to remove 'logs' dir if it's empty - be careful with this in broader test suites
                if not os.listdir("logs"):
                    os.rmdir("logs")
            except OSError as e:
                print(f"Warning: Could not clean up test log file/directory: {e}")


if __name__ == '__main__':
    unittest.main()
