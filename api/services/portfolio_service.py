"""
Portfolio Service module
Manages portfolio data and calculations
"""

import logging
from core.connection import IBConnection
from core.utils import print_stock_summary
from config import Config

logger = logging.getLogger('api.services.portfolio')

class PortfolioService:
    """
    Service for handling portfolio operations
    """
    def __init__(self):
        self.config = Config()
        self.connection = None
        
    def _ensure_connection(self):
        """
        Ensure that the IB connection exists and is connected
        """
        if self.connection is None or not self.connection.is_connected():
            self.connection = IBConnection(
                host=self.config.get('host', '127.0.0.1'),
                port=self.config.get('port', 7497),
                client_id=self.config.get('client_id', 1),
                readonly=self.config.get('readonly', True)
            )
            self.connection.connect()
        return self.connection
        
    def get_portfolio_summary(self):
        """
        Get a summary of the current portfolio
        
        Returns:
            dict: Portfolio summary data
        """
        conn = self._ensure_connection()
        account_summary = conn.get_account_summary()
        portfolio_positions = conn.get_portfolio_positions()
        
        # Transform data for API response
        result = {
            'account_value': float(account_summary.get('NetLiquidation', 0)),
            'buying_power': float(account_summary.get('BuyingPower', 0)),
            'cash_balance': float(account_summary.get('TotalCashValue', 0)),
            'positions_count': len(portfolio_positions),
            'unrealized_pnl': float(account_summary.get('UnrealizedPnL', 0)),
            'realized_pnl': float(account_summary.get('RealizedPnL', 0)),
        }
        
        return result
        
    def get_positions(self):
        """
        Get current portfolio positions
        
        Returns:
            list: List of portfolio positions
        """
        conn = self._ensure_connection()
        positions = conn.get_portfolio_positions()
        
        # Transform to API response format
        result = []
        for pos in positions:
            position_data = {
                'symbol': pos.contract.symbol,
                'position': float(pos.position),
                'market_price': float(pos.marketPrice),
                'market_value': float(pos.marketValue),
                'average_cost': float(pos.averageCost),
                'unrealized_pnl': float(pos.unrealizedPNL),
                'realized_pnl': float(pos.realizedPNL),
                'account_name': pos.account,
                'security_type': pos.contract.secType,
            }
            result.append(position_data)
            
        return result
        
    def get_performance_metrics(self):
        """
        Get portfolio performance metrics
        
        Returns:
            dict: Performance metrics
        """
        conn = self._ensure_connection()
        account_summary = conn.get_account_summary()
        
        # Calculate performance metrics
        result = {
            'daily_pnl': float(account_summary.get('DailyPnL', 0)),
            'total_cash_value': float(account_summary.get('TotalCashValue', 0)),
            'net_dividend': float(account_summary.get('NetDividend', 0)),
            'available_funds': float(account_summary.get('AvailableFunds', 0)),
            'excess_liquidity': float(account_summary.get('ExcessLiquidity', 0)),
        }
        
        return result 