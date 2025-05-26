# Binance Futures Tracker

A Python-based framework to connect to Binance Futures, fetch account data (balance, positions, trades), and provide a basic structure for building more advanced trading tools and trackers.

## Features (Current)

*   Connects to Binance Futures API (Mainnet and Testnet).
*   Fetches account balance, open positions, and recent trade history.
*   Stores fetched data in a PostgreSQL database.
*   Automated background data fetching using a scheduler (APScheduler).
*   Configurable intervals for different data types (balance, positions, trades).
*   Configurable list of symbols for trade fetching.
*   Supports Binance Testnet for both manual and scheduled fetching.
*   Basic logging implemented for all components.
*   Unit tests for core functionality, utilities, and scheduler jobs.

## Project Structure

```
.
├── config/
│   └── .env.example        # Example for API key configuration
├── docs/                   # (Placeholder for future documentation)
├── logs/                   # Log files will be created here (.gitignored)
├── output_data/            # Output files from main.py will be saved here (.gitignored)
├── src/
│   └── binance_tracker/
│       ├── __init__.py
│       ├── connectors/     # Binance API connection logic
│       │   ├── __init__.py
│       │   └── binance_connector.py
│       ├── core/           # Core data fetching logic (interacts with DB)
│       │   ├── __init__.py
│       │   └── data_fetcher.py
│       └── utils/          # Utility modules
│           ├── __init__.py
│           ├── database_utils.py # PostgreSQL database schema and session management
│           ├── logging_utils.py  # Logging setup
│           └── storage_utils.py  # Utilities for file-based export (secondary)
├── tests/                  # Unit tests
│   ├── __init__.py
│   ├── test_connectors.py
│   ├── test_core.py
│   ├── test_scheduler_app.py
│   └── test_utils.py
├── .gitignore
├── main.py                 # Example CLI for on-demand data fetching and DB interaction
├── README.md
├── requirements.txt        # Project dependencies
├── scheduler_app.py        # Background scheduler for continuous data fetching
```

## Setup Instructions

### 1. Prerequisites

*   Python 3.8 or higher.
*   `pip` for installing packages.
*   A Binance account (Mainnet or Testnet) with API keys.
*   PostgreSQL server.

### 2. Clone the Repository

```bash
git clone <repository_url>
cd <repository_directory>
```
Replace `<repository_url>` and `<repository_directory>` with the actual URL and the name of the directory where the repository was cloned.

### 3. Create a Virtual Environment (Recommended)

```bash
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure API Keys

*   Copy the example environment file from `config/.env.example` to the project root directory and rename it to `.env`:
    ```bash
    cp config/.env.example .env
    ```
*   Open the `.env` file and replace the placeholder values with your actual Binance API key and secret:
    ```
    BINANCE_API_KEY="YOUR_ACTUAL_API_KEY"
    BINANCE_API_SECRET="YOUR_ACTUAL_API_SECRET"
    ```
    **Important**: Ensure the `.env` file is listed in your `.gitignore` (it is by default in this project) to prevent accidentally committing your API keys.
    *   Also, update the database connection variables (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`) and scheduler configurations (`SCHED_*` variables) in the `.env` file as needed. Refer to `config/.env.example` for the full list of configurable variables.

### 6. Setting up PostgreSQL

*   This application now uses PostgreSQL to store all fetched data.
*   **Installation**: Install PostgreSQL (version 12 or higher is recommended). You can download it from [postgresql.org](https://www.postgresql.org/) or use a package manager (e.g., `sudo apt update && sudo apt install postgresql postgresql-contrib` on Ubuntu, or `brew install postgresql` on macOS).
*   **Database Creation**:
    *   Start the PostgreSQL service.
    *   Connect to PostgreSQL (e.g., using `psql`).
    *   Create a new database for this application, e.g., `CREATE DATABASE binance_tracker_db;`.
    *   Create a new user (role) and grant it privileges to the database, e.g.,
        ```sql
        CREATE USER your_db_user WITH PASSWORD 'your_db_password';
        GRANT ALL PRIVILEGES ON DATABASE binance_tracker_db TO your_db_user;
        ALTER DATABASE binance_tracker_db OWNER TO your_db_user;
        ```
        Replace `your_db_user` and `your_db_password` with your desired credentials.
*   **Configure `.env`**: Update the `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, and `DB_NAME` variables in your `.env` file with the details of your PostgreSQL setup. If `DATABASE_URL` is set, it will override individual components.

## Usage

### Running the Example Script (`main.py`)

The `main.py` script provides an on-demand way to:
*   Ensure the database schema is created (`create_db_tables()`).
*   Connect to the Binance API (Testnet by default).
*   Fetch current account balance, open positions, and recent trades for a sample symbol.
*   Store this data directly into the PostgreSQL database.
*   Print the fetched data to the console.

```bash
python main.py
```

This script is useful for initial setup, testing the connection, or fetching data manually.

```bash
python main.py
```

### Running the Background Scheduler (`scheduler_app.py`)

The `scheduler_app.py` is responsible for periodically fetching data from Binance and storing it in the PostgreSQL database. This is the primary way to collect data continuously.

```bash
python scheduler_app.py
```

This script will:
*   Run as a long-running background process.
*   Connect to Binance (Testnet or Mainnet based on `.env` config).
*   Periodically fetch account balance, open positions, and trades for configured symbols according to intervals set in the `.env` file (`SCHED_BALANCE_INTERVAL_MINUTES`, `SCHED_POSITIONS_INTERVAL_MINUTES`, `SCHED_TRADES_INTERVAL_MINUTES`).
*   Store the fetched data in the PostgreSQL database.
*   Log its activities to `logs/scheduler.log` and the console.
*   You can configure the trade symbols (`SCHED_TRADE_SYMBOLS`) and whether to use Testnet (`SCHED_USE_TESTNET`) in the `.env` file.

To stop the scheduler, press `Ctrl+C` in the terminal where it's running.

### Running Unit Tests

To ensure the core components are working correctly, you can run the unit tests:

```bash
python -m unittest discover -s tests
```
Or, if you have `unittest` installed globally or in your virtual environment, you can often simplify this to:
```bash
python -m unittest tests
```
If that doesn't work, the first command is more explicit and reliable. Make sure your current directory is the project root when running this command.

### Running Integration Tests

**Purpose**: Integration tests verify the interaction between different components of the application, including external services like the Binance Testnet API and PostgreSQL. They ensure that the system works together as a whole.

**Prerequisites**:
*   A running PostgreSQL server.
*   The Binance Testnet API keys must be configured. Copy `config/.env.test.example` to a new file named `.env.test` in the project root:
    ```bash
    cp config/.env.test.example .env.test
    ```
*   Edit `.env.test` to provide your actual Binance Testnet API key and secret.
*   Ensure the database connection details in `.env.test` (especially `DB_NAME`, `DB_USER`, `DB_PASSWORD`) are correctly set up for your test PostgreSQL instance. The tests will attempt to create the test database (e.g., `binance_tracker_db_test` as defined in `.env.test`) if it doesn't exist, provided the configured PostgreSQL user has `CREATEDB` privileges. Otherwise, you may need to create the test database manually.

**Command to Run**:
To run the integration tests, use the following command from the project root:
```bash
python -m unittest tests.test_integration
```
Alternatively, you can run a specific test class or method if needed:
```bash
python -m unittest tests.test_integration.TestIntegration
python -m unittest tests.test_integration.TestIntegration.test_scenario_on_demand_fetch
```

**Important Notes**:
*   Integration tests interact with the live Binance Testnet and will make actual API calls.
*   These tests will also interact with your PostgreSQL database, creating tables and potentially dropping the test database specified in `.env.test` (if `CI_TEARDOWN_DB=true` is set in `.env.test` and the database was created by the test run). Ensure no critical data exists in the specified test database.
*   The tests may take a few minutes to run, especially the scheduler test which involves waiting for scheduled jobs.
*   If running for the first time, the tests might attempt to create the test database. Subsequent runs will use the existing test database and clear table data before each test execution.

## Logging

*   The application uses Python's `logging` module.
*   Log files are stored in the `logs/` directory (e.g., `app.log`, `main_cli.log`).
*   This directory is included in `.gitignore`.

## Output Data

*   The `main.py` and `scheduler_app.py` scripts save fetched data directly into the PostgreSQL database.
*   The `output_data/` directory is now secondary and might be used for occasional manual exports if `storage_utils.py` functions are invoked.

## Data Flow

1.  **Configuration**: API keys, database credentials, and scheduler settings are loaded from the `.env` file.
2.  **Scheduler (`scheduler_app.py`)**:
    *   Periodically triggers data fetching jobs based on configured intervals.
    *   Calls functions in `src.binance_tracker.connectors.binance_connector` to get a Binance API client.
    *   Calls functions in `src.binance_tracker.core.data_fetcher` to fetch data (balance, positions, trades).
    *   The `data_fetcher` functions then use `src.binance_tracker.utils.database_utils` to interact with the PostgreSQL database (map API data to SQLAlchemy models and save them).
3.  **Manual Fetching (`main.py`)**:
    *   Can be run to perform on-demand data fetching.
    *   Also uses the same connector, data fetcher, and database utility modules to store data in PostgreSQL.
4.  **Logging**: All operations are logged to files in the `logs/` directory and to the console.

## Further Development (Roadmap Ideas)

This framework provides a solid foundation. Future enhancements could include:
*   More sophisticated data analysis and visualization tools (e.g., using libraries like Pandas, Matplotlib, or a web framework like Flask/Django).
*   Real-time data streaming and WebSocket integration for lower latency updates.
*   Strategy implementation and backtesting capabilities against the stored historical data.
*   A more comprehensive CLI with commands for querying the database or managing the scheduler.
*   A web-based UI for displaying data and interacting with the application.
*   Advanced error handling, retry mechanisms, and notification services.
*   Support for more data types from Binance (e.g., order book, klines).
```

## Database Schema
(Brief overview - for detailed schema, refer to `src/binance_tracker/utils/database_utils.py`)

*   `asset_balances`: Stores snapshots of account asset balances.
*   `positions`: Stores snapshots of open futures positions.
*   `trades`: Stores individual trade history, with unique constraint on Binance trade ID.
```
