import unittest
from unittest.mock import MagicMock, patch, call
from sqlalchemy.orm import Session # For spec in MagicMock
from binance.exceptions import BinanceAPIException, BinanceRequestException

from src.binance_tracker.core.data_fetcher import (
    get_futures_account_balance,
    get_futures_open_positions,
    get_futures_recent_trades,
)
from src.binance_tracker.utils.database_utils import AssetBalance, Position, Trade

# Mock the logger used in data_fetcher to prevent console output during tests
@patch('src.binance_tracker.core.data_fetcher.logger', MagicMock())
class TestDataFetcher(unittest.TestCase):

    def setUp(self):
        """Set up a mock Binance client and mock DB session before each test."""
        self.mock_client = MagicMock() # spec=Client could be used if Client class is imported
        self.mock_db_session = MagicMock(spec=Session)

    # --- Tests for get_futures_account_balance ---
    def test_get_futures_account_balance_success(self):
        mock_api_response = [
            {'asset': 'USDT', 'balance': '1000.00', 'walletBalance': '1000.00', 'crossWalletBalance': '1000.00', 'availableBalance': '1000.00'},
            {'asset': 'BTC', 'balance': '0.5', 'walletBalance': '0.5', 'crossWalletBalance': '0.5', 'availableBalance': '0.5'}
        ]
        self.mock_client.futures_account_balance.return_value = mock_api_response
        
        result = get_futures_account_balance(self.mock_client, self.mock_db_session)
        
        self.mock_client.futures_account_balance.assert_called_once()
        self.mock_db_session.add_all.assert_called_once()
        # Check if objects passed to add_all are AssetBalance instances
        added_objects = self.mock_db_session.add_all.call_args[0][0]
        self.assertTrue(all(isinstance(obj, AssetBalance) for obj in added_objects))
        self.assertEqual(len(added_objects), 2)
        self.assertEqual(added_objects[0].asset, 'USDT')
        self.mock_db_session.commit.assert_called_once()
        self.assertEqual(len(result), 2)
        self.assertTrue(all(isinstance(r, AssetBalance) for r in result))

    def test_get_futures_account_balance_api_error(self):
        self.mock_client.futures_account_balance.side_effect = BinanceAPIException("API Error")
        result = get_futures_account_balance(self.mock_client, self.mock_db_session)
        self.mock_client.futures_account_balance.assert_called_once()
        self.mock_db_session.rollback.assert_called_once()
        self.mock_db_session.add_all.assert_not_called()
        self.mock_db_session.commit.assert_not_called()
        self.assertEqual(result, [])

    def test_get_futures_account_balance_db_error(self):
        mock_api_response = [{'asset': 'USDT', 'balance': '1000.00', 'walletBalance': '1000.00'}]
        self.mock_client.futures_account_balance.return_value = mock_api_response
        self.mock_db_session.commit.side_effect = Exception("DB Commit Error")
        
        result = get_futures_account_balance(self.mock_client, self.mock_db_session)
        
        self.mock_client.futures_account_balance.assert_called_once()
        self.mock_db_session.add_all.assert_called_once()
        self.mock_db_session.commit.assert_called_once()
        self.mock_db_session.rollback.assert_called_once()
        self.assertEqual(result, [])

    # --- Tests for get_futures_open_positions ---
    def test_get_futures_open_positions_success(self):
        mock_api_response = [
            {'symbol': 'BTCUSDT', 'positionAmt': '0.10', 'entryPrice': '50000', 'leverage': '10', 'marginType': 'isolated', 'positionSide': 'BOTH'},
            {'symbol': 'ETHUSDT', 'positionAmt': '0.00', 'entryPrice': '4000', 'leverage': '10', 'marginType': 'cross', 'positionSide': 'BOTH'} 
        ]
        self.mock_client.futures_position_information.return_value = mock_api_response
        
        result = get_futures_open_positions(self.mock_client, self.mock_db_session)
        
        self.mock_client.futures_position_information.assert_called_once()
        self.mock_db_session.add_all.assert_called_once()
        added_objects = self.mock_db_session.add_all.call_args[0][0]
        self.assertTrue(all(isinstance(obj, Position) for obj in added_objects))
        self.assertEqual(len(added_objects), 1) # Only non-zero positionAmt
        self.assertEqual(added_objects[0].symbol, 'BTCUSDT')
        self.mock_db_session.commit.assert_called_once()
        self.assertEqual(len(result), 1)
        self.assertTrue(all(isinstance(r, Position) for r in result))

    def test_get_futures_open_positions_api_error(self):
        self.mock_client.futures_position_information.side_effect = BinanceAPIException("API Error")
        result = get_futures_open_positions(self.mock_client, self.mock_db_session)
        self.mock_db_session.rollback.assert_called_once()
        self.assertEqual(result, [])

    def test_get_futures_open_positions_db_error(self):
        mock_api_response = [{'symbol': 'BTCUSDT', 'positionAmt': '0.10', 'entryPrice': '50000', 'leverage': '10', 'marginType': 'isolated', 'positionSide': 'BOTH'}]
        self.mock_client.futures_position_information.return_value = mock_api_response
        self.mock_db_session.commit.side_effect = Exception("DB Commit Error")
        
        result = get_futures_open_positions(self.mock_client, self.mock_db_session)
        self.mock_db_session.rollback.assert_called_once()
        self.assertEqual(result, [])

    # --- Tests for get_futures_recent_trades ---
    def test_get_futures_recent_trades_success_new_trades(self):
        mock_api_response = [
            {'id': '123', 'symbol': 'BTCUSDT', 'orderId': 'o1', 'side': 'BUY', 'price': '50000', 'qty': '0.1', 'realizedPnl': '0', 'commission': '0.1', 'commissionAsset': 'USDT', 'time': 1670000000000, 'maker': False},
        ]
        self.mock_client.futures_account_trades.return_value = mock_api_response
        # Simulate trade does not exist in DB
        self.mock_db_session.query(Trade).filter(Trade.binance_trade_id == '123').first.return_value = None 
        
        result = get_futures_recent_trades(self.mock_client, self.mock_db_session, symbol='BTCUSDT', limit=1)
        
        self.mock_client.futures_account_trades.assert_called_once_with(symbol='BTCUSDT', limit=1)
        self.mock_db_session.add_all.assert_called_once()
        added_objects = self.mock_db_session.add_all.call_args[0][0]
        self.assertTrue(all(isinstance(obj, Trade) for obj in added_objects))
        self.assertEqual(len(added_objects), 1)
        self.assertEqual(added_objects[0].binance_trade_id, '123')
        self.mock_db_session.commit.assert_called_once()
        self.assertEqual(len(result), 1)

    def test_get_futures_recent_trades_duplicate_handling(self):
        mock_trade_data = {'id': '123', 'symbol': 'BTCUSDT', 'orderId': 'o1', 'side': 'BUY', 'price': '50000', 'qty': '0.1', 'realizedPnl': '0', 'commission': '0.1', 'commissionAsset': 'USDT', 'time': 1670000000000, 'maker': False}
        self.mock_client.futures_account_trades.return_value = [mock_trade_data]
        
        # First call: trade does not exist
        self.mock_db_session.query(Trade).filter(Trade.binance_trade_id == '123').first.return_value = None
        get_futures_recent_trades(self.mock_client, self.mock_db_session, symbol='BTCUSDT', limit=1)
        self.mock_db_session.add_all.assert_called_once()
        self.mock_db_session.commit.assert_called_once()
        
        # Reset mocks for second call
        self.mock_db_session.add_all.reset_mock()
        self.mock_db_session.commit.reset_mock()
        
        # Second call: trade now exists
        self.mock_db_session.query(Trade).filter(Trade.binance_trade_id == '123').first.return_value = MagicMock(spec=Trade) # Simulate existing trade
        get_futures_recent_trades(self.mock_client, self.mock_db_session, symbol='BTCUSDT', limit=1)
        self.mock_db_session.add_all.assert_not_called() # Should not be called due to duplicate
        self.mock_db_session.commit.assert_not_called()


    def test_get_futures_recent_trades_api_error(self):
        self.mock_client.futures_account_trades.side_effect = BinanceAPIException("API Error")
        result = get_futures_recent_trades(self.mock_client, self.mock_db_session, symbol='BTCUSDT', limit=1)
        self.mock_db_session.rollback.assert_called_once()
        self.assertEqual(result, [])

    def test_get_futures_recent_trades_db_error_on_commit(self):
        mock_api_response = [{'id': '123', 'symbol': 'BTCUSDT', 'orderId': 'o1', 'side': 'BUY', 'price': '50000', 'qty': '0.1', 'realizedPnl': '0', 'commission': '0.1', 'commissionAsset': 'USDT', 'time': 1670000000000, 'maker': False}]
        self.mock_client.futures_account_trades.return_value = mock_api_response
        self.mock_db_session.query(Trade).filter(Trade.binance_trade_id == '123').first.return_value = None
        self.mock_db_session.commit.side_effect = Exception("DB Commit Error")
        
        result = get_futures_recent_trades(self.mock_client, self.mock_db_session, symbol='BTCUSDT', limit=1)
        
        self.mock_db_session.rollback.assert_called_once()
        self.assertEqual(result, [])

if __name__ == '__main__':
    unittest.main()
