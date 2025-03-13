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
    def __init__(self, real_time=False):
        self.config = Config()
        self.connection = None
        self.db = OptionsDatabase()
        self.real_time = real_time
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
    
    def _generate_mock_option_data(self, ticker, expiration, option_type, strike, stock_data):
        """
        Generate mock option data when real data is not available
        
        Args:
            ticker (str): Stock ticker symbol
            expiration (str): Expiration date in YYYYMMDD format
            option_type (str): Option type ('C' for call, 'P' for put)
            strike (float): Strike price
            stock_data (dict): Stock data dictionary
            
        Returns:
            dict: Mock option data
        """
        logger.warning(f"Generating mock {option_type} option data for {ticker} at strike {strike}")
        
        # Get current stock price and date information
        stock_price = float(stock_data.get('last', 100))
        today = datetime.now()
        
        try:
            exp_date = datetime.strptime(expiration, '%Y%m%d')
            days_to_expiry = (exp_date - today).days
            if days_to_expiry < 0:
                days_to_expiry = 7  # Default to a week if expiration is invalid
        except:
            # Default to 30 days if expiration date is invalid
            days_to_expiry = 30
            
        # Calculate time value factor (more time = more extrinsic value)
        time_factor = min(1.0, days_to_expiry / 365)
        
        # Calculate intrinsic value
        if option_type == 'C':  # Call option
            intrinsic = max(0, stock_price - strike)
        else:  # Put option
            intrinsic = max(0, strike - stock_price)
            
        # Calculate implied volatility based on stock price and days to expiry
        # Higher stock prices and longer expirations typically have higher IV
        base_iv = 0.30  # 30% base IV
        price_factor = 1.0 + (abs(stock_price - strike) / stock_price) * 0.5
        iv = base_iv * price_factor * (1 + time_factor * 0.5)
        
        # Calculate extrinsic value based on IV, time, and distance from ATM
        atm_factor = 1.0 - min(1.0, abs(stock_price - strike) / stock_price)
        extrinsic = stock_price * iv * time_factor * atm_factor
        
        # Total option price
        option_price = intrinsic + extrinsic
        
        # Ensure minimum price
        option_price = max(0.05, option_price)
        
        # Calculate greeks
        delta = 0.5
        if option_type == 'C':
            if stock_price > strike:
                delta = 0.6 + (0.4 * min(1.0, (stock_price - strike) / strike))
            else:
                delta = 0.4 * min(1.0, (stock_price / strike))
        else:  # Put
            if stock_price < strike:
                delta = -0.6 - (0.4 * min(1.0, (strike - stock_price) / strike))
            else:
                delta = -0.4 * min(1.0, (strike / stock_price))
                
        gamma = 0.06 * atm_factor
        theta = -option_price * 0.01 / max(1, days_to_expiry)
        vega = option_price * 0.1
        
        # Generate bid/ask spread
        spread_factor = 0.05 + (0.15 * (1 - atm_factor))  # Wider spreads for further OTM options
        bid = option_price * (1 - spread_factor)
        ask = option_price * (1 + spread_factor)
        
        # Format values
        bid = round(bid, 2)
        ask = round(ask, 2)
        last = round((bid + ask) / 2, 2)
        
        # Create option data dictionary
        option_data = {
            'symbol': f"{ticker}{expiration}{option_type}{int(strike)}",
            'strike': strike,
            'expiration': expiration,
            'option_type': 'CALL' if option_type == 'C' else 'PUT',
            'bid': bid,
            'ask': ask,
            'last': last,
            'volume': int(random.uniform(100, 5000)),
            'open_interest': int(random.uniform(500, 20000)),
            'implied_volatility': round(iv * 100, 2),  # Convert to percentage
            'delta': round(delta, 3),
            'gamma': round(gamma, 3),
            'theta': round(theta, 3),
            'vega': round(vega, 3),
            'is_mock': True
        }
        
        return option_data
        
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
      
    def get_otm_options(self, tickers=None, otm_percentage=10, for_calls=True, for_puts=True, expiration=None, monthly=False, options_only=False):
        """
        Get options based on OTM percentage from current price.
        
        Args:
            tickers (list, optional): List of ticker symbols. If None, uses portfolio tickers.
            otm_percentage (float, optional): Percentage OTM for option selection. Default 10%.
            for_calls (bool, optional): Whether to fetch call options. Default True.
            for_puts (bool, optional): Whether to fetch put options. Default True.
            expiration (str, optional): Target expiration date in YYYY-MM-DD format. Default None.
            monthly (bool, optional): Whether to use monthly expiration. Default False.
            options_only (bool, optional): Whether to only fetch option data without querying stock prices. Default False.
        
        Returns:
            dict: Dictionary with option data by ticker
        """
        start_time = time.time()
        logger.info(f"Starting OTM-based options request for {otm_percentage}% OTM")
        
        conn = self._ensure_connection()
        is_market_open = conn._is_market_hours()
        
        # Safely get portfolio data
        try:
            portfolio_data = conn.get_portfolio()
            positions = portfolio_data.get('positions', {})
        except Exception as e:
            logger.warning(f"Error getting portfolio data: {str(e)}")
            portfolio_data = {}
            positions = {}
        
        # If no tickers provided, get them from portfolio
        if tickers is None:
            # Safely check if portfolio_service exists
            if hasattr(self, 'portfolio_service') and self.portfolio_service is not None:
                tickers = self.portfolio_service.get_portfolio_tickers()
            else:
                tickers = []
     
            
        # Determine expiration date if not provided
        if expiration is None:
            if monthly:
                expiration_date = get_next_monthly_expiration()
            else:
                expiration_date = get_closest_friday()
            expiration = expiration_date.strftime('%Y%m%d')
        
        # Process in parallel with ThreadPoolExecutor
        if not tickers:
            logger.warning("No tickers provided and no portfolio positions found")
            return {'expiration': expiration, 'otm_percentage': otm_percentage, 'data': {}}
        
        # Only get stock prices if options_only is False
        if not options_only:
            logger.info("Fetching current stock prices")
            stock_prices = conn.get_multiple_stock_prices(tickers)
            
            # Check for NaN or None values
            cleaned_stock_prices = {}
            for ticker, price in stock_prices.items():
                if price is None or (isinstance(price, float) and math.isnan(price)):
                    logger.warning(f"Invalid price value for {ticker}: {price}")
                else:
                    cleaned_stock_prices[ticker] = price
            stock_prices = cleaned_stock_prices
        else:
            logger.info("Skipping stock price query (options_only=True)")
            stock_prices = {}
        
        # Filter out tickers with invalid prices for market hours
        valid_tickers = []
        for ticker in tickers:
            if not options_only:
                # Only validate prices if we're not skipping stock price queries
                if ticker not in stock_prices or stock_prices[ticker] is None:
                    if is_market_open:
                        logger.error(f"Invalid stock price for {ticker} during market hours")
                        raise ValueError(f"Invalid stock price for {ticker} during market hours")
                    else:
                        logger.info(f"Invalid stock price for {ticker} during closed market, skipping")
                        continue
            valid_tickers.append(ticker)
        
        if not valid_tickers:
            if is_market_open:
                raise ValueError("No valid stock prices during market hours")
            else:
                logger.info("No valid stock prices during closed market")
                return {'expiration': expiration, 'otm_percentage': otm_percentage, 'data': {}}
        
        # Process tickers in parallel using ThreadPoolExecutor
        result = {
            'expiration': expiration,
            'otm_percentage': otm_percentage,
            'data': {}
        }
        
        # Process each ticker (sequentially to avoid threading issues)
        for ticker in valid_tickers:
            try:
                # Process the ticker to find OTM options
                ticker_result = self._process_ticker_for_otm(
                    ticker, stock_prices, expiration, otm_percentage,
                    for_calls=for_calls, for_puts=for_puts, 
                    is_market_open=is_market_open, positions=positions, 
                    portfolio_data=portfolio_data, options_only=options_only
                )
                
                if ticker_result:
                    result['data'][ticker] = ticker_result
                    
            except Exception as e:
                logger.error(f"Error processing {ticker}: {str(e)}")
                traceback.print_exc()
                if is_market_open:
                    # During market hours, we should raise exceptions
                    raise
        
        elapsed_time = time.time() - start_time
        logger.info(f"Completed OTM-based options request in {elapsed_time:.2f} seconds")
        return result
        
    def _process_ticker_for_otm(self, ticker, stock_prices, expiration, otm_percentage, 
                                 for_calls=True, for_puts=True, is_market_open=True, 
                                 positions=None, portfolio_data=None, options_only=False):
        """Process a single ticker for OTM options.
        
        Args:
            ticker (str): Ticker symbol
            stock_prices (dict): Dictionary of stock prices by ticker
            expiration (str): Expiration date to use
            otm_percentage (float): OTM percentage to target
            for_calls (bool): Whether to fetch call options. Default True.
            for_puts (bool): Whether to fetch put options. Default True.
            is_market_open (bool): Whether the market is open.
            positions (dict): Dictionary of positions by ticker
            portfolio_data (dict): Dictionary of portfolio data
            options_only (bool): Whether to only fetch option data without querying stock prices. Default False.
        
        Returns:
            dict: Option data for the ticker
        """
        # Initialize parameters to avoid None issues
        if positions is None:
            positions = {}
        if portfolio_data is None:
            portfolio_data = {}
        
        try:
            logger.info(f"Processing options for {ticker} at {otm_percentage}% OTM")
            
            # If options_only is True, get stock price from positions instead of querying
            if options_only and positions and ticker in positions:
                position = positions[ticker]
                logger.info(f"Using position price for {ticker} (options_only=True)")
                
                # Extract market price based on whether positions is a dict or an object
                if isinstance(position, dict) and 'market_price' in position:
                    current_price = float(position['market_price'])
                elif hasattr(position, 'market_price'):
                    current_price = float(position.market_price)
                else:
                    # Try to find market price in different formats
                    for key in ['price', 'last_price', 'current_price', 'last']:
                        if isinstance(position, dict) and key in position:
                            current_price = float(position[key])
                            logger.info(f"Found price for {ticker} using key: {key}")
                            break
                        elif hasattr(position, key):
                            current_price = float(getattr(position, key))
                            logger.info(f"Found price for {ticker} using attribute: {key}")
                            break
                    else:
                        logger.warning(f"No price found in position data for {ticker}, falling back to stock_prices")
                        current_price = stock_prices.get(ticker, 0)
            else:
                current_price = stock_prices.get(ticker, 0)
            
            if not current_price > 0:
                logger.warning(f"No valid price found for {ticker}. Using fallback method.")
                # Use a fallback method to get price if not available
                try:
                    current_price = self.get_last_price(ticker)
                    logger.info(f"Fallback price for {ticker}: {current_price}")
                except Exception as e:
                    logger.error(f"Failed to get fallback price for {ticker}: {str(e)}")
                    return None
            
            # Make sure we have a connection
            conn = self._ensure_connection()
            
            # Calculate target strikes based on OTM percentage
            call_strike = None
            put_strike = None
            
            if for_calls:
                # For calls, OTM means strike is higher than current price
                call_strike_raw = current_price * (1 + otm_percentage/100)
                call_strike = self._adjust_to_standard_strike(call_strike_raw)
                logger.info(f"Call target strike for {ticker}: {call_strike} ({otm_percentage}% OTM from {current_price})")
                
            if for_puts:
                # For puts, OTM means strike is lower than current price
                put_strike_raw = current_price * (1 - otm_percentage/100)
                put_strike = self._adjust_to_standard_strike(put_strike_raw)
                logger.info(f"Put target strike for {ticker}: {put_strike} ({otm_percentage}% OTM from {current_price})")
            
            # Get option chain with these specific strikes
            call_option = None
            put_option = None
            
            # Get call option
            if for_calls and call_strike:
                try:
                    call_options = conn.get_option_chain_snapshot(
                        ticker, 
                        expiration, 
                        [call_strike], 
                        rights=['C']
                    )
                    
                    if call_options and 'calls' in call_options and call_options['calls']:
                        call_option = call_options['calls'][0]
                        logger.info(f"Found call option for {ticker} at strike {call_strike}")
                except Exception as e:
                    logger.error(f"Error getting call option for {ticker}: {str(e)}")
                    if is_market_open:
                        raise
            
            # Get put option
            if for_puts and put_strike:
                try:
                    put_options = conn.get_option_chain_snapshot(
                        ticker, 
                        expiration, 
                        [put_strike], 
                        rights=['P']
                    )
                    
                    if put_options and 'puts' in put_options and put_options['puts']:
                        put_option = put_options['puts'][0]
                        logger.info(f"Found put option for {ticker} at strike {put_strike}")
                except Exception as e:
                    logger.error(f"Error getting put option for {ticker}: {str(e)}")
                    if is_market_open:
                        raise
            
            # Use mock data if needed
            if is_market_open:
                if (for_calls and not call_option) or (for_puts and not put_option):
                    raise ValueError(f"Could not find options for {ticker} during market hours")
            else:
                # Generate mock data if needed outside market hours
                stock_data = {
                    'symbol': ticker,
                    'last': current_price,
                    'price': current_price,
                    'timestamp': datetime.now().isoformat(),
                }
                
                if for_calls and not call_option and call_strike:
                    call_option = self._generate_mock_option_data(ticker, expiration, 'C', call_strike, stock_data)
                    call_option['is_mock'] = True
                    
                if for_puts and not put_option and put_strike:
                    put_option = self._generate_mock_option_data(ticker, expiration, 'P', put_strike, stock_data)
                    put_option['is_mock'] = True
            
            # Get portfolio position data for this ticker
            position_size = 0
            avg_cost = 0
            market_value = 0
            unrealized_pnl = 0
            
            # Use the portfolio data we already retrieved
            if ticker in positions:
                position = positions[ticker]
                position_size = float(position.get('shares', 0))
                avg_cost = float(position.get('avg_cost', 0))
                market_value = float(position.get('market_value', 0))
                unrealized_pnl = float(position.get('unrealized_pnl', 0))
            
            # Calculate potential earnings
            call_earnings = None
            put_earnings = None
            available_cash = 0
            
            # Safely extract available cash from portfolio data
            if portfolio_data is not None and isinstance(portfolio_data, dict):
                available_cash = portfolio_data.get('available_cash', 0)
                if available_cash is None or (isinstance(available_cash, float) and math.isnan(available_cash)):
                    available_cash = 0
            
            if call_option and position_size > 0:
                # For covered calls (only if we own the stock)
                max_contracts = int(position_size // 100)  # Each contract covers 100 shares
                bid_price = call_option.get('bid', 0)
                
                # Check for NaN values
                if isinstance(bid_price, float) and math.isnan(bid_price):
                    bid_price = 0
                    
                premium_per_contract = float(bid_price) * 100  # Convert to dollar amount
                total_premium = premium_per_contract * max_contracts
                
                # Check for division by zero or NaN
                if max_contracts > 0 and current_price > 0:
                    return_on_capital = (total_premium / (current_price * 100 * max_contracts)) * 100
                else:
                    return_on_capital = 0
                
                call_earnings = {
                    'strategy': 'Covered Call',
                    'max_contracts': max_contracts,
                    'premium_per_contract': premium_per_contract,
                    'total_premium': total_premium,
                    'return_on_capital': return_on_capital
                }
            
            if put_option:
                # For cash-secured puts
                put_strike_val = float(put_option.get('strike', 0))
                bid_price = put_option.get('bid', 0)
                
                # Check for NaN values
                if isinstance(bid_price, float) and math.isnan(bid_price):
                    bid_price = 0
                
                if isinstance(put_strike_val, float) and math.isnan(put_strike_val):
                    logger.warning(f"NaN strike price for {ticker} put option, using current price instead")
                    put_strike_val = current_price
                
                safety_margin = 0.8  # Use only 80% of available funds
                max_position_value = available_cash * safety_margin
                
                # Avoid division by zero and ensure valid values for calculation
                if put_strike_val > 0:
                    max_contracts = int(max_position_value // (put_strike_val * 100))
                else:
                    max_contracts = 0
                    
                premium_per_contract = float(bid_price) * 100  # Convert to dollar amount
                total_premium = premium_per_contract * max_contracts
                
                # Check for division by zero or NaN
                if max_contracts > 0 and put_strike_val > 0:
                    return_on_cash = (total_premium / (put_strike_val * 100 * max_contracts)) * 100
                else:
                    return_on_cash = 0
                
                put_earnings = {
                    'strategy': 'Cash-Secured Put',
                    'max_contracts': max_contracts,
                    'premium_per_contract': premium_per_contract,
                    'total_premium': total_premium,
                    'return_on_cash': return_on_cash
                }
            
            # Build result for this ticker
            ticker_result = {
                'ticker': ticker,
                'price': current_price,
                'position': {
                    'size': position_size,
                    'avg_cost': avg_cost,
                    'market_value': market_value,
                    'unrealized_pnl': unrealized_pnl
                }
            }
            
            # Add call data if available
            if call_option:
                # Ensure delta value is valid
                delta = call_option.get('delta', 0)
                if isinstance(delta, float) and math.isnan(delta):
                    delta = 0
                
                ticker_result['call'] = {
                    'strike': float(call_option.get('strike', 0)),
                    'bid': float(call_option.get('bid', 0) if not math.isnan(call_option.get('bid', 0)) else 0),
                    'ask': float(call_option.get('ask', 0) if not math.isnan(call_option.get('ask', 0)) else 0),
                    'delta': float(delta),
                    'earnings': call_earnings,
                    'is_mock': call_option.get('is_mock', False)
                }
            
            # Add put data if available
            if put_option:
                # Ensure delta value is valid
                delta = put_option.get('delta', 0)
                if isinstance(delta, float) and math.isnan(delta):
                    delta = 0
                
                ticker_result['put'] = {
                    'strike': float(put_option.get('strike', 0)),
                    'bid': float(put_option.get('bid', 0) if not math.isnan(put_option.get('bid', 0)) else 0),
                    'ask': float(put_option.get('ask', 0) if not math.isnan(put_option.get('ask', 0)) else 0),
                    'delta': float(delta),
                    'earnings': put_earnings,
                    'is_mock': put_option.get('is_mock', False)
                }
            
            logger.info(f"Successfully processed {ticker} with {otm_percentage}% OTM options")
            return ticker_result
            
        except Exception as e:
            logger.error(f"Error processing {ticker} with OTM percentage {otm_percentage}: {str(e)}")
            if is_market_open:
                raise
            return None

    def get_last_price(self, ticker):
        """
        Get the last price for a ticker using a fallback method
        
        Args:
            ticker (str): Ticker symbol
            
        Returns:
            float: Last price for the ticker
        """
        logger.info(f"Getting last price for {ticker} using fallback method")
        
        try:
            # Use a simplified approach with default prices for common tickers
            default_prices = {
                'AAPL': 175.0,
                'MSFT': 320.0,
                'AMZN': 175.0,
                'GOOGL': 145.0,
                'META': 468.0,
                'TSLA': 175.0,
                'NVDA': 850.0,
                'JPM': 185.0,
                'V': 270.0,
                'WMT': 60.0
            }
            
            if ticker in default_prices:
                price = default_prices[ticker]
                logger.info(f"Using default price for {ticker}: {price}")
                return price
                
            # If all else fails, return a default value
            logger.warning(f"No price found for {ticker}, using default price of 100.0")
            return 100.0
            
        except Exception as e:
            logger.error(f"Error getting last price for {ticker}: {str(e)}")
            # Return a default price as a last resort
            return 100.0 