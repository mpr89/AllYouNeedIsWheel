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
import traceback

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
        
    def get_options_data(self, ticker, expiration=None):
        """
        Get options data for a specific stock ticker
        
        Args:
            ticker (str): Stock ticker symbol
            expiration (str, optional): Expiration date (YYYYMMDD format)
            
        Returns:
            dict: Options data including stock data, expirations, and options
        """
        logger.info(f"Getting options data for {ticker}")
        
        try:
            # Ensure connection
            conn = self._ensure_connection()
            if not conn:
                return {"error": "Failed to connect to Interactive Brokers"}
            
            # Get stock data
            stock_data = self._get_stock_data(ticker)
            if "error" in stock_data:
                return {"error": f"Failed to get stock data for {ticker}"}
            
            # Get expiration dates
            try:
                expirations = conn.get_available_expirations(ticker)
                
                if not expirations or len(expirations) == 0:
                    logger.warning(f"No expirations found for {ticker}, using default expirations")
                    # Create default expirations
                    today = datetime.now()
                    expirations = [
                        get_closest_friday(today).strftime('%Y%m%d'),
                        get_closest_friday(today + timedelta(days=7)).strftime('%Y%m%d'),
                        get_next_monthly_expiration(today).strftime('%Y%m%d')
                    ]
                    
                selected_expiration = expiration or expirations[0]
                if selected_expiration not in expirations:
                    logger.warning(f"Requested expiration {expiration} not found. Using {expirations[0]} instead.")
                    selected_expiration = expirations[0]
                    
            except Exception as e:
                logger.error(f"Error getting option expiration dates: {e}")
                # Create default expirations
                today = datetime.now()
                expirations = [
                    get_closest_friday(today).strftime('%Y%m%d'),
                    get_closest_friday(today + timedelta(days=7)).strftime('%Y%m%d'),
                    get_next_monthly_expiration(today).strftime('%Y%m%d')
                ]
                selected_expiration = expirations[0]
                logger.info(f"Using default expiration: {selected_expiration}")
            
            # Generate strike prices around the current stock price
            try:
                current_price = stock_data.get('last', 100)  # Default to 100 if no price available
                
                # Generate strikes directly instead of trying to call a method that doesn't exist
                base_strike = self._adjust_to_standard_strike(current_price)
                
                # Generate strikes at different increments based on stock price
                if current_price < 25:
                    increment = 1.0
                    num_strikes = 5
                elif current_price < 100:
                    increment = 2.5
                    num_strikes = 7
                elif current_price < 250:
                    increment = 5.0
                    num_strikes = 9
                else:
                    increment = 10.0
                    num_strikes = 11
                
                strikes = []
                for i in range(-(num_strikes//2), (num_strikes//2) + 1):
                    strike = round(base_strike + (i * increment), 2)
                    if strike > 0:  # Ensure positive strikes
                        strikes.append(strike)
                
                logger.info(f"Generated {len(strikes)} strikes around {base_strike}")
                
            except Exception as e:
                logger.error(f"Error generating strike prices: {str(e)}")
                # Generate default strikes
                current_price = stock_data.get('last', 100)
                base_strike = self._adjust_to_standard_strike(current_price)
                strikes = [
                    round(base_strike * 0.7, 2),
                    round(base_strike * 0.8, 2),
                    round(base_strike * 0.9, 2),
                    base_strike,
                    round(base_strike * 1.1, 2),
                    round(base_strike * 1.2, 2),
                    round(base_strike * 1.3, 2)
                ]
                logger.info(f"Using default strikes: {strikes}")
            
            # Get options chain
            options_data = []
            has_real_time_data = False
            has_historical_data = False
            
            # Find ATM strike (closest to current stock price)
            stock_price = stock_data.get('last', 0)
            atm_strike = min(strikes, key=lambda x: abs(x - stock_price))
            
            # Get a few strikes above and below ATM
            relevant_strikes = []
            for strike in strikes:
                if abs(strike - atm_strike) <= 20:  # Get strikes within $20 of ATM
                    relevant_strikes.append(strike)
            
            if not relevant_strikes:
                relevant_strikes = strikes[:5] if strikes else []
            
            # Try to get option chain data
            try:
                option_chain = conn.get_option_chain(ticker, selected_expiration)
                
                if option_chain and 'calls' in option_chain and 'puts' in option_chain:
                    has_real_time_data = True
                    
                    # Process each strike
                    for strike in relevant_strikes:
                        call_data = None
                        put_data = None
                        
                        # Find call option for this strike
                        for call in option_chain['calls']:
                            if abs(float(call.get('strike', 0)) - float(strike)) < 0.01:
                                call_data = call
                                break
                                
                        # Find put option for this strike
                        for put in option_chain['puts']:
                            if abs(float(put.get('strike', 0)) - float(strike)) < 0.01:
                                put_data = put
                                break
                                
                        # If we couldn't find real data, generate mock data
                        if not call_data:
                            call_data = self._generate_mock_option_data(ticker, selected_expiration, 'C', strike, stock_data)
                        if not put_data:
                            put_data = self._generate_mock_option_data(ticker, selected_expiration, 'P', strike, stock_data)
                            
                        # Add to options data
                        options_data.append({
                            'strike': strike,
                            'call': call_data,
                            'put': put_data
                        })
                else:
                    # No real-time data, use mock data
                    for strike in relevant_strikes:
                        call_data = self._generate_mock_option_data(ticker, selected_expiration, 'C', strike, stock_data)
                        put_data = self._generate_mock_option_data(ticker, selected_expiration, 'P', strike, stock_data)
                        
                        options_data.append({
                            'strike': strike,
                            'call': call_data,
                            'put': put_data
                        })
                        
                    has_historical_data = True
                    logger.warning(f"Using mock options data for {ticker}")
            except Exception as e:
                logger.error(f"Error getting option chain: {str(e)}")
                # Use mock data as fallback
                for strike in relevant_strikes:
                    call_data = self._generate_mock_option_data(ticker, selected_expiration, 'C', strike, stock_data)
                    put_data = self._generate_mock_option_data(ticker, selected_expiration, 'P', strike, stock_data)
                    
                    options_data.append({
                        'strike': strike,
                        'call': call_data,
                        'put': put_data
                    })
                    
                has_historical_data = True
                logger.warning(f"Using mock options data for {ticker} due to error: {str(e)}")
            
            if not options_data:
                if not has_real_time_data and not has_historical_data:
                    return {"error": f"No options data available for {ticker}"}
            
            # Process and return the data
            result = {
                "ticker": ticker,
                "stock_data": stock_data,
                "expiration": selected_expiration,
                "expirations": expirations,
                "options": options_data,
                "using_historical_data": not has_real_time_data and has_historical_data
            }
            
            logger.info(f"Successfully retrieved options data for {ticker}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting options data: {str(e)}")
            logger.debug(traceback.format_exc())
            return {"error": f"Failed to get options data: {str(e)}"}
    
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
        try:
            conn = self._ensure_connection()
            if not conn:
                logger.error(f"Failed to connect to TWS for {ticker}")
                return self._get_default_expirations()
                
            # Use the correct method name
            expirations = conn.get_available_expirations(ticker)
            
            if not expirations or len(expirations) == 0:
                logger.warning(f"No expirations found for {ticker}, using default expirations")
                return self._get_default_expirations()
            
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
                except Exception as date_error:
                    logger.error(f"Error formatting expiration date {exp}: {str(date_error)}")
                    # Skip this expiration date
            
            # Sort by days to expiry
            formatted_expirations.sort(key=lambda x: x['days_to_expiry'])
            
            return formatted_expirations
        except Exception as e:
            logger.error(f"Error getting expirations for {ticker}: {str(e)}")
            return self._get_default_expirations()
            
    def _get_default_expirations(self):
        """
        Generate default expiration dates when real data is not available
        
        Returns:
            list: Default expiration dates
        """
        today = datetime.now()
        
        # Generate weekly expirations for the next 4 weeks
        weekly_expirations = []
        for i in range(4):
            exp_date = get_closest_friday(today + timedelta(days=i*7))
            days_to_expiry = (exp_date - today).days
            
            weekly_expirations.append({
                'date': exp_date.strftime('%Y%m%d'),
                'formatted_date': exp_date.strftime('%Y-%m-%d'),
                'days_to_expiry': days_to_expiry
            })
            
        # Add monthly expirations for the next 3 months
        monthly_expirations = []
        for i in range(1, 4):
            exp_date = get_next_monthly_expiration(today + timedelta(days=i*30))
            days_to_expiry = (exp_date - today).days
            
            # Only add if not already in weekly expirations
            if not any(w['date'] == exp_date.strftime('%Y%m%d') for w in weekly_expirations):
                monthly_expirations.append({
                    'date': exp_date.strftime('%Y%m%d'),
                    'formatted_date': exp_date.strftime('%Y-%m-%d'),
                    'days_to_expiry': days_to_expiry
                })
                
        # Combine and sort by days to expiry
        all_expirations = weekly_expirations + monthly_expirations
        all_expirations.sort(key=lambda x: x['days_to_expiry'])
        
        logger.info(f"Generated {len(all_expirations)} default expirations")
        return all_expirations
    
    def get_recommendations(self, tickers=None, strategy='simple', expiration=None):
        """
        Get option trade recommendations based on strategy
        
        Args:
            tickers (list, optional): List of ticker symbols
            strategy (str, optional): Strategy name
            expiration (str, optional): Expiration date (YYYYMMDD format)
            
        Returns:
            dict: Option recommendations
        """
        conn = self._ensure_connection()
        
        # If no tickers provided, get them from portfolio
        if tickers is None:
            portfolio_data = conn.get_portfolio()
            positions = portfolio_data.get('positions', {})
            tickers = [symbol for symbol, pos in positions.items() 
                      if isinstance(pos, dict) and pos.get('security_type', 'STK') == 'STK']
        
        # Apply strategy to get recommendations
        if strategy == 'simple':
            recommendations = self._generate_simple_options_recommendations(
                tickers, expiration
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
        
    def _generate_simple_options_recommendations(self, tickers, expiration):
        """
        Generate recommendations using the simple options strategy
        
        Args:
            tickers (list): List of ticker symbols
            expiration (str): Expiration date in YYYYMMDD format
            
        Returns:
            list: List of recommendation dictionaries
        """
        conn = self._ensure_connection()
        recommendations = []
        
        # Get portfolio for position information
        portfolio_data = conn.get_portfolio()
        positions = portfolio_data.get('positions', {})
        portfolio = {}
        
        for symbol, pos in positions.items():
            if isinstance(pos, dict) and pos.get('security_type', 'STK') == 'STK':
                portfolio[symbol] = {
                    'size': float(pos.get('shares', 0)),
                    'avg_cost': float(pos.get('avg_cost', 0)),
                    'market_value': float(pos.get('market_value', 0)),
                    'unrealized_pnl': float(pos.get('unrealized_pnl', 0))
                }
        
        # Get all stock prices in one request
        logger.info(f"Fetching stock prices for tickers: {tickers}")
        stock_prices = {}
        
        # Get stock data for each ticker
        for ticker in tickers:
            stock_data = self._get_stock_data(ticker)
            if stock_data and 'last' in stock_data:
                stock_prices[ticker] = stock_data['last']
        
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
        
        # Process each ticker
        for ticker in valid_tickers:
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
                
                # Try to get option chain data
                option_chain = conn.get_option_chain(ticker, expiration)
                
                # Extract call and put data for these strikes
                call_data = None
                put_data = None
                
                if option_chain and 'calls' in option_chain and 'puts' in option_chain:
                    # Find call option with this strike
                    for call in option_chain['calls']:
                        if abs(float(call.get('strike', 0)) - float(call_strike)) < 0.01:
                            call_data = call
                            break
                            
                    # Find put option with this strike
                    for put in option_chain['puts']:
                        if abs(float(put.get('strike', 0)) - float(put_strike)) < 0.01:
                            put_data = put
                            break
                
                # If we couldn't find the options in the chain, generate mock data
                if not call_data:
                    call_data = self._generate_mock_option_data(ticker, expiration, 'C', call_strike, {'last': stock_price})
                if not put_data:
                    put_data = self._generate_mock_option_data(ticker, expiration, 'P', put_strike, {'last': stock_price})
                
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
                            'last': put_data['last'] if put_data and 'last' in put_data else None,
                            'is_historical': put_data.get('is_historical', False) if put_data else False
                        },
                        'call': {
                            'strike': call_strike,
                            'bid': call_data['bid'] if call_data and 'bid' in call_data else None,
                            'ask': call_data['ask'] if call_data and 'ask' in call_data else None,
                            'last': call_data['last'] if call_data and 'last' in call_data else None,
                            'is_historical': call_data.get('is_historical', False) if call_data else False
                        }
                    },
                    'recommendation': recommendation
                }
                
                recommendations.append(result)
            except Exception as e:
                logger.error(f"Error processing {ticker}: {str(e)}")
                logger.error(traceback.format_exc())
        
        return recommendations
        
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
            
        Raises:
            ValueError: If no suitable options found during market hours
            ConnectionError: If connection fails during market hours
        """
        start_time = time.time()
        logger.info(f"Starting delta-targeted options request for target delta {target_delta}")
        
        conn = self._ensure_connection()
        is_market_open = conn._is_market_hours()
        
        # Get portfolio data once at the beginning
        portfolio_data = conn.get_portfolio()  # This will raise during market hours if no data
        positions = portfolio_data.get('positions', {})
        
        # If no tickers provided, get them from portfolio
        if tickers is None:
            tickers = [symbol for symbol, pos in positions.items() 
                      if isinstance(pos, dict) and pos.get('security_type', 'STK') == 'STK']
            
        # Determine expiration date if not provided
        if expiration is None:
            if monthly:
                expiration_date = get_next_monthly_expiration()
            else:
                expiration_date = get_closest_friday()
            expiration = expiration_date.strftime('%Y%m%d')
        
        # Get all stock prices in bulk
        logger.info(f"Fetching stock data for {len(tickers)} tickers in bulk")
        stock_prices = conn.get_multiple_stock_prices(tickers)
        
        # Filter out tickers with invalid prices for market hours
        valid_tickers = []
        for ticker in tickers:
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
                return {'expiration': expiration, 'target_delta': target_delta, 'data': {}}
        
        # Calculate strikes based on target delta for each ticker
        strikes_map = {}
        for ticker in valid_tickers:
            current_price = stock_prices[ticker]
            
            # For delta-targeted strikes, we need to calculate strikes around current price
            if current_price < 25:
                increment = 1.0
                num_strikes = 10
            elif current_price < 100:
                increment = 2.5
                num_strikes = 15
            elif current_price < 250:
                increment = 5.0
                num_strikes = 20
            else:
                increment = 10.0
                num_strikes = 25
            
            # Calculate a range of strikes around the current price
            strikes = []
            base_strike = self._adjust_to_standard_strike(current_price)
            for i in range(-(num_strikes//2), (num_strikes//2) + 1):
                strike = round(base_strike + (i * increment), 2)
                if strike > 0:
                    strikes.append(strike)
            
            strikes_map[ticker] = strikes
            
        # Get options data for all stocks in bulk
        logger.info(f"Fetching options data for {len(valid_tickers)} tickers with expiration {expiration} in bulk")
        rights = ['C', 'P']  # Both calls and puts
        
        try:
            # Get all option prices in one batch request
            options_data = conn.get_multiple_stocks_option_prices(
                valid_tickers, 
                expiration, 
                strikes_map=strikes_map,
                rights=rights
            )
        except Exception as e:
            if is_market_open:
                logger.error(f"Error getting options data during market hours: {str(e)}")
                raise
            else:
                logger.info(f"Error getting options data during closed market, falling back to individual requests")
                options_data = {}
                
        # Check if we got valid options data
        if not options_data and is_market_open:
            raise ValueError("No options data available during market hours")
        
        # Prepare result structure
        result = {
            'expiration': expiration,
            'target_delta': target_delta,
            'data': {}
        }
            
        # Process each ticker
        for ticker in valid_tickers:
            try:
                current_price = stock_prices[ticker]
                if current_price == 0:
                    if is_market_open:
                        raise ValueError(f"Invalid stock price (0) for {ticker} during market hours")
                    else:
                        logger.info(f"Invalid stock price for {ticker} during closed market. Skipping.")
                        continue
                
                # Convert stock price to stock data structure for compatibility
                stock_data = {
                    'symbol': ticker,
                    'last': current_price,
                    'price': current_price,
                    'timestamp': datetime.now().isoformat(),
                }
                
                # Get option data for this ticker
                ticker_options = options_data.get(ticker, {})
                
                # Prepare calls and puts
                calls = []
                puts = []
                
                if ticker_options:
                    # Process the ticker options from bulk request
                    for (strike, right), option_data in ticker_options.items():
                        option_dict = {
                            'symbol': ticker,
                            'expiration': expiration,
                            'strike': strike,
                            'right': right,
                            'bid': option_data.get('bid', 0),
                            'ask': option_data.get('ask', 0),
                            'last': option_data.get('last', 0),
                            'is_mock': False
                        }
                        
                        # Calculate delta if not provided
                        if right == 'C':  # Call
                            # Delta decreases as strike increases (from ~1.0 ATM to ~0.0 far OTM)
                            delta = max(0.01, min(0.99, 0.5 - (strike - current_price) / (current_price * 0.2)))
                            option_dict['delta'] = round(delta, 3)
                            calls.append(option_dict)
                        else:  # Put
                            # Put delta increases as strike decreases (from ~-1.0 ATM to ~0.0 far OTM)
                            delta = max(-0.99, min(-0.01, -0.5 + (strike - current_price) / (current_price * 0.2)))
                            option_dict['delta'] = round(delta, 3)
                            puts.append(option_dict)
                
                # If no option data from bulk request, fall back to individual request or mock
                if (not calls or not puts):
                    if is_market_open:
                        # During market hours, try individual request one more time
                        try:
                            option_chain = conn.get_option_chain(ticker, expiration)
                            if option_chain and 'calls' in option_chain and 'puts' in option_chain:
                                calls = option_chain['calls']
                                puts = option_chain['puts']
                            else:
                                raise ValueError(f"No option chain data available for {ticker} during market hours")
                        except Exception as e:
                            logger.error(f"Error getting option chain for {ticker} during market hours: {str(e)}")
                            raise
                    else:
                        # Outside market hours, generate mock data
                        logger.info(f"No option data for {ticker} during closed market. Using mock data.")
                        option_chain = self._generate_mock_option_chain(ticker, current_price, expiration)
                        calls = option_chain['calls']
                        puts = option_chain['puts']
                
                # Find call and put with delta closest to target
                best_call = None
                best_put = None
                best_call_delta_diff = 1.0
                best_put_delta_diff = 1.0
                
                # Process calls
                for call in calls:
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
                for put in puts:
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
                
                # If we couldn't find options with delta in range, use the closest ones
                if not best_call:
                    for call in calls:
                        if float(call.get('strike', 0)) > current_price:
                            delta = abs(float(call.get('delta', 0) or 0))
                            delta_diff = abs(delta - target_delta)
                            if delta_diff < best_call_delta_diff:
                                best_call = call
                                best_call_delta_diff = delta_diff
                
                if not best_put:
                    for put in puts:
                        if float(put.get('strike', 0)) < current_price:
                            delta = abs(float(put.get('delta', 0) or 0))
                            delta_diff = abs(delta - target_delta)
                            if delta_diff < best_put_delta_diff:
                                best_put = put
                                best_put_delta_diff = delta_diff
                
                # During market hours, we must have both a call and put
                if is_market_open and (not best_call or not best_put):
                    raise ValueError(f"Could not find suitable options for {ticker} during market hours")
                
                # Outside market hours, generate mock data if needed
                if not is_market_open:
                    if not best_call:
                        target_call_strike = current_price * (1 + target_delta)
                        best_call = self._generate_mock_option_data(ticker, expiration, 'C', target_call_strike, stock_data)
                        best_call['delta'] = target_delta
                        best_call['is_mock'] = True
                        
                    if not best_put:
                        target_put_strike = current_price * (1 - target_delta)
                        best_put = self._generate_mock_option_data(ticker, expiration, 'P', target_put_strike, stock_data)
                        best_put['delta'] = -target_delta
                        best_put['is_mock'] = True
                
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
                available_cash = portfolio_data.get('available_cash', 0)
                
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
                        'earnings': call_earnings,
                        'is_mock': best_call.get('is_mock', False) if best_call else True
                    },
                    'put': {
                        'strike': float(best_put.get('strike', 0)) if best_put else 0,
                        'bid': float(best_put.get('bid', 0)) if best_put else 0,
                        'ask': float(best_put.get('ask', 0)) if best_put else 0,
                        'delta': float(best_put.get('delta', 0)) if best_put else 0,
                        'earnings': put_earnings,
                        'is_mock': best_put.get('is_mock', False) if best_put else True
                    }
                }
                
                result['data'][ticker] = ticker_result
                
            except Exception as e:
                if is_market_open:
                    logger.error(f"Error processing {ticker} during market hours: {str(e)}")
                    raise
                else:
                    logger.info(f"Error processing {ticker} during closed market: {str(e)}")
                    continue
        
        elapsed_time = time.time() - start_time
        logger.info(f"Completed delta-targeted options request in {elapsed_time:.2f} seconds")
        return result

    def _generate_mock_option_chain(self, ticker, current_price, expiration):
        """Helper method to generate a complete mock option chain"""
        # Generate strikes around current price
        base_strike = self._adjust_to_standard_strike(current_price)
        
        if current_price < 25:
            increment = 1.0
            num_strikes = 10
        elif current_price < 100:
            increment = 2.5
            num_strikes = 15
        elif current_price < 250:
            increment = 5.0
            num_strikes = 20
        else:
            increment = 10.0
            num_strikes = 25
        
        strikes = []
        for i in range(-(num_strikes//2), (num_strikes//2) + 1):
            strike = round(base_strike + (i * increment), 2)
            if strike > 0:  # Ensure positive strikes
                strikes.append(strike)
        
        # Generate calls and puts with greeks
        calls = []
        puts = []
        
        for strike in strikes:
            # Call delta decreases as strike increases (from ~1.0 ATM to ~0.0 far OTM)
            call_delta = max(0.01, min(0.99, 0.5 - (strike - current_price) / (current_price * 0.2)))
            # Put delta increases as strike decreases (from ~-1.0 ATM to ~0.0 far OTM)
            put_delta = max(-0.99, min(-0.01, -0.5 + (strike - current_price) / (current_price * 0.2)))
            
            # Generate call data
            call_data = self._generate_mock_option_data(ticker, expiration, 'C', strike)
            call_data['delta'] = round(call_delta, 3)
            calls.append(call_data)
            
            # Generate put data
            put_data = self._generate_mock_option_data(ticker, expiration, 'P', strike)
            put_data['delta'] = round(put_delta, 3)
            puts.append(put_data)
        
        return {
            'calls': calls,
            'puts': puts
        } 