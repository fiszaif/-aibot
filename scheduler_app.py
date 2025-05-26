import os
import time
import sys
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

from src.binance_tracker.connectors.binance_connector import get_binance_client
from src.binance_tracker.core.data_fetcher import (
    get_futures_account_balance,
    get_futures_open_positions,
    get_futures_recent_trades,
)
from src.binance_tracker.utils.database_utils import get_db, create_db_tables
from src.binance_tracker.utils.logging_utils import setup_logger

# Load environment variables from .env file
load_dotenv()

# Initialize logger for the scheduler application
scheduler_logger = setup_logger('scheduler_app', log_file='scheduler.log')

# --- Retrieve Scheduler Configurations ---
SCHED_BALANCE_INTERVAL_MINUTES = int(os.getenv("SCHED_BALANCE_INTERVAL_MINUTES", "15"))
SCHED_POSITIONS_INTERVAL_MINUTES = int(os.getenv("SCHED_POSITIONS_INTERVAL_MINUTES", "5"))
SCHED_TRADES_INTERVAL_MINUTES = int(os.getenv("SCHED_TRADES_INTERVAL_MINUTES", "10"))
SCHED_TRADE_SYMBOLS_STR = os.getenv("SCHED_TRADE_SYMBOLS", "BTCUSDT,ETHUSDT")
SCHED_TRADE_SYMBOLS = [symbol.strip() for symbol in SCHED_TRADE_SYMBOLS_STR.split(',')]
# Convert 'true'/'false' string from .env to boolean
SCHED_USE_TESTNET_STR = os.getenv("SCHED_USE_TESTNET", "True").lower()
SCHED_USE_TESTNET = SCHED_USE_TESTNET_STR == 'true'
SCHED_TRADES_LIMIT = int(os.getenv("SCHED_TRADES_LIMIT", "50")) # Optional: make limit configurable

scheduler_logger.info(f"Scheduler configured with intervals (Balance: {SCHED_BALANCE_INTERVAL_MINUTES}m, Positions: {SCHED_POSITIONS_INTERVAL_MINUTES}m, Trades: {SCHED_TRADES_INTERVAL_MINUTES}m)")
scheduler_logger.info(f"Trade symbols: {SCHED_TRADE_SYMBOLS}, Trades fetch limit: {SCHED_TRADES_LIMIT}")
scheduler_logger.info(f"Using Testnet for scheduled jobs: {SCHED_USE_TESTNET}")


# --- Define Job Functions ---

def fetch_and_store_balance_job():
    """Job to fetch and store account balance."""
    scheduler_logger.info("Starting 'fetch_and_store_balance_job'...")
    client = None
    try:
        client = get_binance_client(testnet=SCHED_USE_TESTNET)
        if not client:
            scheduler_logger.error("Failed to get Binance client for balance job. API keys might be missing or connection failed.")
            return

        with get_db() as db_session:
            if not db_session:
                scheduler_logger.error("Failed to get DB session for balance job.")
                return
            
            saved_balances = get_futures_account_balance(client, db_session)
            scheduler_logger.info(f"Balance job: Successfully processed and saved {len(saved_balances)} balance entries.")

    except Exception as e:
        scheduler_logger.error(f"Error in 'fetch_and_store_balance_job': {e}", exc_info=True)
    finally:
        scheduler_logger.info("Finished 'fetch_and_store_balance_job'.")


def fetch_and_store_positions_job():
    """Job to fetch and store open positions."""
    scheduler_logger.info("Starting 'fetch_and_store_positions_job'...")
    client = None
    try:
        client = get_binance_client(testnet=SCHED_USE_TESTNET)
        if not client:
            scheduler_logger.error("Failed to get Binance client for positions job.")
            return

        with get_db() as db_session:
            if not db_session:
                scheduler_logger.error("Failed to get DB session for positions job.")
                return
            
            saved_positions = get_futures_open_positions(client, db_session)
            scheduler_logger.info(f"Positions job: Successfully processed and saved {len(saved_positions)} open positions.")

    except Exception as e:
        scheduler_logger.error(f"Error in 'fetch_and_store_positions_job': {e}", exc_info=True)
    finally:
        scheduler_logger.info("Finished 'fetch_and_store_positions_job'.")


def fetch_and_store_trades_job():
    """Job to fetch and store recent trades for configured symbols."""
    scheduler_logger.info("Starting 'fetch_and_store_trades_job'...")
    client = None
    try:
        client = get_binance_client(testnet=SCHED_USE_TESTNET)
        if not client:
            scheduler_logger.error("Failed to get Binance client for trades job.")
            return

        with get_db() as db_session:
            if not db_session:
                scheduler_logger.error("Failed to get DB session for trades job.")
                return
            
            total_new_trades_saved = 0
            for symbol in SCHED_TRADE_SYMBOLS:
                scheduler_logger.debug(f"Trades job: Fetching trades for symbol {symbol}...")
                try:
                    saved_trades = get_futures_recent_trades(client, db_session, symbol=symbol, limit=SCHED_TRADES_LIMIT)
                    if saved_trades: # Only log if non-zero trades were saved to reduce noise
                        scheduler_logger.info(f"Trades job: Successfully processed and saved {len(saved_trades)} new trades for symbol {symbol}.")
                        total_new_trades_saved += len(saved_trades)
                    else:
                        scheduler_logger.info(f"Trades job: No new trades found or saved for symbol {symbol}.")
                except Exception as e_symbol: # Catch error per symbol to allow other symbols to be processed
                    scheduler_logger.error(f"Trades job: Error processing symbol {symbol}: {e_symbol}", exc_info=True)
            scheduler_logger.info(f"Trades job: Total new trades saved across all symbols: {total_new_trades_saved}.")

    except Exception as e:
        scheduler_logger.error(f"Error in 'fetch_and_store_trades_job' (outer scope): {e}", exc_info=True)
    finally:
        scheduler_logger.info("Finished 'fetch_and_store_trades_job'.")


# --- Main Execution Block ---

if __name__ == '__main__':
    scheduler_logger.info("Scheduler application starting...")

    # Ensure database tables are ready before starting the scheduler
    try:
        scheduler_logger.info("Initializing database and ensuring tables are created...")
        create_db_tables()
        scheduler_logger.info("Database tables checked/created successfully.")
    except Exception as e_db:
        scheduler_logger.error(f"Critical error: Failed to initialize database tables: {e_db}", exc_info=True)
        scheduler_logger.error("Please ensure your PostgreSQL server is running and configured correctly in .env. Exiting.")
        sys.exit(1) # Exit if DB setup fails

    scheduler = BackgroundScheduler(timezone="UTC") # Use UTC for consistency

    # Add jobs to the scheduler
    scheduler.add_job(fetch_and_store_balance_job, trigger='interval', minutes=SCHED_BALANCE_INTERVAL_MINUTES, id='balance_job')
    scheduler.add_job(fetch_and_store_positions_job, trigger='interval', minutes=SCHED_POSITIONS_INTERVAL_MINUTES, id='positions_job')
    scheduler.add_job(fetch_and_store_trades_job, trigger='interval', minutes=SCHED_TRADES_INTERVAL_MINUTES, id='trades_job')
    
    scheduler_logger.info(
        f"Jobs scheduled: Balance ({SCHED_BALANCE_INTERVAL_MINUTES}m), "
        f"Positions ({SCHED_POSITIONS_INTERVAL_MINUTES}m), "
        f"Trades ({SCHED_TRADES_INTERVAL_MINUTES}m for symbols {SCHED_TRADE_SYMBOLS})."
    )

    scheduler.start()
    scheduler_logger.info("Scheduler started. Press Ctrl+C to exit.")

    try:
        # Keep the main thread alive
        while True:
            time.sleep(2) # Check for interrupt every 2 seconds
    except (KeyboardInterrupt, SystemExit):
        scheduler_logger.info("Scheduler shutting down...")
        scheduler.shutdown()
        scheduler_logger.info("Scheduler shutdown complete.")
        sys.exit(0)
    except Exception as e_main:
        scheduler_logger.error(f"An unexpected error occurred in the main scheduler loop: {e_main}", exc_info=True)
        scheduler.shutdown()
        scheduler_logger.info("Scheduler shutdown due to unexpected error.")
        sys.exit(1)
