import os
from dotenv import load_dotenv
# Construct the path to .env.test relative to this test file's location
# Assuming tests/test_integration.py and .env.test is in project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
dotenv_path = os.path.join(project_root, '.env.test')
if not os.path.exists(dotenv_path):
    print(f"WARNING: .env.test file not found at {dotenv_path}. Integration tests might fail or use unexpected configurations.")
    # Fallback to .env if .env.test is not found, for environments where only .env is provided
    # This is a practical measure, though strict separation is ideal.
    dotenv_path_fallback = os.path.join(project_root, '.env')
    if os.path.exists(dotenv_path_fallback):
        print(f"Attempting to load {dotenv_path_fallback} as a fallback.")
        load_dotenv(dotenv_path=dotenv_path_fallback, override=True)
    else:
        print(f"WARNING: Fallback .env also not found at {dotenv_path_fallback}.")
else:
    load_dotenv(dotenv_path=dotenv_path, override=True)
    print(f"Loaded test environment from: {os.path.abspath(dotenv_path)}")


import unittest
import time
import subprocess
import signal
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError, ProgrammingError

# Important: Ensure all other project imports happen *after* load_dotenv
from src.binance_tracker.utils.database_utils import get_database_url, Base, create_db_tables as app_create_db_tables
from src.binance_tracker.utils.database_utils import AssetBalance, Position, Trade # Import models
from main import run_on_demand_fetch # Import the refactored function

# Setup a logger for the test script itself
from src.binance_tracker.utils.logging_utils import setup_logger
test_logger = setup_logger('integration_test_script', log_file='integration_tests.log')


class TestIntegration(unittest.TestCase):
    _db_created_by_test = False # Flag to track if DB was created by these tests
    engine = None # Class variable for engine, to be used by tearDownClass
    default_db_url_for_teardown = None # For potential DB drop

    @classmethod
    def setUpClass(cls):
        test_logger.info("Setting up TestIntegration class...")
        
        cls.test_db_name = os.getenv("DB_NAME") # Should come from .env.test
        if not cls.test_db_name:
            test_logger.error("DB_NAME not found in environment. Ensure .env.test is loaded and configured.")
            raise EnvironmentError("DB_NAME for test database not configured in .env.test.")

        # Construct URL for the default 'postgres' database (or as specified by POSTGRES_DB_FOR_ADMIN)
        # This is to connect and check/create the test database.
        # The get_database_url() from the app will give the URL for the *test database itself*.
        # We need to modify it to connect to the maintenance DB.
        
        # Base URL from .env.test (which should point to the test database)
        cls.test_db_url = get_database_url() 
        
        # Default database to connect to for admin tasks (like creating the test DB)
        # Usually 'postgres' for PostgreSQL. Can be overridden by env var if needed.
        admin_db_name = os.getenv("POSTGRES_DB_FOR_ADMIN", "postgres")
        
        # Construct the admin DB URL by replacing the test DB name with the admin DB name
        # This assumes DB_USER has superuser or CREATEDB privileges
        # Example: postgresql://user:pass@host:port/postgres
        cls.default_db_url_for_teardown = cls.test_db_url.replace(f"/{cls.test_db_name}", f"/{admin_db_name}")
        test_logger.info(f"Admin DB URL for setup/teardown: {cls.default_db_url_for_teardown.replace(os.getenv('DB_PASSWORD','****'), '****')}")


        try:
            engine_default_db = create_engine(cls.default_db_url_for_teardown, isolation_level="AUTOCOMMIT")
            with engine_default_db.connect() as conn:
                res = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname='{cls.test_db_name}'"))
                db_exists = res.scalar_one_or_none()
                if not db_exists:
                    test_logger.info(f"Test database '{cls.test_db_name}' does not exist. Attempting to create.")
                    conn.execute(text(f"CREATE DATABASE {cls.test_db_name}"))
                    cls._db_created_by_test = True
                    test_logger.info(f"Test database '{cls.test_db_name}' created successfully.")
                else:
                    test_logger.info(f"Test database '{cls.test_db_name}' already exists.")
            engine_default_db.dispose()
        except (OperationalError, ProgrammingError) as e:
            test_logger.warning(f"Could not connect to admin DB or create test database '{cls.test_db_name}'. Error: {e}")
            test_logger.warning("Please ensure the database exists or the user has CREATEDB permissions.")
            # If DB creation fails, we assume it might exist and proceed. Table creation will fail later if not.
        except Exception as e_global:
            test_logger.error(f"Unexpected error during database existence check/creation: {e_global}", exc_info=True)
            raise # Re-raise if it's a critical, unexpected error


        # Now connect to the test database to create tables
        test_logger.info(f"Connecting to test database: {cls.test_db_url.replace(os.getenv('DB_PASSWORD','****'), '****')}")
        try:
            cls.engine = create_engine(cls.test_db_url)
            app_create_db_tables(cls.engine) # Pass engine to app's create_tables
            test_logger.info(f"Tables created/verified in test database '{cls.test_db_name}'.")
        except Exception as e:
            test_logger.error(f"Failed to connect to test database '{cls.test_db_name}' or create tables: {e}", exc_info=True)
            raise # Critical if we can't set up tables

        Session = sessionmaker(bind=cls.engine)
        cls.Session = Session
        test_logger.info("TestIntegration class setup complete.")

    @classmethod
    def tearDownClass(cls):
        test_logger.info("Tearing down TestIntegration class...")
        if cls.engine:
            cls.engine.dispose()
            test_logger.info("Test database engine disposed.")

        # Optional: Drop the test database if created by this test run and if CI_TEARDOWN_DB is true
        if cls._db_created_by_test and os.getenv("CI_TEARDOWN_DB", "false").lower() == "true":
            test_logger.info(f"CI_TEARDOWN_DB is true and DB was created by this test run. Attempting to drop test database '{cls.test_db_name}'.")
            try:
                engine_default_db = create_engine(cls.default_db_url_for_teardown, isolation_level="AUTOCOMMIT")
                with engine_default_db.connect() as conn:
                    # Important: Terminate connections before dropping DB.
                    # This is PostgreSQL specific.
                    conn.execute(text(f"""
                        SELECT pg_terminate_backend(pg_stat_activity.pid)
                        FROM pg_stat_activity
                        WHERE pg_stat_activity.datname = '{cls.test_db_name}'
                          AND pid <> pg_backend_pid();
                    """))
                    conn.execute(text(f"DROP DATABASE IF EXISTS {cls.test_db_name}"))
                engine_default_db.dispose()
                test_logger.info(f"Dropped test database '{cls.test_db_name}'.")
            except Exception as e:
                test_logger.error(f"Could not drop test database '{cls.test_db_name}'. Error: {e}", exc_info=True)
        else:
            if not cls._db_created_by_test:
                test_logger.info("Test database was not created by this test run. Skipping drop.")
            if os.getenv("CI_TEARDOWN_DB", "false").lower() != "true":
                test_logger.info("CI_TEARDOWN_DB is not 'true'. Skipping drop of test database.")
        test_logger.info("TestIntegration class teardown complete.")


    def setUp(self):
        test_logger.debug(f"Running setUp for test: {self.id()}")
        # Clear data from tables before each test
        # This ensures tests are idempotent and start with a clean state.
        retries = 3
        for i in range(retries):
            try:
                with self.Session() as session:
                    session.execute(text(f"DELETE FROM {Trade.__tablename__}"))
                    session.execute(text(f"DELETE FROM {Position.__tablename__}"))
                    session.execute(text(f"DELETE FROM {AssetBalance.__tablename__}"))
                    session.commit()
                test_logger.debug(f"Tables cleared for test: {self.id()}")
                return
            except Exception as e:
                test_logger.warning(f"Attempt {i+1}/{retries} to clear tables failed for test {self.id()}: {e}")
                if i == retries - 1: # Last attempt
                    test_logger.error(f"Failed to clear tables after {retries} attempts for test {self.id()}. Test may be unreliable.")
                    raise
                time.sleep(0.5) # Short delay before retry

    def test_scenario_on_demand_fetch(self):
        test_logger.info(f"Starting test: {self.id()}")
        
        # run_on_demand_fetch is imported at the top of the file
        test_logger.info("Running on-demand fetch scenario...")
        success = run_on_demand_fetch(test_mode=True)
        self.assertTrue(success, "run_on_demand_fetch should indicate overall success.")

        with self.Session() as session:
            balances = session.query(AssetBalance).all()
            positions = session.query(Position).all()
            # Example: trades for one of the SCHED_TRADE_SYMBOLS (e.g., BTCUSDT)
            # This relies on SCHED_TRADE_SYMBOLS being set in .env.test
            test_symbols_str = os.getenv("SCHED_TRADE_SYMBOLS", "BTCUSDT")
            first_test_symbol = test_symbols_str.split(',')[0]
            trades = session.query(Trade).filter_by(symbol=first_test_symbol).all()

            self.assertTrue(len(balances) > 0, "Should fetch at least one asset balance")
            test_logger.info(f"Found {len(positions)} positions after on-demand fetch.")
            test_logger.info(f"Found {len(trades)} trades for symbol {first_test_symbol} after on-demand fetch.")
            # Positions can be zero, so no hard assertion.
            # Trades can be zero if no recent testnet activity, so also no hard assertion on count > 0.
            # More specific assertions would require predictable testnet account state.
        test_logger.info(f"Finished test: {self.id()}")

    def test_scenario_scheduler_driven_fetch(self):
        test_logger.info(f"Starting test: {self.id()}")
        scheduler_script_path = os.path.join(project_root, 'scheduler_app.py')
        
        # Use short intervals from .env.test
        balance_interval_min = float(os.getenv("SCHED_BALANCE_INTERVAL_MINUTES", "0.2"))
        # Let scheduler run for a bit longer than one interval to ensure jobs trigger at least once
        # Convert minutes to seconds for time.sleep()
        run_duration_seconds = int(balance_interval_min * 60 * 1.5) 
        if run_duration_seconds < 15 : run_duration_seconds = 15 # Minimum practical time for scheduler to run and fetch

        test_logger.info(f"Running scheduler-driven fetch scenario for {run_duration_seconds} seconds...")
        process = None
        try:
            # Start scheduler_app.py as a subprocess using the current (test) environment
            process = subprocess.Popen([sys.executable, scheduler_script_path], env=os.environ.copy())
            time.sleep(run_duration_seconds) 
        finally:
            if process:
                test_logger.info("Terminating scheduler process...")
                process.send_signal(signal.SIGINT) # Simulate Ctrl+C for graceful shutdown
                try:
                    process.wait(timeout=15) # Wait for graceful shutdown
                    test_logger.info("Scheduler process terminated gracefully.")
                except subprocess.TimeoutExpired:
                    test_logger.warning("Scheduler process did not terminate gracefully within timeout. Killing.")
                    process.kill() 
                    test_logger.warning("Scheduler process killed.")

        with self.Session() as session:
            balances_count = session.query(AssetBalance).count()
            positions_count = session.query(Position).count()
            trades_count = session.query(Trade).count() 

            self.assertTrue(balances_count > 0, "Scheduler should fetch and save asset balances.")
            # Positions might be 0 if no open positions on testnet, so this is more of a smoke test.
            test_logger.info(f"Scheduler found {positions_count} positions.")
            # Trades might be 0 if no recent trades for configured symbols on testnet.
            test_logger.info(f"Scheduler found {trades_count} trades for configured symbols.")
            # Asserting count > 0 for trades might be flaky depending on testnet activity.
            # If SCHED_TRADE_SYMBOLS is empty or symbols have no trades, trades_count will be 0.
            # A more robust test would be to ensure the scheduler ran without critical errors (logged).
        test_logger.info(f"Finished test: {self.id()}")

if __name__ == '__main__':
    # This allows running the integration tests directly, e.g., python tests/test_integration.py
    # Ensure .env.test is in the project root or .env as fallback.
    unittest.main()
