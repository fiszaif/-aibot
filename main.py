import os
from src.binance_tracker.utils.logging_utils import setup_logger
from src.binance_tracker.connectors.binance_connector import get_binance_client
# Ensure this import is after dotenv loading if tests are run from here,
# but for integration tests, .env.test is loaded by the test script.
from src.binance_tracker.core.data_fetcher import (
    get_futures_account_balance,
    get_futures_open_positions,
    get_futures_recent_trades,
)
# from src.binance_tracker.utils.storage_utils import save_to_json, save_to_csv # No longer primary storage
from src.binance_tracker.utils.database_utils import get_db, create_db_tables
# Models are not directly used in main.py but are essential for data_fetcher and db operations
# from src.binance_tracker.utils.database_utils import AssetBalance, Position, Trade 

# Setup logger for the main script
logger = setup_logger('main_script', log_file='main_cli.log')

def run_on_demand_fetch(test_mode=False):
    """
    Core logic for fetching and saving Binance data on demand.
    Can be called from main() or integration tests.

    Args:
        test_mode (bool): If True, might use specific test configurations (e.g., test symbols).
                          Currently, uses SCHED_USE_TESTNET and SCHED_TRADE_SYMBOLS from .env.
    """
    logger.info("Running on-demand fetch...")

    # Configuration for fetching (could be adapted further for test_mode if needed)
    # For now, test_mode implies using testnet if SCHED_USE_TESTNET is True
    # and specific symbols if SCHED_TRADE_SYMBOLS is set.
    use_testnet_str = os.getenv("SCHED_USE_TESTNET", "True").lower()
    use_testnet = use_testnet_str == 'true'
    
    default_symbols = "BTCUSDT,ETHUSDT" # Default if not in .env
    trade_symbols_str = os.getenv("SCHED_TRADE_SYMBOLS", default_symbols)
    if test_mode and not trade_symbols_str: # Ensure there's a symbol for testing trades
        trade_symbols_str = default_symbols
    trade_symbols = [symbol.strip() for symbol in trade_symbols_str.split(',')]
    
    sample_symbol_for_trades = trade_symbols[0] if trade_symbols else "BTCUSDT" # Use first configured symbol or default

    logger.info(f"On-demand fetch configured for Testnet: {use_testnet}, Trade Symbol: {sample_symbol_for_trades}")

    # --- Initialize Binance Client ---
    logger.info(f"Attempting to connect to Binance (Testnet: {use_testnet})...")
    client = None
    try:
        client = get_binance_client(testnet=use_testnet)
    except ValueError as ve: 
        logger.error(f"Critical setup error (API Keys): {ve}")
        print(f"Error: {ve}") 
        return False # Indicate failure
    
    if not client:
        logger.error("Failed to initialize Binance client. Check logs for details.")
        print("Failed to initialize Binance client.")
        return False # Indicate failure

    logger.info("Successfully connected to Binance API.")

    # --- Process Data with Database Session ---
    success_overall = True
    with get_db() as db_session:
        if not db_session:
            logger.error("Failed to acquire database session.")
            print("Critical error: Could not get a database session.")
            return False # Indicate failure

        # Fetch and Save Account Balance
        logger.info("Fetching Futures Account Balance...")
        saved_balances = get_futures_account_balance(client, db_session)
        if saved_balances:
            logger.info(f"Saved {len(saved_balances)} asset balances.")
            print("\n--- Futures Account Balance (from DB) ---")
            for item in saved_balances: print(f"  Asset: {item.asset}, Balance: {item.balance}, DB ID: {item.id}")
        else:
            logger.warning("Could not fetch/save account balance or no balance found.")
            success_overall = False # Mark as partial failure if expected data isn't fetched

        # Fetch and Save Open Positions
        logger.info("Fetching Futures Open Positions...")
        saved_positions = get_futures_open_positions(client, db_session)
        if saved_positions:
            logger.info(f"Saved {len(saved_positions)} open positions.")
            print("\n--- Futures Open Positions (from DB) ---")
            for item in saved_positions: print(f"  Symbol: {item.symbol}, Amount: {item.position_amount}, DB ID: {item.id}")
        else:
            logger.info("No open positions found/saved or an error occurred.")
            # Not necessarily a failure if there are genuinely no open positions.

        # Fetch and Save Recent Trades for the sample/configured symbol
        logger.info(f"Fetching Recent Trades for {sample_symbol_for_trades} (limit 10)...")
        saved_trades = get_futures_recent_trades(client, db_session, symbol=sample_symbol_for_trades, limit=10)
        if saved_trades:
            logger.info(f"Saved {len(saved_trades)} new trades for {sample_symbol_for_trades}.")
            print(f"\n--- Recent Trades for {sample_symbol_for_trades} (newly saved to DB) ---")
            for item in saved_trades: print(f"  Symbol: {item.symbol}, Binance Trade ID: {item.binance_trade_id}, DB ID: {item.id}")
        else:
            logger.info(f"No new recent trades found/saved for {sample_symbol_for_trades}.")
            # Not necessarily a failure.
            
    logger.info("On-demand fetch finished.")
    return success_overall

def main():
    """
    Main entry point for the CLI application.
    Ensures DB tables are created and then runs the on-demand fetch.
    """
    logger.info("Starting Binance Tracker CLI (main.py)...")

    # --- Database Setup ---
    try:
        logger.info("Ensuring database tables are created...")
        create_db_tables() # Uses engine from database_utils
    except Exception as e:
        logger.error(f"Failed to create or check database tables: {e}", exc_info=True)
        logger.error("Please ensure your PostgreSQL server is running and configured correctly in .env.")
        print("Critical error: Could not connect to or set up the database. Check logs. Exiting.")
        return

    # --- Run the main fetching logic ---
    if run_on_demand_fetch():
        print("\nOn-demand data fetch completed successfully (data saved to DB).")
    else:
        print("\nOn-demand data fetch encountered issues. Check logs for details.")

if __name__ == "__main__":
    main()
