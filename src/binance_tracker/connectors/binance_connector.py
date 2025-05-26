import os
from binance.client import Client
from dotenv import load_dotenv
from ..utils.logging_utils import setup_logger

logger = setup_logger(__name__)

def load_api_keys():
    """
    Loads Binance API key and secret from .env file.

    Raises:
        ValueError: If API key or secret is not found in environment variables.

    Returns:
        tuple: API key and secret.
    """
    load_dotenv()
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")

    if not api_key or not api_secret:
        msg = ("Binance API key or secret not found. "
               "Please create a .env file in the project root directory with your "
               "BINANCE_API_KEY and BINANCE_API_SECRET.")
        logger.error(msg)
        raise ValueError(msg)
    logger.info("API keys loaded successfully.")
    return api_key, api_secret

def get_binance_client(testnet=False):
    """
    Initializes and returns a Binance API client.

    Args:
        testnet (bool, optional): Whether to use the testnet. Defaults to False.

    Returns:
        binance.client.Client or None: Binance API client instance, or None if initialization fails.
    """
    try:
        api_key, api_secret = load_api_keys()
        client = Client(api_key, api_secret)
        if testnet:
            # For spot/margin/savings/mining testnet, the URL is set via client.API_URL
            # For futures testnet, it's often a different parameter during Client initialization
            # or a different base URL entirely. The python-binance library documentation
            # should be consulted for the most up-to-date way to specify futures testnet.
            # Assuming Client handles testnet for futures correctly when testnet=True,
            # or that spot testnet URL is acceptable for now.
            # If specific futures testnet is needed, this might need adjustment.
            # client.API_URL = Client.API_TESTNET_URL # This is for spot testnet
            # For futures, it might be something like:
            # client = Client(api_key, api_secret, testnet=True) # if library supports it directly
            # or client = Client(api_key, api_secret, base_url='https://testnet.binancefuture.com') # if specific base_url is needed
            
            # Based on python-binance documentation, setting testnet=True in the Client constructor
            # is the standard way to use the testnet for SPOT, MARGIN, FUTURES.
            # The library then directs requests to the appropriate testnet URLs.
            # So, we re-initialize the client with testnet=True
            client = Client(api_key, api_secret, testnet=True)

        # Verify connection (optional, but good for immediate feedback)
        # client.ping() # Optional: can be noisy, consider logging success after a specific successful call
        # logger.info("Successfully connected to Binance API after ping.")
        logger.info(f"Binance client initialized. Testnet: {testnet}")
        return client
    except ValueError as ve:
        # This specific ValueError is from load_api_keys, which already logs the error.
        # We re-raise it to signal the caller that setup failed.
        # If we caught other ValueErrors here, we would log them: logger.error(f"Configuration Error: {ve}")
        raise
    except Exception as e:
        # Catching a general exception for other issues like connection problems
        logger.error(f"Error connecting to Binance API: {e}", exc_info=True)
        # Depending on desired behavior, either re-raise or return None
        # For this task, let's return None to indicate failure without stopping caller if they can handle it
        return None
