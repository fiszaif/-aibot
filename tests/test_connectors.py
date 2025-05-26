import unittest
from unittest.mock import patch, MagicMock
import os
from src.binance_tracker.connectors.binance_connector import load_api_keys, get_binance_client
from binance.client import Client # Used for type hinting and potentially for mock instance checks

# Ensure the logger within binance_connector doesn't output during tests
# or is mocked if its output/behavior is part of a test.
# For now, we'll assume it's okay or mock it specifically if needed.

class TestBinanceConnector(unittest.TestCase):

    @patch.dict(os.environ, {'BINANCE_API_KEY': 'test_key', 'BINANCE_API_SECRET': 'test_secret'})
    def test_load_api_keys_success(self):
        """Test API keys are loaded successfully when environment variables are set."""
        api_key, api_secret = load_api_keys()
        self.assertEqual(api_key, 'test_key')
        self.assertEqual(api_secret, 'test_secret')

    @patch.dict(os.environ, {'BINANCE_API_SECRET': 'test_secret'}, clear=True)
    def test_load_api_keys_missing_key(self):
        """Test ValueError is raised if BINANCE_API_KEY is missing."""
        # Ensure BINANCE_API_KEY is not in environ for this test
        if 'BINANCE_API_KEY' in os.environ:
            del os.environ['BINANCE_API_KEY']
        
        with self.assertRaises(ValueError) as context:
            load_api_keys()
        self.assertIn("Binance API key or secret not found", str(context.exception))

    @patch.dict(os.environ, {'BINANCE_API_KEY': 'test_key'}, clear=True)
    def test_load_api_keys_missing_secret(self):
        """Test ValueError is raised if BINANCE_API_SECRET is missing."""
        # Ensure BINANCE_API_SECRET is not in os.environ for this test
        if 'BINANCE_API_SECRET' in os.environ:
            del os.environ['BINANCE_API_SECRET']

        with self.assertRaises(ValueError) as context:
            load_api_keys()
        self.assertIn("Binance API key or secret not found", str(context.exception))

    @patch('src.binance_tracker.connectors.binance_connector.Client')
    @patch('src.binance_tracker.connectors.binance_connector.load_api_keys')
    def test_get_binance_client_success(self, mock_load_api_keys, MockBinanceClient):
        """Test successful Binance client creation."""
        mock_load_api_keys.return_value = ('test_key', 'test_secret')
        mock_client_instance = MockBinanceClient.return_value # The instance returned by Client()
        
        client = get_binance_client(testnet=False)
        
        mock_load_api_keys.assert_called_once()
        MockBinanceClient.assert_called_once_with('test_key', 'test_secret', testnet=False)
        self.assertEqual(client, mock_client_instance)

    @patch('src.binance_tracker.connectors.binance_connector.Client')
    @patch('src.binance_tracker.connectors.binance_connector.load_api_keys')
    def test_get_binance_client_testnet(self, mock_load_api_keys, MockBinanceClient):
        """Test successful Binance client creation for testnet."""
        mock_load_api_keys.return_value = ('test_key', 'test_secret')
        mock_client_instance = MockBinanceClient.return_value
        
        client = get_binance_client(testnet=True)
        
        mock_load_api_keys.assert_called_once()
        # The implementation re-initializes client with testnet=True
        # So, Client(api_key, api_secret) might be called first, then Client(api_key, api_secret, testnet=True)
        # The provided solution for binance_connector.py initializes with testnet=True directly if testnet is True.
        MockBinanceClient.assert_called_once_with('test_key', 'test_secret', testnet=True)
        self.assertEqual(client, mock_client_instance)

    @patch('src.binance_tracker.connectors.binance_connector.load_api_keys')
    def test_get_binance_client_api_key_error(self, mock_load_api_keys):
        """Test client creation failure when API keys are missing."""
        mock_load_api_keys.side_effect = ValueError("API key error")
        
        with self.assertRaises(ValueError): # As per implementation, it re-raises ValueError
            get_binance_client()
        
        # Check if logger.error was called (optional, requires more mocking if logger is complex)
        # For now, focus on the ValueError being raised.

    @patch('src.binance_tracker.connectors.binance_connector.Client')
    @patch('src.binance_tracker.connectors.binance_connector.load_api_keys')
    def test_get_binance_client_connection_error(self, mock_load_api_keys, MockBinanceClient):
        """Test client creation failure on connection error."""
        mock_load_api_keys.return_value = ('test_key', 'test_secret')
        MockBinanceClient.side_effect = Exception("Connection failed") # Simulate a generic connection error
        
        client = get_binance_client()
        
        self.assertIsNone(client) # As per implementation, returns None on general Exception
        # Check if logger.error was called (optional)

if __name__ == '__main__':
    unittest.main()
