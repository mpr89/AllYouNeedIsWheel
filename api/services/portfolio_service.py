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
        logger.info(f"Portfolio service using port: {self.config.get('port')}")
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
                port = self.config.get('port', 7497)
                logger.info(f"Connecting to TWS on port: {port}")
                
                self.connection = IBConnection(
                    host=self.config.get('host', '127.0.0.1'),
                    port=port,
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
                    'stock_positions_count': 0,
                    'option_positions_count': 0,
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
                    'stock_positions_count': 0,
                    'option_positions_count': 0,
                    'unrealized_pnl': 0,
                    'realized_pnl': 0,
                    'error': 'Failed to retrieve portfolio data'
                }
            
            # Calculate total unrealized and realized PnL for all positions
            positions = portfolio_data.get('positions', {})
            
            # Count positions by type
            stock_positions = [pos for pos in positions.values() if pos.get('security_type') == 'STK']
            option_positions = [pos for pos in positions.values() if pos.get('security_type') == 'OPT']
            
            # Calculate PnL
            unrealized_pnl = sum(pos.get('unrealized_pnl', 0) for pos in positions.values())
            realized_pnl = sum(pos.get('realized_pnl', 0) for pos in positions.values())
            
            # Log the counts
            logger.info(f"Portfolio summary: {len(stock_positions)} stock positions, {len(option_positions)} option positions")
            
            # Transform data for API response
            result = {
                'account_id': portfolio_data.get('account_id', 'Unknown'),
                'account_value': portfolio_data.get('account_value', 0),
                'buying_power': portfolio_data.get('available_cash', 0) * 2,  # Estimate buying power as 2x cash
                'cash_balance': portfolio_data.get('available_cash', 0),
                'positions_count': len(positions),
                'stock_positions_count': len(stock_positions),
                'option_positions_count': len(option_positions),
                'unrealized_pnl': unrealized_pnl,
                'realized_pnl': realized_pnl
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
                'stock_positions_count': 0,
                'option_positions_count': 0,
                'unrealized_pnl': 0,
                'realized_pnl': 0,
                'error': str(e)
            }
        
    def get_positions(self, position_type=None):
        """
        Get current portfolio positions
        
        Args:
            position_type (str, optional): Filter positions by type. Options: 'STK' for stocks, 
                                          'OPT' for options, None for all positions
        
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
            
            stock_count = 0
            option_count = 0
            other_count = 0
            
            logger.info(f"Processing positions with filter: {position_type or 'ALL'}")
            
            for position_key, pos in positions.items():
                try:
                    # Get security type
                    security_type = pos.get('security_type')
                    
                    # Apply filter if provided
                    if position_type and security_type != position_type:
                        continue
                    
                    # Create position data based on security type
                    if security_type == 'STK':
                        stock_count += 1
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
                                'security_type': 'STK'
                            }
                        else:  # This is our dictionary format
                            contract = pos.get('contract')
                            position_data = {
                                'symbol': contract.symbol if contract else position_key.split('_')[0],
                                'position': float(pos.get('shares', 0)),
                                'market_price': float(pos.get('market_price', 0)),
                                'market_value': float(pos.get('market_value', 0)),
                                'average_cost': float(pos.get('avg_cost', 0)),
                                'unrealized_pnl': float(pos.get('unrealized_pnl', 0)),
                                'realized_pnl': float(pos.get('realized_pnl', 0)),
                                'account_name': portfolio_data.get('account_id', 'Unknown'),
                                'security_type': 'STK'
                            }
                    elif security_type == 'OPT':
                        option_count += 1
                        # Handle option positions
                        if hasattr(pos, 'contract'):
                            contract = pos.contract
                            position_data = {
                                'symbol': contract.symbol,
                                'position': float(pos.position),
                                'market_price': float(pos.marketPrice),
                                'market_value': float(pos.marketValue),
                                'average_cost': float(pos.averageCost),
                                'unrealized_pnl': float(pos.unrealizedPNL),
                                'realized_pnl': float(pos.realizedPNL),
                                'account_name': portfolio_data.get('account_id', 'Unknown'),
                                'security_type': 'OPT',
                                'expiration': contract.lastTradeDateOrContractMonth,
                                'strike': float(contract.strike),
                                'right': contract.right,
                                'option_type': 'CALL' if contract.right == 'C' else 'PUT'
                            }
                        else:
                            contract = pos.get('contract')
                            # Parse position key for option details if contract is missing
                            if contract:
                                option_data = {
                                    'symbol': contract.symbol,
                                    'expiration': contract.lastTradeDateOrContractMonth,
                                    'strike': float(contract.strike),
                                    'right': contract.right,
                                    'option_type': 'CALL' if contract.right == 'C' else 'PUT'
                                }
                            else:
                                # Try to parse from position key (fallback)
                                parts = position_key.split('_')
                                if len(parts) >= 4:
                                    symbol = parts[0]
                                    expiration = parts[1]
                                    strike = float(parts[2])
                                    right = parts[3]
                                    option_data = {
                                        'symbol': symbol,
                                        'expiration': expiration,
                                        'strike': strike,
                                        'right': right,
                                        'option_type': 'CALL' if right == 'C' else 'PUT'
                                    }
                                else:
                                    # Can't determine option details
                                    option_data = {
                                        'symbol': position_key,
                                        'expiration': 'Unknown',
                                        'strike': 0.0,
                                        'right': 'Unknown',
                                        'option_type': 'Unknown'
                                    }
                            
                            position_data = {
                                'symbol': option_data['symbol'],
                                'position': float(pos.get('shares', 0)),
                                'market_price': float(pos.get('market_price', 0)),
                                'market_value': float(pos.get('market_value', 0)),
                                'average_cost': float(pos.get('avg_cost', 0)),
                                'unrealized_pnl': float(pos.get('unrealized_pnl', 0)),
                                'realized_pnl': float(pos.get('realized_pnl', 0)),
                                'account_name': portfolio_data.get('account_id', 'Unknown'),
                                'security_type': 'OPT',
                                'expiration': option_data['expiration'],
                                'strike': option_data['strike'],
                                'right': option_data['right'],
                                'option_type': option_data['option_type']
                            }
                    else:
                        # Handle other security types if needed
                        other_count += 1
                        continue  # Skip other security types for now
                    
                    result.append(position_data)
                        
                except Exception as pos_error:
                    logger.error(f"Error processing position {position_key}: {str(pos_error)}")
                    # Continue with next position
            
            filter_msg = f" (filter: {position_type})" if position_type else ""
            logger.info(f"Returning {stock_count} stock positions, {option_count} option positions, filtered out {other_count} other positions{filter_msg}")
            return result
        except Exception as e:
            logger.error(f"Error in get_positions: {str(e)}")
            return []
            
    def get_weekly_option_income(self):
        """
        Get all short option positions in the portfolio that expire next Friday
        and calculate potential income.
        
        Returns:
            dict: Dictionary containing weekly option income data
        """
        try:
            from datetime import datetime, timedelta
            
            # Connect to TWS
            conn = self._ensure_connection()
            if not conn:
                logger.error("Failed to establish connection to TWS")
                return {
                    'positions': [],
                    'total_income': 0,
                    'positions_count': 0,
                    'error': 'Failed to connect to TWS'
                }
                
            # Get portfolio data
            portfolio_data = conn.get_portfolio()
            
            if not portfolio_data:
                logger.error("Failed to retrieve portfolio data")
                return {
                    'positions': [],
                    'total_income': 0,
                    'positions_count': 0,
                    'error': 'Failed to retrieve portfolio data'
                }
            
            # Calculate next Friday's date in YYYYMMDD format
            today = datetime.now()
            days_until_friday = (4 - today.weekday()) % 7
            if days_until_friday == 0:  # If today is Friday, get next Friday
                days_until_friday = 7
            next_friday = today + timedelta(days=days_until_friday)
            next_friday_str = next_friday.strftime('%Y%m%d')
            
            logger.info(f"Looking for options expiring on {next_friday_str}")
            
            # Filter for short option positions expiring next Friday
            positions = portfolio_data.get('positions', {})
            weekly_options = []
            total_income = 0
            
            # Process each position
            for position_key, pos in positions.items():
                try:
                    # Check if position is an option and is a short position (negative quantity)
                    security_type = pos.get('security_type')
                    position_value = float(pos.get('shares', 0))
                    
                    # Only process short option positions (negative quantity)
                    if security_type == 'OPT' and position_value < 0:
                        # Get the contract object
                        contract = pos.get('contract')
                        
                        if not contract:
                            logger.warning(f"Option position {position_key} has no contract object, skipping")
                            continue
                        
                        # Get expiration date
                        expiration = contract.lastTradeDateOrContractMonth
                            
                        # Check if this option expires next Friday
                        if expiration == next_friday_str:
                            # Get option details
                            option_data = {
                                'symbol': contract.symbol,
                                'option_type': contract.right,
                                'strike': float(contract.strike),
                                'expiration': expiration,
                                'position': abs(position_value),  # Make positive for display
                                'avg_cost': float(pos.get('avg_cost', 0)),
                                'current_price': float(pos.get('market_price', 0)),
                                'income': abs(float(pos.get('avg_cost', 0))) * 100 * abs(position_value)
                            }
                            
                            weekly_options.append(option_data)
                            total_income += option_data['income']
                            
                            logger.debug(f"Found option expiring next Friday: {contract.symbol} {contract.right} {contract.strike}")
                except Exception as pos_error:
                    logger.error(f"Error processing option position {position_key}: {str(pos_error)}")
                    # Continue with next position
            
            logger.info(f"Found {len(weekly_options)} short option positions expiring next Friday")
            
            return {
                'positions': weekly_options,
                'total_income': total_income,
                'positions_count': len(weekly_options),
                'next_friday': next_friday_str
            }
            
        except Exception as e:
            logger.error(f"Error in get_weekly_option_income: {str(e)}")
            return {
                'positions': [],
                'total_income': 0,
                'positions_count': 0,
                'error': str(e)
            }