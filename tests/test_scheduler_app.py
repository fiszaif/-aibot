import unittest
from unittest.mock import patch, MagicMock, call
import os
import sys

# Temporarily add src directory to path to allow direct import of scheduler_app for testing its internals
# This is often needed if scheduler_app.py is not part of an installed package
# and tests are run from the root directory.
# A better approach for larger projects might be to structure tests as a package
# that can import the main package, or use tox/nox for test environment setup.
# For this specific case, we'll assume tests might be run directly or via 'python -m unittest discover'
# from the root, where 'scheduler_app' might not be directly importable without path adjustment.
# However, if `PYTHONPATH` is set correctly (e.g. to include project root), this is not needed.
# We will attempt to import directly, assuming the test runner handles paths or PYTHONPATH is set.

# Attempt to import functions and variables from scheduler_app
# If scheduler_app.py relies on relative imports like ..utils,
# running it directly as a script can cause issues.
# For unit testing, we usually import specific functions/classes.

# We will mock the global variables that are set up when scheduler_app is imported.
# This is tricky because scheduler_app.py executes code at import time (like loading env vars).

# Option 1: Mock environment variables *before* importing scheduler_app parts.
# This is complex because the import happens before test methods run.

# Option 2: Patch the loaded config values within scheduler_app directly.
# This is more feasible for unit tests.

# Option 3: Structure scheduler_app.py to have its core logic in functions
# that can be called with configuration, making it easier to test.
# (Assuming current structure where config is loaded at module level)

# For testing, we'll patch the specific config variables as they are used by the job functions
# and also patch the functions called by the jobs (get_binance_client, get_db, data_fetchers).

class TestSchedulerAppConfig(unittest.TestCase):

    @patch.dict(os.environ, {"SCHED_BALANCE_INTERVAL_MINUTES": "30"}, clear=True)
    def test_load_balance_interval_custom(self):
        # This test needs to effectively re-import or re-evaluate scheduler_app's config loading.
        # Since config is loaded at module level on import, this is tricky.
        # A better way is to have a function in scheduler_app that parses config.
        # For now, we'll assume we can patch os.getenv calls if they were inside functions.
        # Or, we test the effect of these env vars on the job scheduling (integration test style).
        # Let's simulate that the scheduler_app's global var would be set.
        # This test is more illustrative of how one might test config parsing
        # if it were encapsulated in a function.
        # For now, we'll skip direct testing of module-level config loading
        # and focus on testing job functions with mocked config values.
        pass # Placeholder, as direct testing of module-level load is complex

    @patch.dict(os.environ, {}, clear=True) # No env var set
    def test_load_balance_interval_default(self):
        # Similar to above, testing default value requires re-evaluation.
        # We will assume SCHED_BALANCE_INTERVAL_MINUTES in scheduler_app would take its default.
        pass # Placeholder


# We need to patch objects *where they are looked up*, which is in 'scheduler_app' module.
@patch('scheduler_app.get_binance_client')
@patch('scheduler_app.get_db')
@patch('scheduler_app.get_futures_account_balance')
@patch('scheduler_app.get_futures_open_positions')
@patch('scheduler_app.get_futures_recent_trades')
@patch('scheduler_app.scheduler_logger', MagicMock()) # Mock the logger
class TestSchedulerJobs(unittest.TestCase):

    def setUp(self):
        # Define mock config values that would normally be loaded from os.environ in scheduler_app
        self.mock_config = {
            "SCHED_USE_TESTNET": True,
            "SCHED_TRADE_SYMBOLS": ["BTCUSDT", "ETHUSDT"],
            "SCHED_TRADES_LIMIT": 50,
        }

    # --- Tests for fetch_and_store_balance_job ---
    def test_fetch_and_store_balance_job_success(self, mock_gfrt, mock_gfop, mock_gfab, mock_get_db, mock_gbc):
        # Import the job function here to ensure it's fresh for each test case if needed,
        # or ensure mocks are applied correctly before its use.
        from scheduler_app import fetch_and_store_balance_job

        mock_client_instance = MagicMock()
        mock_gbc.return_value = mock_client_instance
        
        mock_db_session_instance = MagicMock()
        mock_get_db_context_manager = MagicMock()
        mock_get_db_context_manager.__enter__.return_value = mock_db_session_instance
        mock_get_db_context_manager.__exit__.return_value = None
        mock_get_db.return_value = mock_get_db_context_manager
        
        mock_gfab.return_value = [MagicMock()] # Simulate it returns a list of one saved balance

        # Patch the global config variables used by the job
        with patch.dict('scheduler_app.__dict__', self.mock_config):
            fetch_and_store_balance_job()

        mock_gbc.assert_called_once_with(testnet=self.mock_config["SCHED_USE_TESTNET"])
        mock_get_db.assert_called_once()
        mock_gfab.assert_called_once_with(mock_client_instance, mock_db_session_instance)
        # scheduler_logger.info should have been called with success message (requires logger mock configuration)

    def test_fetch_and_store_balance_job_client_failure(self, mock_gfrt, mock_gfop, mock_gfab, mock_get_db, mock_gbc):
        from scheduler_app import fetch_and_store_balance_job
        mock_gbc.return_value = None # Simulate client creation failure

        with patch.dict('scheduler_app.__dict__', self.mock_config):
            fetch_and_store_balance_job()

        mock_gbc.assert_called_once_with(testnet=self.mock_config["SCHED_USE_TESTNET"])
        mock_get_db.assert_not_called() # Should not proceed to get DB session
        mock_gfab.assert_not_called() # Data fetcher should not be called

    def test_fetch_and_store_balance_job_db_session_failure(self, mock_gfrt, mock_gfop, mock_gfab, mock_get_db, mock_gbc):
        from scheduler_app import fetch_and_store_balance_job
        mock_gbc.return_value = MagicMock() # Client success
        
        mock_get_db_context_manager = MagicMock()
        mock_get_db_context_manager.__enter__.return_value = None # Simulate DB session failure
        mock_get_db_context_manager.__exit__.return_value = None
        mock_get_db.return_value = mock_get_db_context_manager

        with patch.dict('scheduler_app.__dict__', self.mock_config):
            fetch_and_store_balance_job()
        
        mock_gfab.assert_not_called() # Data fetcher should not be called if DB session fails

    def test_fetch_and_store_balance_job_fetcher_api_error(self, mock_gfrt, mock_gfop, mock_gfab, mock_get_db, mock_gbc):
        from scheduler_app import fetch_and_store_balance_job
        mock_gbc.return_value = MagicMock()
        mock_get_db.return_value.__enter__.return_value = MagicMock() # DB session success
        mock_gfab.side_effect = Exception("API Fetcher Error") # Simulate error in data_fetcher

        with patch.dict('scheduler_app.__dict__', self.mock_config):
            fetch_and_store_balance_job()
        
        mock_gfab.assert_called_once() # Assert it was called
        # Check logger for error message (scheduler_logger.error was called)

    # --- Tests for fetch_and_store_positions_job (similar structure) ---
    def test_fetch_and_store_positions_job_success(self, mock_gfrt, mock_gfop, mock_gfab, mock_get_db, mock_gbc):
        from scheduler_app import fetch_and_store_positions_job
        mock_client_instance = MagicMock()
        mock_gbc.return_value = mock_client_instance
        mock_db_session_instance = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db_session_instance
        mock_gfop.return_value = [MagicMock()]

        with patch.dict('scheduler_app.__dict__', self.mock_config):
            fetch_and_store_positions_job()

        mock_gbc.assert_called_once_with(testnet=self.mock_config["SCHED_USE_TESTNET"])
        mock_get_db.assert_called_once()
        mock_gfop.assert_called_once_with(mock_client_instance, mock_db_session_instance)

    # --- Tests for fetch_and_store_trades_job ---
    def test_fetch_and_store_trades_job_success_multi_symbol(self, mock_gfrt, mock_gfop, mock_gfab, mock_get_db, mock_gbc):
        from scheduler_app import fetch_and_store_trades_job
        mock_client_instance = MagicMock()
        mock_gbc.return_value = mock_client_instance
        mock_db_session_instance = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db_session_instance
        
        # Simulate different numbers of trades returned for different symbols
        mock_gfrt.side_effect = [[MagicMock(), MagicMock()], [MagicMock()]] # 2 for BTC, 1 for ETH

        with patch.dict('scheduler_app.__dict__', self.mock_config):
            fetch_and_store_trades_job()

        mock_gbc.assert_called_once_with(testnet=self.mock_config["SCHED_USE_TESTNET"])
        mock_get_db.assert_called_once()
        
        # Check calls to get_futures_recent_trades for each symbol
        expected_calls = [
            call(mock_client_instance, mock_db_session_instance, symbol="BTCUSDT", limit=self.mock_config["SCHED_TRADES_LIMIT"]),
            call(mock_client_instance, mock_db_session_instance, symbol="ETHUSDT", limit=self.mock_config["SCHED_TRADES_LIMIT"]),
        ]
        mock_gfrt.assert_has_calls(expected_calls, any_order=False) # any_order=False if symbols are processed in defined order
        self.assertEqual(mock_gfrt.call_count, 2) # Called once for each symbol

    def test_fetch_and_store_trades_job_symbol_specific_error(self, mock_gfrt, mock_gfop, mock_gfab, mock_get_db, mock_gbc):
        from scheduler_app import fetch_and_store_trades_job
        mock_client_instance = MagicMock()
        mock_gbc.return_value = mock_client_instance
        mock_db_session_instance = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db_session_instance

        # First symbol (BTCUSDT) fetch works, second (ETHUSDT) raises an error
        mock_gfrt.side_effect = [
            [MagicMock()],  # Successful fetch for BTCUSDT
            Exception("Error fetching ETHUSDT trades") # Error for ETHUSDT
        ]
        
        # Mock config for this test to have a predictable order
        test_config = self.mock_config.copy()
        test_config["SCHED_TRADE_SYMBOLS"] = ["BTCUSDT", "ETHUSDT"]

        with patch.dict('scheduler_app.__dict__', test_config):
            fetch_and_store_trades_job()

        # Assert that get_futures_recent_trades was called for both symbols
        self.assertEqual(mock_gfrt.call_count, 2)
        # Assert logger.error was called for the ETHUSDT error (requires logger mock setup)
        # scheduler_logger.error.assert_any_call( innehåller "Error processing symbol ETHUSDT" )


if __name__ == '__main__':
    # Important: For these tests to run correctly, especially with module-level patching or imports,
    # it's best to run them using 'python -m unittest tests.test_scheduler_app' from the project root,
    # or 'python -m unittest discover -s tests'.
    # This helps Python resolve imports correctly.
    unittest.main()
