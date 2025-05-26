import os
from src.binance_tracker.utils.logging_utils import setup_logger
from src.binance_tracker.connectors.binance_connector import get_binance_client
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

def main():
    """
    Main function to run the Binance Tracker CLI.
    Fetches account information, positions, and trades, then saves them to PostgreSQL.
    """
    logger.info("Starting Binance Tracker CLI...")

    # --- Database Setup ---
    try:
        logger.info("Ensuring database tables are created...")
        create_db_tables() # Idempotent - creates tables if they don't exist
    except Exception as e:
        logger.error(f"Failed to create or check database tables: {e}", exc_info=True)
        logger.error("Please ensure your PostgreSQL server is running and configured correctly in .env.")
        print("Critical error: Could not connect to or set up the database. Check logs and .env settings. Exiting.")
        return # Exit script if DB setup fails

    # --- Configuration ---
    # output_dir = "output_data" # No longer primary, but could be used for exports
    # os.makedirs(output_dir, exist_ok=True) 
    
    sample_symbol = "BTCUSDT" 
    use_testnet = True # Set to False for Mainnet, ensure API keys match

    # --- Initialize Binance Client ---
    logger.info(f"Attempting to connect to Binance (Testnet: {use_testnet})...")
    logger.info("Please ensure your .env file is in the project root with BINANCE_API_KEY and BINANCE_API_SECRET.")
    client = None
    try:
        client = get_binance_client(testnet=use_testnet)
    except ValueError as ve: 
        logger.error(f"Critical setup error (API Keys): {ve}")
        print(f"Error: {ve}") 
        print("Please create a .env file in the project root with your BINANCE_API_KEY and BINANCE_API_SECRET.")
        print("You can copy config/.env.example to .env and fill in your details.")
        return 
    
    if not client:
        logger.error("Failed to initialize Binance client. Check logs for details.")
        print("Failed to initialize Binance client. Please check logs, network, or API key permissions.")
        return 

    logger.info("Successfully connected to Binance API.")

    # --- Process Data with Database Session ---
    with get_db() as db_session:
        if not db_session:
            logger.error("Failed to acquire database session. Cannot proceed with data fetching and saving.")
            print("Critical error: Could not get a database session. Check logs. Exiting.")
            return

        # --- Fetch and Save Account Balance ---
        logger.info("Fetching Futures Account Balance...")
        saved_balances = get_futures_account_balance(client, db_session)
        if saved_balances:
            logger.info(f"Successfully saved {len(saved_balances)} asset balances to the database.")
            print("\n--- Futures Account Balance (from DB) ---")
            for asset_model in saved_balances:
                # Displaying only assets with a non-zero total balance for brevity
                if asset_model.balance > 0:
                    print(f"  Asset: {asset_model.asset}, Balance: {asset_model.balance}, Available: {asset_model.available_balance}, DB ID: {asset_model.id}")
            # JSON/CSV saving removed, data is in PostgreSQL
            # save_to_json(balance_data, output_dir, "futures_balance.json")
            # save_to_csv(balance_data, output_dir, "futures_balance.csv")
        else:
            logger.warning("Could not fetch or save account balance, or no balance found.")
            print("Could not fetch account balance or no balance found.")

        # --- Fetch and Save Open Positions ---
        logger.info("Fetching Futures Open Positions...")
        saved_positions = get_futures_open_positions(client, db_session)
        if saved_positions:
            logger.info(f"Successfully saved {len(saved_positions)} open positions to the database.")
            print("\n--- Futures Open Positions (from DB) ---")
            for pos_model in saved_positions:
                print(f"  Symbol: {pos_model.symbol}, Amount: {pos_model.position_amount}, Entry: {pos_model.entry_price}, PNL: {pos_model.unrealized_profit}, DB ID: {pos_model.id}")
            # JSON/CSV saving removed
            # save_to_json(positions_data, output_dir, "futures_positions.json")
        else:
            logger.warning("No open positions found/saved or an error occurred.")
            print("No open positions found or an error occurred.")

        # --- Fetch and Save Recent Trades ---
        logger.info(f"Fetching Recent Trades for {sample_symbol} (limit 10)...")
        saved_trades = get_futures_recent_trades(client, db_session, symbol=sample_symbol, limit=10)
        if saved_trades:
            logger.info(f"Successfully saved {len(saved_trades)} new trades for {sample_symbol} to the database.")
            print(f"\n--- Recent Trades for {sample_symbol} (newly saved to DB) ---")
            for trade_model in saved_trades:
                print(f"  Symbol: {trade_model.symbol}, Binance Trade ID: {trade_model.binance_trade_id}, Side: {trade_model.side}, Price: {trade_model.price}, Qty: {trade_model.quantity}, PNL: {trade_model.realized_pnl}, DB ID: {trade_model.id}")
            # JSON/CSV saving removed
            # save_to_json(trades_data, output_dir, f"futures_trades_{sample_symbol}.json")
        else:
            logger.warning(f"No new recent trades found/saved for {sample_symbol} or an error occurred.")
            print(f"No new recent trades found for {sample_symbol} or an error occurred.")

    logger.info("Script finished. Data is saved in the PostgreSQL database.")
    print("\nScript finished. Data has been processed and saved to the PostgreSQL database.")
    # Reminder about output_data directory can be removed or modified if it's no longer used.
    # logger.info("Reminder: Ensure 'output_data/' is in .gitignore if it contains sensitive information.")
    # print("Please ensure 'output_data/' is added to your .gitignore file to avoid committing sensitive data if any real data is fetched.")

if __name__ == "__main__":
    main()
