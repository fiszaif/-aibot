from datetime import datetime
from sqlalchemy.orm import Session
from binance.exceptions import BinanceAPIException, BinanceRequestException

from ..connectors.binance_connector import get_binance_client # Keep for __main__ test block
from ..utils.logging_utils import setup_logger
from ..utils.database_utils import AssetBalance, Position, Trade # Removed get_db for direct import in __main__

logger = setup_logger(__name__)

def get_futures_account_balance(client, db: Session):
    """
    Fetches the futures account balance from Binance, saves it to the database,
    and returns a list of saved AssetBalance model instances.

    Args:
        client: Binance API client instance.
        db: SQLAlchemy Session object.

    Returns:
        list[AssetBalance]: A list of AssetBalance model instances that were saved.
                            Returns an empty list if an error occurs or no balances are found.
    """
    try:
        api_balances = client.futures_account_balance()
        logger.debug(f"Successfully fetched {len(api_balances)} asset balances from API.")
        
        saved_balances = []
        db_balance_objects = []
        for b_data in api_balances:
            balance_obj = AssetBalance(
                asset=b_data['asset'],
                balance=float(b_data['balance']), # This is 'walletBalance' or total balance
                wallet_balance=float(b_data.get('walletBalance', b_data['balance'])), # Explicit
                cross_wallet_balance=float(b_data.get('crossWalletBalance', 0)), # May not always be present
                available_balance=float(b_data.get('availableBalance', b_data.get('balance', 0))), # Fallback
                timestamp=datetime.utcnow(), # Snapshot time
                account_type="FUTURES" # As per context
            )
            db_balance_objects.append(balance_obj)
        
        if db_balance_objects:
            db.add_all(db_balance_objects)
            db.commit()
            for obj in db_balance_objects: # Ensure IDs are loaded after commit for return
                db.refresh(obj)
            saved_balances.extend(db_balance_objects)
            logger.info(f"Saved {len(saved_balances)} asset balances to the database.")
        
        return saved_balances
    except BinanceAPIException as e:
        logger.error(f"Binance API Exception while fetching account balance: {e}", exc_info=True)
        if db: db.rollback()
        return []
    except BinanceRequestException as e:
        logger.error(f"Binance Request Exception while fetching account balance: {e}", exc_info=True)
        if db: db.rollback()
        return []
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching/saving account balance: {e}", exc_info=True)
        if db: db.rollback()
        return []

def get_futures_open_positions(client, db: Session):
    """
    Fetches current open positions from Binance, saves them to the database,
    and returns a list of saved Position model instances.

    Args:
        client: Binance API client instance.
        db: SQLAlchemy Session object.

    Returns:
        list[Position]: A list of Position model instances that were saved.
                        Returns an empty list if an error occurs or no open positions are found.
    """
    try:
        api_positions = client.futures_position_information()
        # Filter out positions with zero amount as per original logic
        open_api_positions = [p for p in api_positions if float(p.get('positionAmt', 0)) != 0]
        logger.debug(f"Successfully fetched {len(open_api_positions)} open positions from API.")

        saved_positions = []
        db_position_objects = []
        for p_data in open_api_positions:
            pos_obj = Position(
                symbol=p_data['symbol'],
                position_amount=float(p_data['positionAmt']),
                entry_price=float(p_data['entryPrice']),
                mark_price=float(p_data.get('markPrice', 0.0)), # Use .get for optional fields
                unrealized_profit=float(p_data.get('unRealizedProfit', 0.0)),
                leverage=p_data['leverage'],
                margin_type=p_data['marginType'],
                isolated_wallet=float(p_data.get('isolatedWallet', 0.0)),
                position_side=p_data['positionSide'],
                timestamp=datetime.utcnow() # Snapshot time
            )
            db_position_objects.append(pos_obj)

        if db_position_objects:
            db.add_all(db_position_objects)
            db.commit()
            for obj in db_position_objects:
                db.refresh(obj)
            saved_positions.extend(db_position_objects)
            logger.info(f"Saved {len(saved_positions)} open positions to the database.")
            
        return saved_positions
    except BinanceAPIException as e:
        logger.error(f"Binance API Exception while fetching open positions: {e}", exc_info=True)
        if db: db.rollback()
        return []
    except BinanceRequestException as e:
        logger.error(f"Binance Request Exception while fetching open positions: {e}", exc_info=True)
        if db: db.rollback()
        return []
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching/saving open positions: {e}", exc_info=True)
        if db: db.rollback()
        return []

def get_futures_recent_trades(client, db: Session, symbol, limit=50):
    """
    Fetches recent trades for a specific symbol from Binance, saves new trades to the database,
    and returns a list of newly saved Trade model instances.

    Args:
        client: Binance API client instance.
        db: SQLAlchemy Session object.
        symbol (str): The trading symbol (e.g., 'BTCUSDT').
        limit (int, optional): The number of recent trades to fetch. Defaults to 50.

    Returns:
        list[Trade]: A list of Trade model instances that were newly saved.
                     Returns an empty list if an error occurs or no new trades are found/saved.
    """
    try:
        api_trades = client.futures_account_trades(symbol=symbol, limit=limit)
        logger.debug(f"Successfully fetched {len(api_trades)} trades for symbol {symbol} from API.")

        saved_trades = []
        db_trade_objects = []
        for t_data in api_trades:
            binance_trade_id = str(t_data['id']) # Ensure it's a string for DB
            
            # Check if trade already exists
            exists = db.query(Trade).filter(Trade.binance_trade_id == binance_trade_id).first()
            if exists:
                logger.debug(f"Trade with Binance ID {binance_trade_id} for symbol {symbol} already exists. Skipping.")
                continue

            trade_obj = Trade(
                binance_trade_id=binance_trade_id,
                symbol=t_data['symbol'],
                order_id=str(t_data['orderId']), # Ensure string
                side=t_data['side'],
                price=float(t_data['price']),
                quantity=float(t_data['qty']),
                realized_pnl=float(t_data['realizedPnl']),
                commission=float(t_data['commission']),
                commission_asset=t_data['commissionAsset'],
                # Convert Binance's millisecond timestamp to datetime
                trade_time=datetime.fromtimestamp(int(t_data['time']) / 1000.0),
                is_maker=t_data.get('maker', False), # Default to False if not present
                timestamp=datetime.utcnow() # Record ingestion time
            )
            db_trade_objects.append(trade_obj)

        if db_trade_objects:
            db.add_all(db_trade_objects)
            db.commit()
            for obj in db_trade_objects:
                db.refresh(obj)
            saved_trades.extend(db_trade_objects)
            logger.info(f"Saved {len(saved_trades)} new trades for symbol {symbol} to the database.")
            
        return saved_trades
    except BinanceAPIException as e:
        logger.error(f"Binance API Exception while fetching recent trades for {symbol}: {e}", exc_info=True)
        if db: db.rollback()
        return []
    except BinanceRequestException as e:
        logger.error(f"Binance Request Exception while fetching recent trades for {symbol}: {e}", exc_info=True)
        if db: db.rollback()
        return []
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching/saving recent trades for {symbol}: {e}", exc_info=True)
        if db: db.rollback()
        return []

if __name__ == '__main__':
    # This section is for basic testing and will require a .env file with API keys
    # and database configuration in the project root directory.
    from ..utils.database_utils import get_db, create_db_tables # Corrected import for get_db

    test_logger = setup_logger('data_fetcher_test', log_file='data_fetcher_test.log')
    test_logger.info("Attempting to test data fetcher functions with DB integration...")
    test_logger.info("Ensure .env is set up for API keys AND database in the project root.")

    # Create tables if they don't exist (idempotent)
    try:
        create_db_tables()
        test_logger.info("Database tables checked/created.")
    except Exception as e_db_create:
        test_logger.error(f"Failed to create/check database tables: {e_db_create}", exc_info=True)
        # Exit if DB setup fails, as tests below depend on it.
        exit()


    binance_client = None
    try:
        # Using testnet=True for safety, ensure API keys are for testnet if running this.
        binance_client = get_binance_client(testnet=True) 
    except ValueError as ve:
        test_logger.error(f"Configuration Error (API Keys): {ve}", exc_info=True)
    except Exception as e_client:
        test_logger.error(f"Failed to initialize Binance client: {e_client}", exc_info=True)

    if binance_client:
        with get_db() as db_session:
            if not db_session:
                test_logger.error("Failed to acquire database session. Aborting tests.")
                exit()

            test_logger.info("Fetching and saving futures account balance...")
            saved_balances = get_futures_account_balance(binance_client, db_session)
            if saved_balances:
                for b in saved_balances:
                    test_logger.info(f"  Saved Balance - Asset: {b.asset}, DB ID: {b.id}, Balance: {b.balance}")
            else:
                test_logger.warning("No balance information saved or an error occurred.")

            test_logger.info("Fetching and saving futures open positions...")
            saved_positions = get_futures_open_positions(binance_client, db_session)
            if saved_positions:
                for p in saved_positions:
                    test_logger.info(f"  Saved Position - Symbol: {p.symbol}, DB ID: {p.id}, Amount: {p.position_amount}")
            else:
                test_logger.warning("No open positions saved or an error occurred.")

            test_symbol = 'BTCUSDT' # Use a symbol active on testnet if possible
            test_logger.info(f"Fetching and saving recent trades for {test_symbol}...")
            saved_trades = get_futures_recent_trades(binance_client, db_session, symbol=test_symbol, limit=10)
            if saved_trades:
                for t in saved_trades:
                    test_logger.info(f"  Saved Trade - Symbol: {t.symbol}, DB ID: {t.id}, Binance Trade ID: {t.binance_trade_id}")
            else:
                test_logger.warning(f"No new recent trades saved for {test_symbol} or an error occurred.")
    else:
        test_logger.error("Binance client not initialized. Skipping data fetching tests.")

    test_logger.info("Data fetcher tests with DB integration finished.")
