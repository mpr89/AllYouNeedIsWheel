"""
Stock and Options Trading Connection Module for Interactive Brokers
"""

import logging
import asyncio
import math
import time
import os
import json
import threading
import traceback
from typing import Optional, Dict, Any
from datetime import datetime, time as datetime_time
import pytz

# Import ib_insync
from ib_insync import IB, Stock, Option, Contract, util

# Import our logging configuration
from core.logging_config import get_logger

# Configure logging
logger = get_logger('autotrader.connection', 'tws')

# Set ib_insync logger to WARNING level to reduce noise
def suppress_ib_logs():
    """
    Suppress verbose logs from the ib_insync library by setting higher log levels
    """
    # Base ib_insync loggers
    logging.getLogger('ib_insync').setLevel(logging.WARNING)
    logging.getLogger('ib_insync.wrapper').setLevel(logging.WARNING)
    logging.getLogger('ib_insync.client').setLevel(logging.WARNING)
    logging.getLogger('ib_insync.ticker').setLevel(logging.WARNING)
    
    # Additional ib_insync logger components
    logging.getLogger('ib_insync.event').setLevel(logging.WARNING)
    logging.getLogger('ib_insync.util').setLevel(logging.WARNING)
    logging.getLogger('ib_insync.objects').setLevel(logging.WARNING)
    logging.getLogger('ib_insync.contract').setLevel(logging.WARNING)
    logging.getLogger('ib_insync.order').setLevel(logging.WARNING)
    logging.getLogger('ib_insync.ib').setLevel(logging.WARNING)
    
    # Suppress related lower-level modules used by ib_insync
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('eventkit').setLevel(logging.WARNING)
    
# Call to suppress IB logs
suppress_ib_logs()


class IBConnection:
    """
    Class for managing connection to Interactive Brokers
    """
    def __init__(self, host='127.0.0.1', port=7497, client_id=1, timeout=20, readonly=True):
        """
        Initialize the IB connection
        
        Args:
            host (str): TWS/IB Gateway host (default: 127.0.0.1)
            port (int): TWS/IB Gateway port (default: 7497 for paper trading, 7496 for live)
            client_id (int): Client ID for TWS/IB Gateway
            timeout (int): Connection timeout in seconds
            readonly (bool): Whether to connect in readonly mode
        """
        self.host = host
        self.port = port
        self.client_id = client_id
        self.timeout = timeout
        self.readonly = False
        self.ib = IB()
        self._connected = False
        
        # Suppress ib_insync logs when initializing
        suppress_ib_logs()
    
    def _ensure_event_loop(self):
        """
        Ensure that an event loop exists for the current thread
        """
        try:
            # Check if an event loop exists and is running
            loop = asyncio.get_event_loop()
            if not loop.is_running():
                pass  # Loop exists but not running, which is fine
        except RuntimeError:
            # No event loop exists in this thread, create one
            logger.debug("Creating new event loop for thread")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return True
    
    def connect(self):
        """
        Connect to TWS/IB Gateway
        
        Returns:
            bool: True if successful, False otherwise
        """
        # Suppress logs during connection attempt
        suppress_ib_logs()
        
        try:
            if self._connected and self.ib.isConnected():
                logger.info(f"Already connected to IB")
                return True
            
            logger.info(f"Connecting to IB at {self.host}:{self.port} with client ID {self.client_id}")
            
            # Ensure event loop exists
            self._ensure_event_loop()
            
            # Set read-only mode if requested
            if self.readonly:
                self.ib.clientId = self.client_id
                self.ib.connect(self.host, self.port, clientId=self.client_id, readonly=True, timeout=self.timeout)
            else:
                self.ib.clientId = self.client_id
                self.ib.connect(self.host, self.port, clientId=self.client_id, readonly=False, timeout=self.timeout)
            
            self._connected = self.ib.isConnected()
            if self._connected:
                logger.info(f"Successfully connected to IB with client ID {self.client_id}")
                return True
            else:
                logger.error(f"Failed to connect to IB with client ID {self.client_id}")
                return False
        except Exception as e:
            error_msg = str(e)
            if "clientId" in error_msg and "already in use" in error_msg:
                logger.error(f"Connection error: Client ID {self.client_id} is already in use by another application.")
                logger.error("Please try using a different client ID, or close other applications connected to TWS/IB Gateway.")
            elif "There is no current event loop" in error_msg:
                logger.error("Asyncio event loop error detected. This may be due to threading issues.")
                logger.error("Please try running your code in the main thread or configuring asyncio properly.")
            else:
                logger.error(f"Error connecting to IB: {error_msg}")
                # Log more detailed error information for debugging
                logger.error(f"Connection details: host={self.host}, port={self.port}, clientId={self.client_id}, readonly={self.readonly}")
                logger.debug(traceback.format_exc())
            
            self._connected = False
            return False
    
    def disconnect(self):
        """
        Disconnect from Interactive Brokers
        """
        if self._connected:
            self.ib.disconnect()
            self._connected = False
            logger.info("Disconnected from IB")
    
    def is_connected(self):
        """
        Check if connected to Interactive Brokers
        
        Returns:
            bool: True if connected, False otherwise
        """
        return self._connected and self.ib.isConnected()
    
    def get_stock_price(self, symbol):
        """
        Get the current price of a stock
        
        Args:
            symbol (str): Stock symbol
            
        Returns:
            float: Current stock price or None if error
        """
        if not self.is_connected():
            logger.warning("Not connected to IB. Attempting to connect...")
            if not self.connect():
                return None
        
        try:
            # Ensure event loop exists for this thread
            self._ensure_event_loop()
            
            # Create a stock contract
            contract = Contract(symbol=symbol, secType='STK', exchange='SMART', currency='USD')
            
            # Qualify the contract
            qualified_contracts = self.ib.qualifyContracts(contract)
            if not qualified_contracts:
                logger.error(f"Failed to qualify contract for {symbol}")
                return None
            
            qualified_contract = qualified_contracts[0]
            
            # Request market data
            ticker = self.ib.reqMktData(qualified_contract)
            
            # Wait for market data to be received
            self.ib.sleep(0.2)
            
            # Get the last price
            last_price = ticker.last if ticker.last else (ticker.close if ticker.close else None)
            bid_price = ticker.bid if ticker.bid else None
            ask_price = ticker.ask if ticker.ask else None
            last_rth_trade = ticker.lastRTHTrade.price if hasattr(ticker, 'lastRTHTrade') and ticker.lastRTHTrade else None
            
            # If no last price is available, check other prices
            if last_price is None:
                if bid_price and ask_price:
                    # Use midpoint of bid-ask spread
                    last_price = (bid_price + ask_price) / 2
                elif bid_price:
                    last_price = bid_price
                elif ask_price:
                    last_price = ask_price
                elif last_rth_trade:
                    last_price = last_rth_trade
            
            # Cancel the market data subscription
            self.ib.cancelMktData(qualified_contract)
            
            if last_price is None:
                logger.error(f"Could not get price for {symbol}")
                return None
                
            return last_price
            
        except Exception as e:
            error_msg = str(e)
            if "There is no current event loop" in error_msg:
                logger.error("Asyncio event loop error in get_stock_price. Retrying with new event loop.")
                # Try one more time with a fresh event loop
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    return self.get_stock_price(symbol)
                except Exception as retry_error:
                    logger.error(f"Failed to get stock price after event loop retry: {str(retry_error)}")
                    return None
            else:
                logger.error(f"Error getting {symbol} price: {error_msg}")
            return None
            
    def get_multiple_stock_prices(self, tickers):
        """
        Get multiple stock prices in one batch request
        
        Args:
            tickers (list): List of ticker symbols
            
        Returns:
            dict: Dictionary of stock prices by ticker
        """
        if not self._ensure_connected():
            logger.error("Not connected to TWS")
            return {}
        
        result = {}
        
        try:
            for ticker in tickers:
                try:
                    stock = Stock(ticker, 'SMART', 'USD')
                    self.ib.qualifyContracts(stock)
                    self.ib.reqMarketDataType(1)  # 1 = Live data
                    ticker_data = self.ib.reqMktData(stock)
                    # Wait for data to arrive
                    self.ib.sleep(0.2)
                    # Use last or close price
                    price = ticker_data.last if ticker_data.last > 0 else ticker_data.close
                    result[ticker] = price
                except Exception as e:
                        logger.error(f"Error getting real-time price for {ticker}: {str(e)}")
            # Cancel all market data requests
            self.ib.cancelMktData()
            
            return result
        except Exception as e:
            logger.error(f"Error getting multiple stock prices: {str(e)}")
            return {}
    
    def get_option_chain(self, symbol, expiration=None, right='C', target_strike=None, exchange='SMART'):
        """
        Get option chain data for a stock, filtered to a specific expiration date and closest strike price
        
        Args:
            symbol (str): Stock symbol
            expiration (str): Target expiration date in YYYYMMDD format
            right (str): Option right ('C' for call, 'P' for put)
            target_strike (float, optional): Target strike price. If provided, returns only the option with the closest strike.
            exchange (str): Exchange
            
        Returns:
            dict: Dictionary with option chain data including market data
        """
        if not self.is_connected():
            logger.warning("Not connected to IB. Attempting to connect...")
            if not self.connect():
                return None
            
        # Get stock contract and price
        stock = Stock(symbol, exchange, 'USD')
        
        try:
            # Qualify the stock contract
            qualified_stocks = self.ib.qualifyContracts(stock)
            if not qualified_stocks:
                logger.error(f"Could not qualify stock contract for {symbol}")
                return None
            
            stock_contract = qualified_stocks[0]
            
            # Get current stock price for reference
            ticker = self.ib.reqMktData(stock_contract)
            self.ib.sleep(0.2)  # Wait for data to arrive
            stock_price = ticker.last if hasattr(ticker, 'last') and ticker.last > 0 else ticker.close
            self.ib.cancelMktData(stock_contract)
            
            logger.info(f"Current price for {symbol}: ${stock_price}")
            
            # Request option chain
            chains = self.ib.reqSecDefOptParams(stock_contract.symbol, '', stock_contract.secType, stock_contract.conId)
            
            if not chains:
                logger.error(f"No option chain found for {symbol}")
                return None
            
            chain = next((c for c in chains if c.exchange == exchange), None)
            if not chain:
                logger.error(f"No option chain found for {symbol} on exchange {exchange}")
                return None
            
            # Filter available expirations if a specific one is requested
            available_expirations = chain.expirations
            if expiration:
                if expiration in available_expirations:
                    logger.info(f"Using requested expiration date: {expiration}")
                    expirations = [expiration]
                else:
                    logger.warning(f"Requested expiration {expiration} not found in available expirations: {available_expirations}")
                    # Find the closest expiration date if the requested one is not available
                    if available_expirations:
                        try:
                            from datetime import datetime
                            # Parse the requested expiration
                            requested_date = datetime.strptime(expiration, '%Y%m%d')
                            # Parse all available expirations
                            exp_dates = [(exp, datetime.strptime(exp, '%Y%m%d')) for exp in available_expirations]
                            # Find the closest expiration date
                            closest_exp = min(exp_dates, key=lambda x: abs((x[1] - requested_date).days))
                            logger.info(f"Using closest available expiration: {closest_exp[0]} (instead of {expiration})")
                            expirations = [closest_exp[0]]
                        except Exception as e:
                            logger.error(f"Error finding closest expiration: {e}")
                            expirations = [available_expirations[0]]
                    else:
                        logger.error(f"No expirations available for {symbol}")
                        return None
            else:
                # If no expiration provided, use the first available one
                if available_expirations:
                    expirations = [available_expirations[0]]
                    logger.info(f"No expiration specified, using first available: {expirations[0]}")
                else:
                    logger.error(f"No expirations available for {symbol}")
                    return None
            
            strikes = chain.strikes
            
            # If target_strike is provided, find the closest strike
            if target_strike is not None and strikes:
                logger.info(f"Finding strike closest to {target_strike} for {symbol}")
                closest_strike = min(strikes, key=lambda s: abs(s - target_strike))
                logger.info(f"Selected strike {closest_strike} (from {len(strikes)} available strikes)")
                strikes = [closest_strike]
            
            # Build option contracts
            option_contracts = []
            for exp in expirations:
                for strike in strikes:
                    option = Option(symbol, exp, strike, right, exchange)
                    option.currency = 'USD'
                    option.multiplier = '100'  # Standard for equity options
                    option_contracts.append(option)
            
            # Get market data for the options
            logger.info(f"Requesting market data for {len(option_contracts)} option contracts")
            
            # Initialize result structure
            result = {
                'symbol': symbol,
                'expiration': expirations[0],  # Just use the first one since we're filtering
                'stock_price': stock_price,
                'right': right,
                'options': []
            }
            
            self.ib.reqMarketDataType(1)
            
            # Qualify and request market data for each option
            for contract in option_contracts:
                try:
                    # Qualify the contract
                    qualified_contracts = self.ib.qualifyContracts(contract)
                    if not qualified_contracts:
                        logger.warning(f"Could not qualify option contract: {contract.symbol} {contract.lastTradeDateOrContractMonth} {contract.strike} {contract.right}")
                        continue
                    
                    qualified_contract = qualified_contracts[0]
                    
                    # Request market data with model computation
                    ticker = self.ib.reqMktData(qualified_contract, '', True, False)  # Add genericTickList='Greeks' to get Greeks
                    
                    # Wait for data to arrive - give more time for Greeks
                    wait_time = 20
                    for _ in range(wait_time):
                        self.ib.sleep(0.1)
                        # Check if we have model greeks data
                        if hasattr(ticker, 'modelGreeks') and ticker.modelGreeks:
                            break
                    
                    # Extract market data
                    bid = ticker.bid if hasattr(ticker, 'bid') and ticker.bid is not None and ticker.bid > 0 else 0
                    ask = ticker.ask if hasattr(ticker, 'ask') and ticker.ask is not None and ticker.ask > 0 else 0
                    last = ticker.last if hasattr(ticker, 'last') and ticker.last is not None and ticker.last > 0 else 0
                    volume = ticker.volume if hasattr(ticker, 'volume') and ticker.volume is not None else 0
                    open_interest = ticker.openInterest if hasattr(ticker, 'openInterest') and ticker.openInterest is not None else 0
                    implied_vol = ticker.impliedVolatility if hasattr(ticker, 'impliedVolatility') and ticker.impliedVolatility is not None else 0
                    
                    # Get real delta from model greeks if available
                    delta = None
                    gamma = None
                    theta = None
                    vega = None
                    
                    if hasattr(ticker, 'modelGreeks') and ticker.modelGreeks:
                        delta = ticker.modelGreeks.delta if hasattr(ticker.modelGreeks, 'delta') else None
                        gamma = ticker.modelGreeks.gamma if hasattr(ticker.modelGreeks, 'gamma') else None
                        theta = ticker.modelGreeks.theta if hasattr(ticker.modelGreeks, 'theta') else None
                        vega = ticker.modelGreeks.vega if hasattr(ticker.modelGreeks, 'vega') else None
                        
                        logger.debug(f"Got real greeks for {contract.symbol} {contract.right} {contract.strike}: delta={delta}, gamma={gamma}, theta={theta}, vega={vega}")
                    else:
                        logger.debug(f"No model greeks available for {contract.symbol} {contract.right} {contract.strike}")
                        
                        # Fall back to estimate for delta if not available from TWS
                        atm_factor = 1.0 - min(1.0, abs(stock_price - contract.strike) / stock_price)
                        
                        if contract.right == 'C':
                            if contract.strike < stock_price:
                                delta = 0.5 + (0.5 * atm_factor)
                            else:
                                delta = 0.5 * (1 - atm_factor)
                        else:  # Put
                            if contract.strike > stock_price:
                                delta = -0.5 - (0.5 * atm_factor)
                            else:
                                delta = -0.5 * (1 - atm_factor)
                        
                        logger.debug(f"Using estimated delta for {contract.symbol} {contract.right} {contract.strike}: delta={delta}")
                    
                    # Create option data dictionary
                    option_data = {
                        'strike': contract.strike,
                        'expiration': contract.lastTradeDateOrContractMonth,
                        'option_type': 'CALL' if contract.right == 'C' else 'PUT',
                        'bid': bid,
                        'ask': ask,
                        'last': last,
                        'volume': volume,
                        'open_interest': open_interest,
                        'implied_volatility': implied_vol,
                        'delta': round(delta, 3) if delta is not None else None,
                        'gamma': round(gamma, 5) if gamma is not None else None,
                        'theta': round(theta, 5) if theta is not None else None,
                        'vega': round(vega, 5) if vega is not None else None
                    }
                    
                    # Add to the result
                    result['options'].append(option_data)
                    
                    # Cancel market data request
                    self.ib.cancelMktData(qualified_contract)
        
                except Exception as e:
                    logger.error(f"Error getting market data for option {contract.symbol} {contract.lastTradeDateOrContractMonth} {contract.strike} {contract.right}: {e}")
                    logger.error(traceback.format_exc())
            
            # Sort options by strike price
            result['options'] = sorted(result['options'], key=lambda x: x['strike'])
            
            return result
        except Exception as e:
            logger.error(f"Error retrieving option chain for {symbol}: {e}")
            logger.error(traceback.format_exc())
            return None
            
    def get_option_price(self, contract):
        """
        Get the price data for an option contract
        
        Args:
            contract (Contract): IB option contract
            
        Returns:
            dict: Dictionary with bid, ask, and last prices
        """
        try:
            # Make sure contract has the exchange set to SMART
            if not contract.exchange or contract.exchange != 'SMART':
                contract.exchange = 'SMART'
            
            # Try to qualify the contract first
            try:
                qualified_contracts = self.ib.qualifyContracts(contract)
                if not qualified_contracts:
                    logger.error(f"Could not qualify contract: {contract.symbol} {contract.lastTradeDateOrContractMonth} {contract.strike} {contract.right}")
                    return None
                
                qualified_contract = qualified_contracts[0]
            except Exception as e:
                # If we get an ambiguous contract error, try to handle it
                error_msg = str(e)
                if "ambiguous" in error_msg.lower():
                    logger.warning(f"Ambiguous contract: {contract.symbol} {contract.lastTradeDateOrContractMonth} {contract.strike} {contract.right}")
                    
                    # Try to create a more specific contract
                    try:
                        from ib_insync import Contract
                        # Create a full contract specification with conId if possible
                        detailed_contract = Contract(
                            secType='OPT',
                            symbol=contract.symbol,
                            lastTradeDateOrContractMonth=contract.lastTradeDateOrContractMonth,
                            strike=contract.strike,
                            right=contract.right,
                            multiplier='100',  # Standard for equity options
                            exchange='SMART',
                            currency='USD'
                        )
                        
                        # Try again with the detailed contract
                        qualified_contracts = self.ib.qualifyContracts(detailed_contract)
                        if qualified_contracts:
                            qualified_contract = qualified_contracts[0]
                        else:
                            logger.error(f"Still could not qualify contract after retry: {contract.symbol} {contract.lastTradeDateOrContractMonth} {contract.strike} {contract.right}")
                            return None
                    except Exception as inner_e:
                        logger.error(f"Error handling ambiguous contract: {inner_e}")
                        return None
                else:
                    logger.error(f"Error qualifying contract: {e}")
                    return None
            
            # Request market data
            ticker = self.ib.reqMktData(qualified_contract)
            
            # Wait for market data to arrive (up to 5 seconds)
            max_wait = 20  # 2seconds
            logger.debug(f"Waiting up to {max_wait} seconds for option market data...")
            
            for i in range(max_wait):
                self.ib.sleep(0.1)
                # Log data for debugging purposes
                logger.debug(f"Option data wait ({i+1}/{max_wait}): "
                             f"bid={ticker.bid if hasattr(ticker, 'bid') else None}, "
                             f"ask={ticker.ask if hasattr(ticker, 'ask') else None}, "
                             f"last={ticker.last if hasattr(ticker, 'last') else None}")
                
                # Check if we have received any meaningful data
                if (hasattr(ticker, 'bid') and ticker.bid is not None and ticker.bid > 0) or \
                   (hasattr(ticker, 'ask') and ticker.ask is not None and ticker.ask > 0) or \
                   (hasattr(ticker, 'last') and ticker.last is not None and ticker.last > 0):
                    break
            
            # Get price data
            bid = ticker.bid if hasattr(ticker, 'bid') and ticker.bid is not None and ticker.bid > 0 else None
            ask = ticker.ask if hasattr(ticker, 'ask') and ticker.ask is not None and ticker.ask > 0 else None
            last = ticker.last if hasattr(ticker, 'last') and ticker.last is not None and ticker.last > 0 else None
            
            # Log a warning if we didn't get any price data
            if bid is None and ask is None and last is None:
                logger.warning(f"No price data available for {contract.symbol} {contract.right} {contract.strike} {contract.lastTradeDateOrContractMonth}")
            
            # Cancel market data subscription
            self.ib.cancelMktData(qualified_contract)
            
            return {
                'bid': bid,
                'ask': ask,
                'last': last
            }
        except Exception as e:
            logger.error(f"Error getting option price: {e}")
            return None
   
    def get_portfolio(self):
        """
        Get current portfolio positions and account information from IB
        
        Returns:
            dict: Dictionary containing account information and positions
            
        Raises:
            ConnectionError: If connection fails during market hours
            ValueError: If no data available during market hours
        """
        is_market_open = self._is_market_hours()
        
        if not self.is_connected():
            if is_market_open:
                logger.error("Not connected to IB during market hours")
                raise ConnectionError("Not connected to IB during market hours")
            else:
                logger.info("Market is closed. Using mock portfolio data.")
                return self._generate_mock_portfolio()
        
        try:
            # Get account summary
            account_id = self.ib.managedAccounts()[0]
            account_values = self.ib.accountSummary(account_id)
            
            if not account_values:
                if is_market_open:
                    raise ValueError("No account data available during market hours")
                else:
                    logger.info("No account data during closed market. Using mock portfolio data.")
                    return self._generate_mock_portfolio()
            
            # Extract relevant account information
            account_info = {
                'account_id': account_id,
                'available_cash': 0,
                'account_value': 0
            }
            
            for av in account_values:
                if av.tag == 'TotalCashValue':
                    account_info['available_cash'] = float(av.value)
                elif av.tag == 'NetLiquidation':
                    account_info['account_value'] = float(av.value)
            
            # Get positions
            portfolio = self.ib.portfolio()
            positions = {}
            
            for position in portfolio:
                symbol = position.contract.symbol
                market_price = position.marketPrice
                
                positions[symbol] = {
                    'shares': position.position,
                    'avg_cost': position.averageCost,
                    'market_price': market_price,
                    'market_value': position.marketValue,
                    'unrealized_pnl': position.unrealizedPNL,
                    'realized_pnl': position.realizedPNL,
                    'contract': position.contract
                }
            
            if not positions:
                if is_market_open:
                    raise ValueError("No position data available during market hours")
                else:
                    logger.info("No positions found during closed market. Using mock portfolio data.")
                    return self._generate_mock_portfolio()
            
            return {
                'account_id': account_id,
                'available_cash': account_info.get('available_cash', 0),
                'account_value': account_info.get('account_value', 0),
            'positions': positions,
            'is_mock': False
        }
        
        except Exception as e:
            if is_market_open:
                logger.error(f"Error getting portfolio during market hours: {str(e)}")
                raise
            else:
                logger.info(f"Error getting portfolio during closed market. Using mock portfolio data.")
                return self._generate_mock_portfolio()
          
    def _generate_mock_stock_data(self, symbol):
        """
        Generate mock stock data when real and historical data are unavailable
        
        Args:
            symbol (str): Stock symbol
            
        Returns:
            dict: Mock stock data
        """
        import random
        from datetime import datetime
        
        # Special case for NVDA
        if symbol.upper() == 'NVDA':
            # Use a realistic price for NVDA (around $900 - will be a fixed reference point)
            price = 905.75
            volume = 32457890  # Realistic volume
            
            logger.warning(f"Using MOCK DATA for NVIDIA stock - real and historical data unavailable")
            
            return {
                'symbol': 'NVDA',
                'last': price,
                'bid': price * 0.998,  # $904.00
                'ask': price * 1.002,  # $907.50
                'high': price * 1.02,   # $923.87
                'low': price * 0.985,   # $892.16
                'close': price,
                'open': price * 0.99,   # $896.69
                'volume': volume,
                'halted': False,
                'timestamp': datetime.now().isoformat(),
                'is_mock': True
            }
        else:
            # Generate random stock price between $10-$500 for other stocks
            price = random.uniform(10, 500)
            
            # Generate random volume
            volume = random.randint(10000, 1000000)
            
            logger.warning(f"Using MOCK DATA for stock {symbol} - real and historical data unavailable")
            
            return {
                'symbol': symbol,
                'last': price,
                'bid': price * 0.995,  # 0.5% less than last
                'ask': price * 1.005,  # 0.5% more than last
                'high': price * 1.03,  # 3% above last
                'low': price * 0.97,   # 3% below last
                'close': price,
                'open': price * 0.99,  # Slightly below close
                'volume': volume,
                'halted': False,
                'timestamp': datetime.now().isoformat(),
                'is_mock': True
            }

    def _generate_mock_option_data(self, symbol, expiration, right, strike):
        """
        Generate mock option data when real and historical data are unavailable
        
        Args:
            symbol (str): Stock symbol
            expiration (str): Option expiration date in format YYYYMMDD
            right (str): Option right ('C' for call, 'P' for put)
            strike (float): Strike price
            
        Returns:
            dict: Mock option data
        """
        import random
        from datetime import datetime
        
        # Special case for NVDA
        if symbol.upper() == 'NVDA':
            # Use our fixed NVDA mock price
            underlying = 905.75
            
            # Calculate days to expiry
            days_to_expiry = (datetime.strptime(expiration, '%Y%m%d') - datetime.now()).days
            if days_to_expiry < 0:
                days_to_expiry = 30  # Default to 30 days if expiry is in the past
            
            # Calculate a more realistic option price based on strike and right
            if right == 'C':
                # For calls, intrinsic value is underlying - strike (if positive)
                intrinsic = max(0, underlying - strike)
                # Time value decreases as strike increases (for OTM options)
                if strike > underlying:
                    # Out-of-the-money call
                    distance_factor = max(0, 1 - (strike - underlying) / (underlying * 0.2))
                    time_value = underlying * 0.05 * distance_factor * (days_to_expiry / 30)
                else:
                    # In-the-money call
                    time_value = underlying * 0.03 * (days_to_expiry / 30)
            else:
                # For puts, intrinsic value is strike - underlying (if positive)
                intrinsic = max(0, strike - underlying)
                # Time value decreases as strike decreases (for OTM options)
                if strike < underlying:
                    # Out-of-the-money put
                    distance_factor = max(0, 1 - (underlying - strike) / (underlying * 0.2))
                    time_value = underlying * 0.05 * distance_factor * (days_to_expiry / 30)
                else:
                    # In-the-money put
                    time_value = underlying * 0.03 * (days_to_expiry / 30)
            
            option_price = max(0.05, intrinsic + time_value)
            
            # Calculate implied volatility (higher for further expiries and strikes near the money)
            atm_factor = 1 - min(1, abs(strike - underlying) / (underlying * 0.2))
            implied_vol = 0.3 + (0.2 * atm_factor) + (0.1 * (days_to_expiry / 180))
            implied_vol = min(0.9, max(0.15, implied_vol))
            
            # Generate volume (higher for strikes near the money)
            volume_base = 2000 * atm_factor
            volume = int(max(10, volume_base * random.uniform(0.7, 1.3)))
            
            # Calculate Greeks
            if right == 'C':
                if strike == underlying:
                    delta = 0.5
                elif underlying > strike:  # ITM call
                    delta = 0.5 + (0.5 * (1 - (strike / underlying)))
                    delta = min(0.95, delta)
                else:  # OTM call
                    delta = 0.5 - (0.5 * (1 - (underlying / strike)))
                    delta = max(0.05, delta)
            else:  # Put
                if strike == underlying:
                    delta = -0.5
                elif underlying > strike:  # OTM put
                    delta = -0.5 + (0.5 * (1 - (strike / underlying)))
                    delta = max(-0.95, delta)
                else:  # ITM put
                    delta = -0.5 - (0.5 * (1 - (underlying / strike)))
                    delta = min(-0.05, delta)
            
            # Other Greeks based on delta
            gamma = 0.08 * (1 - abs(delta * 2 - 1))  # Highest when ATM
            theta = -option_price * (0.01 + 0.02 * (1 - abs(delta * 2 - 1)))  # Higher decay near ATM
            vega = option_price * 0.1 * (1 - abs(delta * 2 - 1))  # Highest when ATM
            
            logger.warning(f"Using MOCK DATA for NVIDIA option {expiration} {strike} {right} - real data unavailable")
        else:
            # Use existing logic for other stocks
            try:
                stock_data = self.get_stock_data(symbol)
                if stock_data and 'last' in stock_data:
                    underlying = stock_data['last']
                else:
                    underlying = random.uniform(10, 500)
            except:
                underlying = random.uniform(10, 500)
                
            # Calculate a reasonable option price based on strike and right
            if right == 'C':
                intrinsic = max(0, underlying - strike)
            else:
                intrinsic = max(0, strike - underlying)
                
            # Add time value (more for longer dated options)
            days_to_expiry = (datetime.strptime(expiration, '%Y%m%d') - datetime.now()).days
            if days_to_expiry < 0:
                days_to_expiry = 30
            
            time_value = underlying * 0.01 * (days_to_expiry / 30)
            
            option_price = max(0.05, intrinsic + time_value)
            
            # Generate random volume
            volume = random.randint(10, 1000)
            
            # Generate random implied volatility
            implied_vol = random.uniform(0.2, 0.8)
            
            # Calculate simple Greeks
            if strike == underlying:
                delta = 0.5 if right == 'C' else -0.5
            elif (underlying > strike and right == 'C') or (underlying < strike and right == 'P'):
                delta = 0.7 if right == 'C' else -0.7
            else:
                delta = 0.3 if right == 'C' else -0.3
            
            gamma = 0.05
            theta = -option_price * 0.01
            vega = option_price * 0.1
            
            logger.warning(f"Using MOCK DATA for option {symbol} {expiration} {strike} {right} - real data unavailable")
            
        return {
            'symbol': symbol,
            'expiration': expiration,
            'strike': strike,
            'right': right,
            'bid': option_price * 0.95,
            'ask': option_price * 1.05,
            'last': option_price,
            'volume': volume,
            'open_interest': volume * 2,
            'underlying': underlying,
            'delta': delta,
            'gamma': gamma,
            'theta': theta,
            'vega': vega,
            'implied_vol': implied_vol,
            'is_mock': True,
            'timestamp': datetime.now().isoformat()
        }

    def _generate_mock_portfolio(self):
        """
        Generate a mock portfolio with NVDA position and $1M cash
        
        Returns:
            dict: Mock portfolio data
        """
        # Use our NVDA mock price
        nvda_price = 905.75
        nvda_position = 5000
        nvda_value = nvda_price * nvda_position
        
        # Create mock account data
        account_id = "U1234567"  # Mock account number
        total_cash = 1000000.00  # $1M cash as requested
        total_value = total_cash + nvda_value
        
        # Create a contract for NVDA position
        from ib_insync import Contract
        nvda_contract = Contract(
            symbol="NVDA",
            secType="STK",
            exchange="SMART",
            currency="USD"
        )
        
        # Create the portfolio object
        positions = {
            "NVDA": {
                'shares': nvda_position,
                'avg_cost': nvda_price * 0.8,  # Assume we bought it 20% cheaper
                'market_price': nvda_price,
                'market_value': nvda_value,
                'unrealized_pnl': nvda_value - (nvda_price * 0.8 * nvda_position),
                'realized_pnl': 0,
                'contract': nvda_contract
            }
        }
        
        logger.warning("Using MOCK PORTFOLIO DATA - showing 5000 NVDA shares and $1M cash")
        
        return {
            'account_id': account_id,
            'available_cash': total_cash,
            'account_value': total_value,
            'positions': positions,
            'is_mock': True
        }

    def _is_market_hours(self):
        """
        Check if it's currently market hours (9:30 AM to 4:00 PM ET, Monday to Friday).
        Returns: True if it's market hours, False otherwise.
        """
        # Get the current time in ET
        eastern = pytz.timezone('US/Eastern')
        now = datetime.now(eastern)
        
        # Check if it's a weekend
        if now.weekday() >= 5:  # 5 is Saturday, 6 is Sunday
            return False
        
        # Check if it's before market open or after market close
        market_open = datetime_time(9, 30)
        market_close = datetime_time(16, 0)
        
        current_time = now.time()
        return market_open <= current_time <= market_close

    def get_stock_data(self, symbol):
        """
        Get comprehensive stock data including price, volume, and other metrics
        
        Args:
            symbol (str): Stock symbol
            
        Returns:
            dict: Dictionary with stock data or None if error
            
        Raises:
            ConnectionError: If connection fails during market hours
            ValueError: If no data available during market hours
        """
        is_market_open = self._is_market_hours()
        
        if not self.is_connected():
            if is_market_open:
                logger.error("Not connected to IB during market hours")
                raise ConnectionError("Not connected to IB during market hours")
            else:
                logger.info("Market is closed. Using mock data.")
                return self._generate_mock_stock_data(symbol)
        
        try:
            # Ensure event loop exists for this thread
            self._ensure_event_loop()
            
            # Create contract for the stock
            contract = Stock(symbol, 'SMART', 'USD')
            
            # Try to get ticker data
            tickers = self.ib.reqTickers(contract)
            
            if not tickers:
                if is_market_open:
                    raise ValueError(f"No ticker data available for {symbol} during market hours")
                else:
                    logger.info(f"No ticker data for {symbol} during closed market. Using mock data.")
                    return self._generate_mock_stock_data(symbol)
            
            # Get the latest ticker data
            ticker_data = tickers[0]
            
            # Extract relevant data from the ticker
            last_price = ticker_data.last if ticker_data.last else ticker_data.close
            bid_price = ticker_data.bid if ticker_data.bid else ticker_data.close
            ask_price = ticker_data.ask if ticker_data.ask else ticker_data.close
            volume = ticker_data.volume if ticker_data.volume else 0
            high = ticker_data.high if ticker_data.high else last_price
            low = ticker_data.low if ticker_data.low else last_price
            open_price = ticker_data.open if ticker_data.open else last_price
            close_price = ticker_data.close if ticker_data.close else last_price
            
            # During market hours, we want real data only
            if is_market_open and (last_price is None or bid_price is None or ask_price is None):
                raise ValueError(f"Incomplete market data for {symbol} during market hours")
            
            # Build and return the result
            result = {
                'symbol': symbol,
                'last': last_price,
                'bid': bid_price,
                'ask': ask_price,
                'high': high,
                'low': low,
                'close': close_price,
                'open': open_price,
                'volume': volume,
                'halted': ticker_data.halted if hasattr(ticker_data, 'halted') else False,
                'timestamp': ticker_data.date.isoformat() if hasattr(ticker_data, 'date') else datetime.now().isoformat(),
                'is_historical': False,
                'is_mock': False
            }
            
            return result
        
        except Exception as e:
            if is_market_open:
                # During market hours, let errors propagate
                logger.error(f"Error getting stock data for {symbol} during market hours: {str(e)}")
                raise
            else:
                # Outside market hours, fall back to mock data
                logger.info(f"Error getting stock data for {symbol} during closed market. Using mock data.")
                return self._generate_mock_stock_data(symbol)
     
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

    def create_option_contract(self, symbol, expiry, strike, option_type, exchange='SMART', currency='USD'):
        """
        Create an option contract for TWS
        
        Args:
            symbol (str): Ticker symbol
            expiry (str): Expiration date in YYYYMMDD format
            strike (float): Strike price
            option_type (str): 'C', 'CALL', 'P', or 'PUT'
            exchange (str): Exchange name, default 'SMART'
            currency (str): Currency code, default 'USD'
            
        Returns:
            Option: Contract object ready for use with TWS
        """
        # Normalize option type to standard format
        if option_type.upper() in ['C', 'CALL']:
            right = 'C'
        elif option_type.upper() in ['P', 'PUT']:
            right = 'P'
        else:
            logger.error(f"Invalid option type: {option_type}")
            return None
            
        try:
            contract = Option(
                symbol=symbol, 
                lastTradeDateOrContractMonth=expiry,
                strike=float(strike),
                right=right,
                exchange=exchange,
                currency=currency
            )
            
            logger.info(f"Created option contract: {symbol} {expiry} {strike} {right}")
            return contract
        except Exception as e:
            logger.error(f"Error creating option contract: {str(e)}")
            logger.error(traceback.format_exc())
            return None
            
    def create_order(self, action, quantity, order_type='LMT', limit_price=None, tif='DAY'):
        """
        Create an order for TWS
        
        Args:
            action (str): 'BUY' or 'SELL'
            quantity (int): Number of contracts
            order_type (str): 'MKT', 'LMT', etc.
            limit_price (float): Price for limit orders
            tif (str): Time in force - 'DAY', 'GTC', etc.
            
        Returns:
            Order: Order object ready for use with TWS
        """
        from ib_insync import LimitOrder, MarketOrder
        
        try:
            if order_type.upper() == 'LMT':
                if limit_price is None:
                    logger.error("Limit price required for limit orders")
                    return None
                    
                order = LimitOrder(
                    action=action.upper(),
                    totalQuantity=quantity,
                    lmtPrice=limit_price,
                    tif=tif
                )
            elif order_type.upper() == 'MKT':
                order = MarketOrder(
                    action=action.upper(),
                    totalQuantity=quantity,
                    tif=tif
                )
            else:
                logger.error(f"Unsupported order type: {order_type}")
                return None
                
            logger.info(f"Created {order_type} order: {action} {quantity} contracts")
            return order
        except Exception as e:
            logger.error(f"Error creating order: {str(e)}")
            logger.error(traceback.format_exc())
            return None
            
    def place_order(self, contract, order):
        """
        Place an order with TWS
        
        Args:
            contract (Contract): Contract object (e.g., Option)
            order (Order): Order object
            
        Returns:
            dict: Order result with order_id and trade info
            None: If an error occurs
        """
        if not self.is_connected():
            logger.error("Cannot place order - not connected to TWS")
            return None
            
        try:
            # Check if we're in read-only mode
            if self.readonly:
                logger.warning("Cannot place order - connection in read-only mode")
                # Return mock data
                mock_order_id = int(time.time()) % 10000
                return {
                    'order_id': mock_order_id,
                    'status': 'submitted',
                    'filled': 0,
                    'remaining': order.totalQuantity,
                    'avg_fill_price': 0,
                    'perm_id': mock_order_id,
                    'last_fill_price': 0,
                    'client_id': self.client_id,
                    'why_held': '',
                    'market_cap': 0,
                    'is_mock': True
                }
                
            # Place the order
            trade = self.ib.placeOrder(contract, order)
            
            # Wait for order acknowledgment (order ID assigned)
            timeout = 3  # seconds
            start_time = time.time()
            while not trade.orderStatus.orderId and time.time() - start_time < timeout:
                self.ib.waitOnUpdate(timeout=0.1)
                
            # Get order status
            order_status = {
                'order_id': trade.orderStatus.orderId,
                'status': trade.orderStatus.status,
                'filled': trade.orderStatus.filled,
                'remaining': trade.orderStatus.remaining,
                'avg_fill_price': trade.orderStatus.avgFillPrice,
                'perm_id': trade.orderStatus.permId,
                'last_fill_price': trade.orderStatus.lastFillPrice,
                'client_id': trade.orderStatus.clientId,
                'why_held': trade.orderStatus.whyHeld,
                'market_cap': trade.orderStatus.mktCapPrice,
                'is_mock': False
            }
            
            logger.info(f"Order placed: {order_status}")
            return order_status
        except Exception as e:
            logger.error(f"Error placing order: {str(e)}")
            logger.error(traceback.format_exc())
            return None