import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Import logger from logging_utils
from .logging_utils import setup_logger
logger = setup_logger(__name__, log_file='database_utils.log')


def get_database_url():
    """
    Loads .env variables and constructs the DATABASE_URL string.
    Prioritizes a full DATABASE_URL if set, otherwise constructs from components.
    Uses default values if components are not set.
    """
    load_dotenv() # Load environment variables from .env file

    db_url = os.getenv("DATABASE_URL")
    if db_url:
        logger.info("Using DATABASE_URL from environment.")
        return db_url

    # Fallback to individual components or defaults
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_user = os.getenv("DB_USER", "your_db_user")
    db_password = os.getenv("DB_PASSWORD", "your_db_password")
    db_name = os.getenv("DB_NAME", "binance_tracker_db")

    constructed_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    logger.info(f"Constructed DATABASE_URL: postgresql://{db_user}:****@{db_host}:{db_port}/{db_name}")
    return constructed_url

# Initialize SQLAlchemy components
DATABASE_URL = get_database_url()
try:
    engine = create_engine(DATABASE_URL)
    logger.info("Database engine created successfully.")
except Exception as e:
    logger.error(f"Failed to create database engine: {e}", exc_info=True)
    # Depending on the application's needs, you might want to exit or raise the exception.
    # For now, we'll let it proceed so that models can be defined, but operations will fail.
    engine = None # Ensure engine is None if creation fails

Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- SQLAlchemy Models ---

class AssetBalance(Base):
    __tablename__ = "asset_balances"

    id = Column(Integer, primary_key=True, index=True)
    asset = Column(String, index=True, nullable=False)
    balance = Column(Float, nullable=False) # This is 'walletBalance' for futures usually
    wallet_balance = Column(Float, nullable=True) # Explicitly naming for clarity
    cross_wallet_balance = Column(Float, nullable=True)
    available_balance = Column(Float, nullable=True) # Often same as balance for futures
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    account_type = Column(String, default="FUTURES", nullable=False)

    def __repr__(self):
        return f"<AssetBalance(asset='{self.asset}', balance={self.balance}, timestamp='{self.timestamp}')>"

class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True, nullable=False)
    position_amount = Column(Float, nullable=False)  # 'positionAmt'
    entry_price = Column(Float, nullable=False)      # 'entryPrice'
    mark_price = Column(Float, nullable=True)        # 'markPrice'
    unrealized_profit = Column(Float, nullable=True) # 'unRealizedProfit'
    leverage = Column(String, nullable=False)        # 'leverage'
    margin_type = Column(String, nullable=False)     # 'marginType' (cross or isolated)
    isolated_wallet = Column(Float, nullable=True)   # 'isolatedWallet'
    position_side = Column(String, nullable=False)   # 'positionSide' (BOTH, LONG, SHORT)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # A position for a symbol on a given side should be unique at a specific timestamp.
    # However, since we are inserting new records over time, this constraint might be too strict
    # if we want to keep historical snapshots. For now, we'll make it unique on symbol, side, and timestamp.
    # A better approach for tracking changes might be to update existing active positions or use a separate history table.
    __table_args__ = (UniqueConstraint('symbol', 'position_side', 'timestamp', name='_symbol_side_timestamp_uc'),)

    def __repr__(self):
        return f"<Position(symbol='{self.symbol}', amount={self.position_amount}, side='{self.position_side}', timestamp='{self.timestamp}')>"

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    binance_trade_id = Column(String, unique=True, index=True, nullable=False) # 'id' from Binance
    symbol = Column(String, index=True, nullable=False)
    order_id = Column(String, index=True, nullable=False) # 'orderId'
    side = Column(String, nullable=False)                 # 'side' (BUY/SELL)
    price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)              # 'qty'
    realized_pnl = Column(Float, nullable=False)          # 'realizedPnl'
    commission = Column(Float, nullable=False)
    commission_asset = Column(String, nullable=False)
    trade_time = Column(DateTime, index=True, nullable=False) # 'time' from Binance (convert from ms timestamp)
    is_maker = Column(Boolean, nullable=True)                 # 'maker' from Binance
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False) # Record ingestion time

    def __repr__(self):
        return f"<Trade(symbol='{self.symbol}', id={self.binance_trade_id}, time='{self.trade_time}')>"


# --- Database Utility Functions ---

def create_db_tables():
    """Creates all database tables defined in Base metadata."""
    if not engine:
        logger.error("Database engine is not initialized. Cannot create tables.")
        return
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully (if they didn't exist).")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}", exc_info=True)

def get_db():
    """
    Provides a database session context.
    Usage: with get_db() as db: ...
    """
    if not SessionLocal:
        logger.error("SessionLocal is not initialized. Cannot get DB session.")
        # This might happen if engine creation failed.
        # You might want to raise an exception or handle this state appropriately.
        # For now, yielding None to prevent further errors down the line if db is used.
        yield None 
        return

    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Exception during database session: {e}", exc_info=True)
        db.rollback() # Rollback in case of error
        raise # Re-raise the exception to be handled by the caller
    finally:
        db.close()

if __name__ == '__main__':
    logger.info("Running database_utils.py directly.")
    logger.info("Attempting to create database tables...")
    # The engine might be None if get_database_url() had issues or create_engine failed.
    if engine:
        create_db_tables()
        logger.info("Table creation process finished. Check logs for details.")
        
        # Example of using get_db (optional, for testing connection)
        logger.info("Testing database connection by acquiring a session...")
        try:
            with get_db() as db:
                if db:
                    # Try a simple query
                    db.execute("SELECT 1")
                    logger.info("Successfully connected to the database and executed a test query.")
                else:
                    logger.error("Failed to acquire database session for testing.")
        except Exception as e:
            logger.error(f"Failed to connect to the database during test: {e}", exc_info=True)
            logger.error("Please ensure your PostgreSQL server is running and configured correctly in .env.")
    else:
        logger.error("Database engine is not available. Cannot run table creation or tests.")
        logger.error("Please check your .env configuration and PostgreSQL server status.")
