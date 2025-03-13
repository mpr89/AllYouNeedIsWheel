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
from core.connection import IBConnection, Option, Stock
from core.utils import get_closest_friday, get_next_monthly_expiration, get_strikes_around_price
from config import Config
from db.database import OptionsDatabase
import traceback
import concurrent.futures
from functools import partial

logger = logging.getLogger('api.services.options')

class OptionsService:
    """
    Service for handling options data operations
    """
    def __init__(self):
        self.config = Config()
        self.connection = None
        self.db = OptionsDatabase()
        self.portfolio_service = None  # Will be initialized when needed
        
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
                
                # Create new connection with real_time flag if specified
                self.connection = IBConnection(
                    host=self.config.get('host', '127.0.0.1'),
                    port=self.config.get('port', 7497),
                    client_id=unique_client_id,  # Use the unique client ID instead of fixed ID 1
                    timeout=self.config.get('timeout', 20),
                    readonly=self.config.get('readonly', True),
                    real_time=getattr(self, 'real_time', False)  # Pass real_time parameter if it exists
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
        
    def _get_stock_data(self, ticker):
        """
        Get stock data using the IBConnection
        
        Args:
            ticker (str): Stock ticker symbol
            
        Returns:
            dict: Stock data dictionary
        """
        conn = self._ensure_connection()
        
        try:
            # Use the get_stock_data method which now has proper fallbacks to mock data
            stock_data = conn.get_stock_data(ticker)
            
            if not stock_data:
                logger.warning(f"Failed to get stock data for {ticker}, returning default values")
                # Return a default structure
                return {
                    'symbol': ticker,
                    'last': 0,
                    'price': 0,
                    'bid': 0,
                    'ask': 0,
                    'high': 0,
                    'low': 0,
                    'close': 0,
                    'open': 0,
                    'volume': 0,
                    'timestamp': datetime.now().isoformat(),
                    'error': 'Failed to retrieve data'
                }
            
            # Ensure we have a 'price' field which some code might expect
            if 'price' not in stock_data and 'last' in stock_data:
                stock_data['price'] = stock_data['last']
                
            return stock_data
        except Exception as e:
            logger.error(f"Error getting stock data for {ticker}: {str(e)}")
            return {
                'symbol': ticker,
                'last': 0,
                'price': 0,
                'bid': 0,
                'ask': 0,
                'high': 0,
                'low': 0,
                'close': 0,
                'open': 0,
                'volume': 0,
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
        
    
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
    
    def _generate_mock_option_data(self, ticker, stock_price, otm_percentage, for_calls, for_puts, expiration):
        """
        Generate mock option data when real data is not available
        
        Args:
            ticker (str): Stock ticker symbol
            stock_price (float): Current stock price
            otm_percentage (float): Percentage out of the money
            for_calls (bool): Whether to generate call options
            for_puts (bool): Whether to generate put options
            expiration (str): Expiration date in YYYYMMDD format
            
        Returns:
            dict: Mock option data
        """
        logger.info(f"Generating mock option data for {ticker} at price {stock_price}")
        
        # Get date information
        today = datetime.now()
        
        try:
            # Parse expiration date or use next monthly expiration if not provided
            if expiration:
                exp_date = datetime.strptime(expiration, '%Y%m%d')
            else:
                # Get next monthly expiration if none provided
                exp_date = get_next_monthly_expiration()
                expiration = exp_date.strftime('%Y%m%d')
            
            days_to_expiry = (exp_date - today).days
            if days_to_expiry < 0:
                days_to_expiry = 30  # Default to 30 days if expiration is invalid
                exp_date = today + timedelta(days=30)
                expiration = exp_date.strftime('%Y%m%d')
        except Exception as e:
            # Default to 30 days if expiration date is invalid
            logger.warning(f"Error parsing expiration date: {e}, using default")
            days_to_expiry = 30
            exp_date = today + timedelta(days=30)
            expiration = exp_date.strftime('%Y%m%d')
            
        # Calculate target strikes
        call_strike = round(stock_price * (1 + otm_percentage / 100), 2)
        put_strike = round(stock_price * (1 - otm_percentage / 100), 2)
        
        # Adjust to standard strike increments
        call_strike = self._adjust_to_standard_strike(call_strike)
        put_strike = self._adjust_to_standard_strike(put_strike)
        
        result = {
            'call': None,
            'put': None,
            'stock_price': stock_price,
            'expiration': expiration,
            'days_to_expiry': days_to_expiry,
            'otm_percentage': otm_percentage
        }
        
        # Calculate time value factor (more time = more extrinsic value)
        time_factor = min(1.0, days_to_expiry / 365)
        
        # Calculate implied volatility based on stock price and days to expiry
        # Higher stock prices and longer expirations typically have higher IV
        base_iv = 0.30  # 30% base IV
        
        if for_calls:
            # Calculate intrinsic value for call
            call_intrinsic = max(0, stock_price - call_strike)
            
            # Calculate IV with price factor for call
            call_price_factor = 1.0 + (abs(stock_price - call_strike) / stock_price) * 0.5
            call_iv = base_iv * call_price_factor * (1 + time_factor * 0.5)
            
            # Calculate extrinsic value based on IV, time, and distance from ATM
            call_atm_factor = 1.0 - min(1.0, abs(stock_price - call_strike) / stock_price)
            call_extrinsic = stock_price * call_iv * time_factor * call_atm_factor
            
            # Total option price
            call_price = call_intrinsic + call_extrinsic
            call_price = max(0.05, call_price)
            
            # Calculate delta for call
            call_delta = 0.5
            if stock_price > call_strike:
                call_delta = 0.6 + (0.4 * min(1.0, (stock_price - call_strike) / call_strike))
            else:
                call_delta = 0.4 * min(1.0, (stock_price / call_strike))
            
            # Generate bid/ask spread
            call_spread_factor = 0.05 + (0.15 * (1 - call_atm_factor))  # Wider spreads for further OTM options
            call_bid = round(call_price * (1 - call_spread_factor), 2)
            call_ask = round(call_price * (1 + call_spread_factor), 2)
            call_last = round((call_bid + call_ask) / 2, 2)
            
            # Calculate call option earnings data
            position_qty = 100  # Assume 100 shares per standard position
            max_contracts = int(position_qty / 100)  # Each contract represents 100 shares
            premium_per_contract = call_price * 100  # Premium per contract (100 shares)
            total_premium = premium_per_contract * max_contracts
            return_on_capital = (total_premium / (call_strike * 100 * max_contracts)) * 100
            
            # Create call option data with earnings
            result['call'] = {
                'symbol': f"{ticker}{expiration}C{int(call_strike)}",
                'strike': call_strike,
                'expiration': expiration,
                'option_type': 'CALL',
                'bid': call_bid,
                'ask': call_ask,
                'last': call_last,
                'volume': int(random.uniform(100, 5000)),
                'open_interest': int(random.uniform(500, 20000)),
                'implied_volatility': round(call_iv * 100, 2),  # Convert to percentage
                'delta': round(call_delta, 5),
                'gamma': round(0.06 * call_atm_factor, 5),
                'theta': round(-(call_price * 0.01) / max(1, days_to_expiry), 5),
                'vega': round(call_price * 0.1, 5),
                'is_mock': True,
                # Add earnings data
                'earnings': {
                    'max_contracts': max_contracts,
                    'premium_per_contract': premium_per_contract,
                    'total_premium': total_premium,
                    'return_on_capital': return_on_capital
                }
            }
        
        if for_puts:
            # Calculate intrinsic value for put
            put_intrinsic = max(0, put_strike - stock_price)
            
            # Calculate IV with price factor for put
            put_price_factor = 1.0 + (abs(stock_price - put_strike) / stock_price) * 0.5
            put_iv = base_iv * put_price_factor * (1 + time_factor * 0.5)
            
            # Calculate extrinsic value based on IV, time, and distance from ATM
            put_atm_factor = 1.0 - min(1.0, abs(stock_price - put_strike) / stock_price)
            put_extrinsic = stock_price * put_iv * time_factor * put_atm_factor
            
            # Total option price
            put_price = put_intrinsic + put_extrinsic
            put_price = max(0.05, put_price)
            
            # Calculate delta for put
            put_delta = -0.5
            if stock_price < put_strike:
                put_delta = -0.6 - (0.4 * min(1.0, (put_strike - stock_price) / put_strike))
            else:
                put_delta = -0.4 * min(1.0, (put_strike / stock_price))
            
            # Generate bid/ask spread
            put_spread_factor = 0.05 + (0.15 * (1 - put_atm_factor))  # Wider spreads for further OTM options
            put_bid = round(put_price * (1 - put_spread_factor), 2)
            put_ask = round(put_price * (1 + put_spread_factor), 2)
            put_last = round((put_bid + put_ask) / 2, 2)
            
            # Calculate put option earnings data
            position_value = put_strike * 100 * int(position_qty / 100)  # Cash needed to secure puts
            max_contracts = int(position_value / (put_strike * 100))
            premium_per_contract = put_price * 100  # Premium per contract
            total_premium = premium_per_contract * max_contracts
            return_on_cash = (total_premium / position_value) * 100
            
            # Create put option data with earnings
            result['put'] = {
                'symbol': f"{ticker}{expiration}P{int(put_strike)}",
                'strike': put_strike,
                'expiration': expiration,
                'option_type': 'PUT',
                'bid': put_bid,
                'ask': put_ask,
                'last': put_last,
                'volume': int(random.uniform(100, 5000)),
                'open_interest': int(random.uniform(500, 20000)),
                'implied_volatility': round(put_iv * 100, 2),  # Convert to percentage
                'delta': round(put_delta, 5),
                'gamma': round(0.06 * put_atm_factor, 5),
                'theta': round(-(put_price * 0.01) / max(1, days_to_expiry), 5),
                'vega': round(put_price * 0.1, 5),
                'is_mock': True,
                # Add earnings data
                'earnings': {
                    'max_contracts': max_contracts,
                    'premium_per_contract': premium_per_contract,
                    'total_premium': total_premium,
                    'return_on_cash': return_on_cash
                }
            }
        
        return result
        
    def _adjust_to_standard_strike(self, price):
        """
        Adjust a price to a standard strike price
        
        Args:
            price (float): Price to adjust
            
        Returns:
            float: Adjusted standard strike price
        """
        if price < 5:
            # $0.50 increments for stocks under $5
            return round(price * 2) / 2
        elif price < 25:
            # $1 increments for stocks $5-$25
            return round(price)
        elif price < 100:
            # $2.50 increments for stocks $25-$100
            return round(price / 2.5) * 2.5
        elif price < 250:
            # $5 increments for stocks $100-$250
            return round(price / 5) * 5
        else:
            # $10 increments for stocks over $250
            return round(price / 10) * 10
      
    def get_otm_options(self, tickers=None, otm_percentage=10):
        start_time = time.time()
        
        # Initialize a new connection with real-time flag if needed
        if self.connection is None or not self.connection.is_connected():
            logger.info("Creating new real-time connection for options")
            unique_client_id = int(time.time() % 10000) + random.randint(1000, 9999)
            self.connection = IBConnection(
                host=self.config.get('host', '127.0.0.1'),
                port=self.config.get('port', 7497),
                client_id=unique_client_id,
                timeout=self.config.get('timeout', 20),
                readonly=self.config.get('readonly', True),
                real_time=True
            )
            logger.info(f"Attempting to connect with real-time mode with client ID {unique_client_id}")
            connected = self.connection.connect()
            logger.info(f"Connection attempt result: {'Connected' if connected else 'Failed'}")
        else:
            self._ensure_connection()
        
        # Determine market status if not provided
        if is_market_open is None:
            is_market_open = self.connection._is_market_hours() if self.connection and self.connection.is_connected() else False
            if not self.connection or not self.connection.is_connected():
                logger.warning("Could not establish connection to market data provider")
                is_market_open = False
            
        # Safely get portfolio data
        positions = {}
        try:
            if self.connection and self.connection.is_connected():
                logger.info("Attempting to retrieve portfolio data")
                portfolio_data = self.connection.get_portfolio()
                
                positions = portfolio_data.get('positions', {})
                logger.info(f"Portfolio has {len(positions)} positions")
            else:
                logger.warning("No connection available for portfolio data")
                portfolio_data = {}
        except Exception as e:
            logger.warning(f"Error getting portfolio data: {e}")
            logger.warning(traceback.format_exc())
            portfolio_data = {}
        
        # If no tickers provided, get them from portfolio
        if tickers is None:
            # First try to get tickers from positions if available
            if positions:
                try:
                    tickers = [p.get('symbol') for p in positions if p.get('symbol')]
                    logger.info(f"Using {len(tickers)} tickers from portfolio positions")
                except Exception as e:
                    logger.warning(f"Error extracting tickers from positions: {e}")
                    tickers = []
        # If no tickers and we're using mock data, provide default opportunity tickers
        if not tickers:
            logger.info("No tickers found, using default opportunity tickers for mock data")
            tickers = ['AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'TSLA', 'SPY']
                
        # Determine expiration date if not provided
        if expiration is None:
            if monthly:
                expiration_date = get_next_monthly_expiration()
            else:
                expiration_date = get_closest_friday()
            expiration = expiration_date.strftime('%Y%m%d')
        # Process each ticker
        result = {}
        use_mock = False  # Flag to track if any ticker used mock data
        
        for ticker in tickers:
            try:
                ticker_data = self._process_ticker_for_otm(self.connection, ticker, otm_percentage, expiration, is_market_open)
                result[ticker] = ticker_data
            except Exception as e:
                logger.error(f"Error processing {ticker} for OTM options: {e}")
                logger.error(traceback.format_exc())
                result[ticker] = {"error": str(e)}
        
        elapsed = time.time() - start_time
        logger.info(f"Completed OTM-based options request in {elapsed:.2f}s, real_time={self.real_time}, is_market_open={is_market_open}")
        
        # Ensure OTM percentage is included in the result
        return {'data': result}
        
    def _process_ticker_for_otm(self, conn, ticker, otm_percentage, expiration=None, is_market_open=None):
        """Process a single ticker for OTM options"""
        logger.info(f"Processing {ticker} for {otm_percentage}% OTM options")
        result = {}
        
        # Get stock price - either real or mock
        stock_price = None
        if conn and conn.is_connected() and is_market_open:
            try:
                logger.info(f"Attempting to get real-time stock price for {ticker}")
                stock_data = conn.get_market_data(ticker)
                if stock_data and isinstance(stock_data, dict):
                    stock_price = stock_data.get('last')
                    logger.info(f"Retrieved real-time stock price for {ticker}: ${stock_price}")
                else:
                    logger.warning(f"Could not get real-time stock price for {ticker}, data: {stock_data}")
            except Exception as e:
                logger.error(f"Error getting real-time stock price for {ticker}: {e}")
                logger.error(traceback.format_exc())
        
        # If we don't have a stock price, use mock data
        if stock_price is None or not isinstance(stock_price, (int, float)) or stock_price <= 0:
            try:
                logger.info(f"Getting mock stock price for {ticker}")
                stock_data = self._get_mock_stock_data(ticker)
                stock_price = stock_data.get('last', 0)
                logger.info(f"Using mock stock price for {ticker}: ${stock_price}")
            except Exception as e:
                logger.error(f"Error getting mock stock price for {ticker}: {e}")
                logger.error(traceback.format_exc())
                stock_price = 100.0  # Default fallback price
        
        # Store stock price in result
        result['stock_price'] = stock_price
        
        # Get options chain - either real or mock
        options_data = {}
        if conn and conn.is_connected() and is_market_open:
            try:
                logger.info(f"Attempting to get real-time options chain for {ticker}")
                # Calculate target strikes
                call_strike = round(stock_price * (1 + otm_percentage / 100), 2)
                put_strike = round(stock_price * (1 - otm_percentage / 100), 2)
                
                # Adjust to standard strike increments
                call_strike = self._adjust_to_standard_strike(call_strike)
                put_strike = self._adjust_to_standard_strike(put_strike)
                call_option = conn.get_option_chain(ticker, expiration,'C',call_strike);
                put_option = conn.get_option_chain(ticker, expiration,'P',call_strike);
                options = [call_option,put_option];
                if call_option and put_option:
                    logger.info(f"Successfully retrieved real-time options for {ticker}")
            
                    options_data = self._process_options_chain(options, ticker, stock_price, 
                                                              otm_percentage)
                    logger.info(f"Processed real-time options data for {ticker}")
                else:
                    logger.warning(f"Could not get real-time options chain for {ticker}")
            except Exception as e:
                logger.error(f"Error getting real-time options chain for {ticker}: {e}")
                logger.error(traceback.format_exc())
        
        # If we need to use mock data
        else:
            try:
                logger.info(f"Generating mock options data for {ticker} with {otm_percentage}% OTM")
                # Both calls and puts because we filter later
                options_data = self._generate_mock_option_data(ticker, stock_price, otm_percentage, expiration)
                logger.info(f"Successfully generated mock options data for {ticker}")
            except Exception as e:
                logger.error(f"Error generating mock options data for {ticker}: {e}")
                logger.error(traceback.format_exc())
                options_data = {'error': str(e)}
        
        # Add options data to result
        result.update(options_data)
        
        # Log summary of the results
        log_msg = f"Completed processing {ticker}"
        logger.info(log_msg)
        
        return result

    def _get_mock_stock_data(self, ticker):
        """Generate realistic mock stock data for a ticker"""
        # Use realistic default prices based on ticker
        default_prices = {
            'AAPL': 175.0,
            'MSFT': 410.0,
            'GOOGL': 150.0,
            'AMZN': 180.0,
            'META': 480.0,
            'TSLA': 175.0,
            'NVDA': 880.0,
            'AMD': 160.0,
            'INTC': 40.0,
            'SPY': 510.0,
            'QQQ': 430.0,
            'DIA': 380.0,
            'IWM': 210.0
        }
        
        # Get base price
        base_price = default_prices.get(ticker, 100.0)
        
        # Add small random variation (+/- 2%)
        variation = random.uniform(-0.02, 0.02)
        price = base_price * (1 + variation)
        
        # Round to 2 decimal places
        price = round(price, 2)
        
        # Create mock stock data structure
        return {
            'symbol': ticker,
            'last': price,
            'bid': round(price * 0.998, 2),  # 0.2% below last
            'ask': round(price * 1.002, 2),  # 0.2% above last
            'volume': random.randint(100000, 10000000),
            'open': round(price * (1 + random.uniform(-0.01, 0.01)), 2),
            'high': round(price * (1 + random.uniform(0, 0.015)), 2),
            'low': round(price * (1 - random.uniform(0, 0.015)), 2),
            'close': None,  # Not applicable for current day
            'is_mock': True
        } 

    def _process_options_chain(self, options, ticker, stock_price, otm_percentage, for_calls=True, for_puts=True):
        """
        Process options chain data and format it similar to mock data format
        
        Args:
            options_chain (dict): Raw options chain data from IB
            ticker (str): Stock symbol
            stock_price (float): Current stock price
            otm_percentage (float): OTM percentage to filter strikes
            for_calls (bool): Whether to process call options
            for_puts (bool): Whether to process put options
            
        Returns:
            dict: Formatted options data
        """
        try:
            if not options:
                logger.error(f"No options data available for {ticker}")
                return None
            
            result = {
                'symbol': ticker,
                'stock_price': stock_price,
                'otm_percentage': otm_percentage,
                'calls': [],
                'puts': []
            }
            
            # Process each option in the chain
            for option in options:
                # Calculate days to expiry
                expiry_date = datetime.strptime(option['expiration'], '%Y%m%d')
                days_to_expiry = (expiry_date - datetime.now()).days
                
                # Calculate ATM factor for Greeks
                atm_factor = 1.0 - min(1.0, abs(stock_price - option['strike']) / stock_price)
                
                # Format option data
                option_data = {
                    'symbol': f"{ticker}{option['expiration']}{option['option_type'][0]}{int(option['strike'])}",
                    'strike': option['strike'],
                    'expiration': option['expiration'],
                    'option_type': option['option_type'],
                    'bid': option['bid'],
                    'ask': option['ask'],
                    'last': option['last'],
                    'volume': option['volume'],
                    'open_interest': option['open_interest'],
                    'implied_volatility': round(option['implied_volatility'] * 100, 2),  # Convert to percentage
                    'delta': round(option['delta'], 5),
                    'gamma': round(0.06 * atm_factor, 5),
                    'theta': round(-(option['last'] * 0.01) / max(1, days_to_expiry), 5),
                    'vega': round(option['last'] * 0.1, 5),
                    'is_mock': False
                }
                
                # Add to appropriate list based on option type
                if option['option_type'] == 'CALL' and for_calls:
                    result['calls'].append(option_data)
                elif option['option_type'] == 'PUT' and for_puts:
                    result['puts'].append(option_data)
            
            # Sort options by strike price
            result['calls'] = sorted(result['calls'], key=lambda x: x['strike'])
            result['puts'] = sorted(result['puts'], key=lambda x: x['strike'])
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing options chain for {ticker}: {str(e)}")
            logger.error(traceback.format_exc())
            return None 