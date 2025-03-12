"""
Portfolio Service module
Manages portfolio data and calculations
"""

import logging
import random
import time
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
        try:
            if self.connection is None or not self.connection.is_connected():
                # Generate a unique client ID based on current timestamp and random number
                # to avoid conflicts with other connections
                unique_client_id = int(time.time() % 10000) + random.randint(1000, 9999)
                logger.info(f"Creating new TWS connection with client ID: {unique_client_id}")
                
                # Create new connection
                self.connection = IBConnection(
                    host=self.config.get('host', '127.0.0.1'),
                    port=self.config.get('port', 7497),
                    client_id=unique_client_id,  # Use the unique client ID instead of fixed ID 1
                    timeout=self.config.get('timeout', 20),
                    readonly=self.config.get('readonly', True)
                )
                
                # Try to connect with proper error handling
                if not self.connection.connect():
                    logger.error("Failed to connect to TWS/IB Gateway")
                else:
                    logger.info("Successfully connected to TWS/IB Gateway")
            return self.connection
        except Exception as e:
            logger.error(f"Error ensuring connection: {str(e)}")
            if "There is no current event loop" in str(e):
                logger.error("Asyncio event loop error - please check connection.py for proper handling")
            return None
        
    def get_portfolio_summary(self):
        """
        Get a summary of the current portfolio
        
        Returns:
            dict: Portfolio summary data
        """
        try:
            conn = self._ensure_connection()
            if not conn:
                logger.error("Failed to establish connection to TWS")
                return {
                    'account_value': 0,
                    'buying_power': 0,
                    'cash_balance': 0,
                    'positions_count': 0,
                    'unrealized_pnl': 0,
                    'realized_pnl': 0,
                    'error': 'Failed to connect to TWS'
                }
                
            # Get portfolio data using the correct method
            portfolio_data = conn.get_portfolio()
            
            if not portfolio_data:
                logger.error("Failed to retrieve portfolio data")
                return {
                    'account_value': 0,
                    'buying_power': 0,
                    'cash_balance': 0,
                    'positions_count': 0,
                    'unrealized_pnl': 0,
                    'realized_pnl': 0,
                    'error': 'Failed to retrieve portfolio data'
                }
            
            # Calculate total unrealized and realized PnL
            positions = portfolio_data.get('positions', {})
            unrealized_pnl = sum(pos.get('unrealized_pnl', 0) for pos in positions.values())
            realized_pnl = sum(pos.get('realized_pnl', 0) for pos in positions.values())
            
            # Transform data for API response
            result = {
                'account_id': portfolio_data.get('account_id', 'Unknown'),
                'account_value': portfolio_data.get('account_value', 0),
                'buying_power': portfolio_data.get('available_cash', 0) * 2,  # Estimate buying power as 2x cash
                'cash_balance': portfolio_data.get('available_cash', 0),
                'positions_count': len(positions),
                'unrealized_pnl': unrealized_pnl,
                'realized_pnl': realized_pnl,
                'is_mock': portfolio_data.get('is_mock', False)
            }
            
            return result
        except Exception as e:
            logger.error(f"Error in get_portfolio_summary: {str(e)}")
            # Return a default structure with error information
            return {
                'account_value': 0,
                'buying_power': 0,
                'cash_balance': 0,
                'positions_count': 0,
                'unrealized_pnl': 0,
                'realized_pnl': 0,
                'error': str(e)
            }
        
    def get_positions(self):
        """
        Get current portfolio positions
        
        Returns:
            list: List of portfolio positions
        """
        try:
            conn = self._ensure_connection()
            if not conn:
                logger.error("Failed to establish connection to TWS")
                return []
                
            # Get portfolio data using the correct method
            portfolio_data = conn.get_portfolio()
            
            if not portfolio_data:
                logger.error("Failed to retrieve portfolio data")
                return []
            
            # Transform to API response format
            result = []
            positions = portfolio_data.get('positions', {})
            
            for symbol, pos in positions.items():
                try:
                    # Handle different types of position data
                    if hasattr(pos, 'contract'):  # This is a raw IB position object
                        position_data = {
                            'symbol': pos.contract.symbol,
                            'position': float(pos.position),
                            'market_price': float(pos.marketPrice),
                            'market_value': float(pos.marketValue),
                            'average_cost': float(pos.averageCost),
                            'unrealized_pnl': float(pos.unrealizedPNL),
                            'realized_pnl': float(pos.realizedPNL),
                            'account_name': portfolio_data.get('account_id', 'Unknown'),
                            'security_type': pos.contract.secType,
                            'is_mock': portfolio_data.get('is_mock', False)
                        }
                    else:  # This is our dictionary format
                        position_data = {
                            'symbol': symbol,
                            'position': float(pos.get('shares', 0)),
                            'market_price': float(pos.get('market_price', 0)),
                            'market_value': float(pos.get('market_value', 0)),
                            'average_cost': float(pos.get('avg_cost', 0)),
                            'unrealized_pnl': float(pos.get('unrealized_pnl', 0)),
                            'realized_pnl': float(pos.get('realized_pnl', 0)),
                            'account_name': portfolio_data.get('account_id', 'Unknown'),
                            'security_type': 'STK',  # Default to stock
                            'is_mock': portfolio_data.get('is_mock', False)
                        }
                    
                    result.append(position_data)
                except Exception as pos_error:
                    logger.error(f"Error processing position {symbol}: {str(pos_error)}")
                    # Continue with next position
                
            return result
        except Exception as e:
            logger.error(f"Error in get_positions: {str(e)}")
            return []
        
    def get_performance_metrics(self):
        """
        Get portfolio performance metrics
        
        Returns:
            dict: Performance metrics
        """
        try:
            conn = self._ensure_connection()
            if not conn:
                logger.error("Failed to establish connection to TWS")
                return {
                    'daily_pnl': 0,
                    'total_cash_value': 0,
                    'net_dividend': 0,
                    'available_funds': 0,
                    'excess_liquidity': 0,
                    'error': 'Failed to connect to TWS'
                }
                
            # Get portfolio data using the correct method
            portfolio_data = conn.get_portfolio()
            
            if not portfolio_data:
                logger.error("Failed to retrieve portfolio data")
                return {
                    'daily_pnl': 0,
                    'total_cash_value': 0,
                    'net_dividend': 0,
                    'available_funds': 0,
                    'excess_liquidity': 0,
                    'error': 'Failed to retrieve portfolio data'
                }
            
            # Calculate performance metrics
            positions = portfolio_data.get('positions', {})
            unrealized_pnl = sum(pos.get('unrealized_pnl', 0) for pos in positions.values())
            
            result = {
                'daily_pnl': unrealized_pnl,  # Use unrealized PnL as an estimate for daily PnL
                'total_cash_value': portfolio_data.get('available_cash', 0),
                'net_dividend': 0,  # Not available in the mock data
                'available_funds': portfolio_data.get('available_cash', 0),
                'excess_liquidity': portfolio_data.get('available_cash', 0) * 0.9,  # Estimate as 90% of cash
                'is_mock': portfolio_data.get('is_mock', False)
            }
            
            return result
        except Exception as e:
            logger.error(f"Error in get_performance_metrics: {str(e)}")
            return {
                'daily_pnl': 0,
                'total_cash_value': 0,
                'net_dividend': 0,
                'available_funds': 0,
                'excess_liquidity': 0,
                'error': str(e)
            } 