"""
Options Service module
Handles options data retrieval and processing
"""

import logging
from datetime import datetime, timedelta
import pandas as pd
from core.connection import IBConnection, Option
from core.processing import SimpleOptionsStrategy
from core.utils import get_closest_friday, get_next_monthly_expiration
from config import Config
from db.database import OptionsDatabase

logger = logging.getLogger('api.services.options')

class OptionsService:
    """
    Service for handling options data operations
    """
    def __init__(self):
        self.config = Config()
        self.connection = None
        self.db = OptionsDatabase()
        
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
        
    def get_options_data(self, ticker, expiration=None, strikes=10, interval=5, monthly=False):
        """
        Get options data for a specific ticker
        
        Args:
            ticker (str): Stock ticker symbol
            expiration (str, optional): Expiration date (YYYYMMDD format)
            strikes (int, optional): Number of strikes to include
            interval (int, optional): Strike price interval
            monthly (bool, optional): Whether to use monthly expiration
            
        Returns:
            dict: Options data including calls and puts
        """
        conn = self._ensure_connection()
        
        # Get stock data
        stock_data = conn.get_stock_data(ticker)
        current_price = stock_data.get('last', 0)
        
        # Determine expiration date if not provided
        if expiration is None:
            if monthly:
                expiration = get_next_monthly_expiration()
            else:
                expiration = get_closest_friday()
            expiration = expiration.strftime('%Y%m%d')
        
        # Get options chain
        options_chain = conn.get_options_chain(
            ticker, 
            expiration=expiration,
            strikes=strikes,
            interval=interval
        )
        
        # Extract calls and puts
        calls = []
        puts = []
        
        for call in options_chain.get('calls', []):
            call_data = {
                'strike': float(call.get('strike', 0)),
                'last_price': float(call.get('last', 0)),
                'bid': float(call.get('bid', 0)),
                'ask': float(call.get('ask', 0)),
                'implied_volatility': float(call.get('impliedVol', 0)),
                'delta': float(call.get('delta', 0)),
                'gamma': float(call.get('gamma', 0)),
                'vega': float(call.get('vega', 0)),
                'theta': float(call.get('theta', 0)),
                'open_interest': int(call.get('openInterest', 0)),
                'volume': int(call.get('volume', 0)),
            }
            calls.append(call_data)
            
        for put in options_chain.get('puts', []):
            put_data = {
                'strike': float(put.get('strike', 0)),
                'last_price': float(put.get('last', 0)),
                'bid': float(put.get('bid', 0)),
                'ask': float(put.get('ask', 0)),
                'implied_volatility': float(put.get('impliedVol', 0)),
                'delta': float(put.get('delta', 0)),
                'gamma': float(put.get('gamma', 0)),
                'vega': float(put.get('vega', 0)),
                'theta': float(put.get('theta', 0)),
                'open_interest': int(put.get('openInterest', 0)),
                'volume': int(put.get('volume', 0)),
            }
            puts.append(put_data)
            
        # Prepare response
        result = {
            'ticker': ticker,
            'current_price': current_price,
            'expiration': expiration,
            'calls': calls,
            'puts': puts,
        }
        
        return result
    
    def get_option_chain(self, ticker, expiration=None):
        """
        Get the full option chain for a ticker
        
        Args:
            ticker (str): Stock ticker symbol
            expiration (str, optional): Expiration date (YYYYMMDD format)
            
        Returns:
            dict: Full option chain data
        """
        conn = self._ensure_connection()
        
        # Determine expiration date if not provided
        if expiration is None:
            expiration = get_closest_friday().strftime('%Y%m%d')
            
        # Get the full option chain
        chain = conn.get_option_chain(ticker, expiration)
        
        # Transform to API response format
        return {
            'ticker': ticker,
            'expiration': expiration,
            'chain': chain
        }
    
    def get_expirations(self, ticker):
        """
        Get available option expiration dates for a ticker
        
        Args:
            ticker (str): Stock ticker symbol
            
        Returns:
            list: Available expiration dates
        """
        conn = self._ensure_connection()
        expirations = conn.get_option_expirations(ticker)
        
        # Format for API response
        formatted_expirations = []
        for exp in expirations:
            try:
                # Parse date and add additional info
                exp_date = datetime.strptime(exp, '%Y%m%d')
                days_to_expiry = (exp_date - datetime.now()).days
                
                formatted_expirations.append({
                    'date': exp,
                    'formatted_date': exp_date.strftime('%Y-%m-%d'),
                    'days_to_expiry': days_to_expiry
                })
            except:
                # Skip invalid dates
                continue
        
        return {
            'ticker': ticker,
            'expirations': formatted_expirations
        }
    
    def get_recommendations(self, tickers=None, strategy='simple', expiration=None, 
                           strikes=10, interval=5, monthly=False):
        """
        Get option trade recommendations based on strategy
        
        Args:
            tickers (list, optional): List of ticker symbols
            strategy (str, optional): Strategy name
            expiration (str, optional): Expiration date (YYYYMMDD format)
            strikes (int, optional): Number of strikes to include
            interval (int, optional): Strike price interval
            monthly (bool, optional): Whether to use monthly expiration
            
        Returns:
            dict: Option recommendations
        """
        conn = self._ensure_connection()
        
        # If no tickers provided, get them from portfolio
        if tickers is None:
            portfolio = conn.get_portfolio_positions()
            tickers = [pos.contract.symbol for pos in portfolio
                      if pos.contract.secType == 'STK']
        
        # Determine expiration date if not provided
        if expiration is None:
            if monthly:
                expiration = get_next_monthly_expiration()
            else:
                expiration = get_closest_friday()
            expiration = expiration.strftime('%Y%m%d')
            
        # Apply strategy to get recommendations
        if strategy == 'simple':
            strategy_obj = SimpleOptionsStrategy()
            recommendations = []
            
            for ticker in tickers:
                try:
                    stock_data = conn.get_stock_data(ticker)
                    options_data = self.get_options_data(
                        ticker,
                        expiration=expiration,
                        strikes=strikes,
                        interval=interval,
                        monthly=monthly
                    )
                    
                    # Generate recommendations using strategy
                    ticker_recs = strategy_obj.generate_recommendations(
                        ticker,
                        stock_data,
                        options_data
                    )
                    
                    recommendations.extend(ticker_recs)
                except Exception as e:
                    logger.error(f"Error getting recommendations for {ticker}: {str(e)}")
        else:
            # Unsupported strategy
            raise ValueError(f"Strategy '{strategy}' not supported")
            
        # Save recommendations to database
        for rec in recommendations:
            self.db.save_recommendation(rec)
            
        return {
            'count': len(recommendations),
            'expiration': expiration,
            'recommendations': recommendations
        }
    
    def get_available_strategies(self):
        """
        Get available option strategies
        
        Returns:
            list: Available strategies
        """
        strategies = [
            {
                'id': 'simple',
                'name': 'Simple Options Strategy',
                'description': 'Basic strategy focusing on selling cash-secured puts and covered calls'
            }
        ]
        
        return {
            'strategies': strategies
        } 