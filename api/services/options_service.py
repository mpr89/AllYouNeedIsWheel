"""
Options Service module
Handles options data retrieval and processing
"""

import logging
import math
import random
import time
from datetime import datetime, timedelta
import pandas as pd
from core.connection import IBConnection, Option
from core.utils import get_closest_friday, get_next_monthly_expiration, get_strikes_around_price
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
            # Generate a unique client ID based on current timestamp and random number
            # to avoid conflicts with other connections
            unique_client_id = int(time.time() % 10000) + random.randint(1000, 9999)
            logger.info(f"Creating new TWS connection with client ID: {unique_client_id}")
            
            self.connection = IBConnection(
                host=self.config.get('host', '127.0.0.1'),
                port=self.config.get('port', 7497),
                client_id=unique_client_id,  # Use the unique client ID instead of fixed ID 1
                timeout=self.config.get('timeout', 20),
                readonly=self.config.get('readonly', True)
            )
            self.connection.connect()
        return self.connection
        
    def _get_stock_data(self, ticker):
        """
        Custom implementation to get stock data directly as a workaround
        for missing get_stock_data method in IBConnection
        
        Args:
            ticker (str): Stock ticker symbol
            
        Returns:
            dict: Stock data dictionary
        """
        conn = self._ensure_connection()
        
        try:
            # We can use get_stock_price which we know exists
            stock_price = conn.get_stock_price(ticker)
            
            # Build a basic stock data object
            stock_data = {
                'symbol': ticker,
                'last': stock_price,
                'price': stock_price,
                'bid': None,
                'ask': None,
                'high': None,
                'low': None,
                'close': stock_price,
                'open': None,
                'volume': None,
                'timestamp': datetime.now().isoformat()
            }
            return stock_data
        except Exception as e:
            logger.error(f"Error getting stock data for {ticker}: {str(e)}")
            return {
                'symbol': ticker,
                'last': 0,
                'price': 0
            }
        
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
        # Using our custom method instead of conn.get_stock_data
        stock_data = self._get_stock_data(ticker)
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
            recommendations = self._generate_simple_options_recommendations(
                tickers, expiration, strikes, interval
            )
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
        
    def _generate_simple_options_recommendations(self, tickers, expiration, strikes=10, interval=5):
        """
        Generate recommendations using the simple options strategy
        
        Args:
            tickers (list): List of ticker symbols
            expiration (str): Expiration date in YYYYMMDD format
            strikes (int): Number of strikes to include
            interval (int): Strike price interval
            
        Returns:
            list: List of recommendation dictionaries
        """
        conn = self._ensure_connection()
        recommendations = []
        
        # Get portfolio for position information
        portfolio_positions = conn.get_portfolio_positions()
        portfolio = {}
        for pos in portfolio_positions:
            if pos.contract.secType == 'STK':
                ticker = pos.contract.symbol
                portfolio[ticker] = {
                    'size': float(pos.position),
                    'avg_cost': float(pos.averageCost),
                    'market_value': float(pos.marketValue),
                    'unrealized_pnl': float(pos.unrealizedPNL)
                }
        
        # Get all stock prices in one request
        logger.info(f"Fetching stock prices for tickers: {tickers}")
        stock_prices = conn.get_multiple_stock_prices(tickers)
        
        if not stock_prices:
            logger.error("Failed to get stock prices")
            return []
            
        # Prepare strikes for each ticker
        put_otm_pct = self.config.get('put_otm_percentage', 20) 
        call_otm_pct = self.config.get('call_otm_percentage', 20)
        
        strikes_map = {}
        valid_tickers = []
        
        for ticker, price in stock_prices.items():
            if price is None or math.isnan(price):
                logger.warning(f"Could not get price for {ticker}, skipping")
                continue
                
            # Calculate option strike prices at specified percentages
            put_strike = self._adjust_to_standard_strike(price * (1 - put_otm_pct/100))
            call_strike = self._adjust_to_standard_strike(price * (1 + call_otm_pct/100))
            
            strikes_map[ticker] = [put_strike, call_strike]
            valid_tickers.append(ticker)
        
        # Get option prices for all tickers and strikes
        all_option_data = conn.get_multiple_stocks_option_prices(
            valid_tickers, 
            expiration, 
            strikes_map=strikes_map
        )
        
        # Process each ticker with the data we've gathered
        for ticker in valid_tickers:
            if ticker not in stock_prices:
                continue
                
            try:
                stock_price = stock_prices[ticker]
                
                # Get the strikes for this ticker
                if ticker not in strikes_map:
                    continue
                
                put_strike, call_strike = strikes_map[ticker]
                
                # Check if we have a position in this stock
                position_size = 0
                avg_cost = 0
                market_value = 0
                unrealized_pnl = 0
                
                if ticker in portfolio:
                    position_size = portfolio[ticker]['size']
                    avg_cost = portfolio[ticker]['avg_cost']
                    market_value = portfolio[ticker]['market_value']
                    unrealized_pnl = portfolio[ticker]['unrealized_pnl']
                
                # Get options data
                put_data = None
                call_data = None
                
                if ticker in all_option_data:
                    ticker_options = all_option_data[ticker]
                    for option_key, option_data in ticker_options.items():
                        # Option key is a tuple of (strike, right)
                        strike, right = option_key
                        if right == 'P' and abs(strike - put_strike) < 0.01:
                            put_data = option_data
                        elif right == 'C' and abs(strike - call_strike) < 0.01:
                            call_data = option_data
                
                # If options data not found in bulk, try individual requests
                if put_data is None:
                    put_contract = conn.create_option_contract(ticker, expiration, put_strike, 'P')
                    put_data = conn.get_option_price(put_contract)
                
                if call_data is None:
                    call_contract = conn.create_option_contract(ticker, expiration, call_strike, 'C')
                    call_data = conn.get_option_price(call_contract)
                
                # Determine strategy based on position
                strategy = "NEUTRAL"  # Default strategy
                
                if position_size > 0:
                    strategy = "BULLISH"  # We own the stock, sell calls
                elif position_size < 0:
                    strategy = "BEARISH"  # We are short the stock, sell puts
                
                # Calculate potential earnings for options
                put_earnings = None
                call_earnings = None
                
                if put_data and 'bid' in put_data and put_data['bid'] is not None:
                    # For cash-secured puts
                    max_contracts = math.floor(self.config.get('max_position_value', 20000) / (put_strike * 100))
                    premium_per_contract = put_data['bid'] * 100  # Convert to dollar amount
                    total_premium = premium_per_contract * max_contracts
                    return_on_cash = (total_premium / (put_strike * 100 * max_contracts)) * 100 if max_contracts > 0 else 0
                    
                    put_earnings = {
                        'strategy': 'Cash-Secured Put',
                        'max_contracts': max_contracts,
                        'premium_per_contract': premium_per_contract,
                        'total_premium': total_premium,
                        'return_on_cash': return_on_cash
                    }
                
                if call_data and 'bid' in call_data and call_data['bid'] is not None and position_size > 0:
                    # For covered calls (only if we own the stock)
                    max_contracts = math.floor(abs(position_size) / 100)  # Each contract covers 100 shares
                    premium_per_contract = call_data['bid'] * 100  # Convert to dollar amount
                    total_premium = premium_per_contract * max_contracts
                    return_on_capital = (total_premium / (stock_price * 100 * max_contracts)) * 100 if max_contracts > 0 else 0
                    
                    call_earnings = {
                        'strategy': 'Covered Call',
                        'max_contracts': max_contracts,
                        'premium_per_contract': premium_per_contract,
                        'total_premium': total_premium,
                        'return_on_capital': return_on_capital
                    }
                
                # Create recommendation based on portfolio position
                recommendation = {}
                
                if strategy == "BULLISH" and position_size > 0:
                    # We own the stock, recommend selling calls
                    recommendation = {
                        'action': 'SELL',
                        'type': 'CALL',
                        'strike': call_strike,
                        'expiration': expiration,
                        'earnings': call_earnings
                    }
                elif strategy == "BEARISH" and position_size < 0:
                    # We are short the stock, recommend selling puts
                    recommendation = {
                        'action': 'SELL',
                        'type': 'PUT',
                        'strike': put_strike,
                        'expiration': expiration,
                        'earnings': put_earnings
                    }
                else:
                    # Neutral strategy or no position
                    # For simplicity, recommend selling puts as it requires less capital than buying stock
                    recommendation = {
                        'action': 'SELL',
                        'type': 'PUT',
                        'strike': put_strike,
                        'expiration': expiration,
                        'earnings': put_earnings
                    }
                    
                    # Also include call option as a bullish alternative
                    recommendation['alternative'] = {
                        'action': 'BUY',
                        'type': 'CALL',
                        'strike': call_strike,
                        'expiration': expiration
                    }
                
                # Build and return the result
                result = {
                    'ticker': ticker,
                    'price': stock_price,
                    'strategy': strategy,
                    'position': {
                        'size': position_size,
                        'avg_cost': avg_cost,
                        'market_value': market_value,
                        'unrealized_pnl': unrealized_pnl
                    },
                    'options': {
                        'expiration': expiration,
                        'put': {
                            'strike': put_strike,
                            'bid': put_data['bid'] if put_data and 'bid' in put_data else None,
                            'ask': put_data['ask'] if put_data and 'ask' in put_data else None,
                            'last': put_data['last'] if put_data and 'last' in put_data else None
                        },
                        'call': {
                            'strike': call_strike,
                            'bid': call_data['bid'] if call_data and 'bid' in call_data else None,
                            'ask': call_data['ask'] if call_data and 'ask' in call_data else None,
                            'last': call_data['last'] if call_data and 'last' in call_data else None
                        }
                    },
                    'recommendation': recommendation
                }
                
                recommendations.append(result)
            except Exception as e:
                logger.error(f"Error processing {ticker}: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
        
        return recommendations
        
    def _adjust_to_standard_strike(self, strike):
        """
        Adjust a strike price to a standard option strike increment
        
        Args:
            strike: Strike price
            
        Returns:
            float: Adjusted strike price
        """
        if strike <= 5:
            # $0.50 increments for stocks under $5
            return round(strike * 2) / 2
        elif strike <= 25:
            # $1.00 increments for stocks under $25
            return round(strike)
        elif strike <= 200:
            # $5.00 increments for stocks under $200
            return round(strike / 5) * 5
        else:
            # $10.00 increments for stocks over $200
            return round(strike / 10) * 10
    
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
        
    def get_delta_targeted_options(self, tickers=None, target_delta=0.1, delta_range=0.05, expiration=None, monthly=False):
        """
        Find options with delta around the target value for use in the dashboard
        
        Args:
            tickers (list, optional): List of ticker symbols. If None, uses portfolio positions.
            target_delta (float, optional): Target delta value. Default 0.1.
            delta_range (float, optional): Acceptable range around target delta. Default 0.05.
            expiration (str, optional): Expiration date in YYYYMMDD format.
            monthly (bool, optional): Whether to use monthly expiration.
            
        Returns:
            dict: Options data keyed by ticker with delta-targeted options
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
                expiration_date = get_next_monthly_expiration()
            else:
                expiration_date = get_closest_friday()
            expiration = expiration_date.strftime('%Y%m%d')
            
        # Prepare result structure
        result = {
            'expiration': expiration,
            'target_delta': target_delta,
            'data': {}
        }
            
        # Process each ticker
        for ticker in tickers:
            try:
                # Get stock data
                stock_data = conn.get_stock_data(ticker)
                current_price = stock_data.get('last', 0)
                
                # Get full options chain with greeks
                options_chain = conn.get_full_options_chain(ticker, expiration)
                
                # Find call and put with delta closest to target
                best_call = None
                best_put = None
                best_call_delta_diff = 1.0
                best_put_delta_diff = 1.0
                
                # Process calls
                for call in options_chain.get('calls', []):
                    if not call.get('delta'):
                        continue
                        
                    delta = abs(float(call.get('delta', 0)))
                    # We want OTM calls with positive delta close to target
                    if float(call.get('strike', 0)) > current_price:
                        delta_diff = abs(delta - target_delta)
                        if delta_diff < best_call_delta_diff and delta_diff <= delta_range:
                            best_call = call
                            best_call_delta_diff = delta_diff
                
                # Process puts
                for put in options_chain.get('puts', []):
                    if not put.get('delta'):
                        continue
                        
                    # For puts, delta is negative, we need to take absolute value
                    delta = abs(float(put.get('delta', 0)))
                    # We want OTM puts with negative delta close to target
                    if float(put.get('strike', 0)) < current_price:
                        delta_diff = abs(delta - target_delta)
                        if delta_diff < best_put_delta_diff and delta_diff <= delta_range:
                            best_put = put
                            best_put_delta_diff = delta_diff
                
                # Get portfolio position data
                position_size = 0
                avg_cost = 0
                market_value = 0
                unrealized_pnl = 0
                
                # Check portfolio for this stock
                portfolio_positions = conn.get_portfolio_positions()
                for pos in portfolio_positions:
                    if pos.contract.symbol == ticker:
                        position_size = float(pos.position)
                        avg_cost = float(pos.averageCost)
                        market_value = float(pos.marketValue)
                        unrealized_pnl = float(pos.unrealizedPNL)
                        break
                
                # Calculate potential earnings
                call_earnings = None
                put_earnings = None
                
                if best_call and position_size > 0:
                    # For covered calls (only if we own the stock)
                    max_contracts = int(position_size // 100)  # Each contract covers 100 shares
                    premium_per_contract = float(best_call.get('bid', 0)) * 100  # Convert to dollar amount
                    total_premium = premium_per_contract * max_contracts
                    return_on_capital = (total_premium / (current_price * 100 * max_contracts)) * 100 if max_contracts > 0 else 0
                    
                    call_earnings = {
                        'strategy': 'Covered Call',
                        'max_contracts': max_contracts,
                        'premium_per_contract': premium_per_contract,
                        'total_premium': total_premium,
                        'return_on_capital': return_on_capital
                    }
                
                if best_put:
                    # For cash-secured puts
                    put_strike = float(best_put.get('strike', 0))
                    # Use a safety margin (e.g., 80% of portfolio value) for max position value
                    portfolio_summary = conn.get_account_summary()
                    available_cash = float(portfolio_summary.get('AvailableFunds', 0))
                    safety_margin = 0.8  # Use only 80% of available funds
                    max_position_value = available_cash * safety_margin
                    
                    max_contracts = int(max_position_value // (put_strike * 100))
                    premium_per_contract = float(best_put.get('bid', 0)) * 100  # Convert to dollar amount
                    total_premium = premium_per_contract * max_contracts
                    return_on_cash = (total_premium / (put_strike * 100 * max_contracts)) * 100 if max_contracts > 0 else 0
                    
                    put_earnings = {
                        'strategy': 'Cash-Secured Put',
                        'max_contracts': max_contracts,
                        'premium_per_contract': premium_per_contract,
                        'total_premium': total_premium,
                        'return_on_cash': return_on_cash
                    }
                
                # Add to result
                ticker_result = {
                    'ticker': ticker,
                    'price': current_price,
                    'position': {
                        'size': position_size,
                        'avg_cost': avg_cost,
                        'market_value': market_value,
                        'unrealized_pnl': unrealized_pnl
                    },
                    'call': {
                        'strike': float(best_call.get('strike', 0)) if best_call else 0,
                        'bid': float(best_call.get('bid', 0)) if best_call else 0,
                        'ask': float(best_call.get('ask', 0)) if best_call else 0,
                        'delta': float(best_call.get('delta', 0)) if best_call else 0,
                        'earnings': call_earnings
                    },
                    'put': {
                        'strike': float(best_put.get('strike', 0)) if best_put else 0,
                        'bid': float(best_put.get('bid', 0)) if best_put else 0,
                        'ask': float(best_put.get('ask', 0)) if best_put else 0,
                        'delta': float(best_put.get('delta', 0)) if best_put else 0,
                        'earnings': put_earnings
                    }
                }
                
                result['data'][ticker] = ticker_result
                
            except Exception as e:
                logger.error(f"Error processing delta-targeted options for {ticker}: {str(e)}")
                continue
                
        return result 