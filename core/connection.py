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
from datetime import datetime, time
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
        self.readonly = readonly
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
            wait_time = 5  # seconds
            self.ib.sleep(wait_time)
            
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
            
    def get_multiple_stock_prices(self, symbols):
        """
        Get the current prices of multiple stocks in one batch
        
        Args:
            symbols (list): List of stock symbols
            
        Returns:
            dict: Dictionary mapping symbols to their current prices (None for failed retrievals)
        """
        if not self.is_connected():
            logger.warning("Not connected to IB. Attempting to connect...")
            if not self.connect():
                return {}
        
        results = {}
        qualified_contracts = []
        symbol_to_contract = {}
        
        # Step 1: Create and qualify all contracts
        for symbol in symbols:
            # Create a stock contract
            contract = Contract(symbol=symbol, secType='STK', exchange='SMART', currency='USD')
            
            try:
                # Qualify the contract
                qualified = self.ib.qualifyContracts(contract)
                if not qualified:
                    logger.error(f"Failed to qualify contract for {symbol}")
                    results[symbol] = None
                    continue
                
                qualified_contract = qualified[0]
                
                qualified_contracts.append(qualified_contract)
                symbol_to_contract[qualified_contract.symbol] = qualified_contract
                
            except Exception as e:
                logger.error(f"Error qualifying contract for {symbol}: {e}")
                results[symbol] = None
        
        # Step 2: Request market data for all qualified contracts
        if qualified_contracts:
            tickers = {}
            
            # Request market data for all contracts
            for contract in qualified_contracts:
                symbol = contract.symbol
                ticker = self.ib.reqMktData(contract)
                tickers[symbol] = ticker
            
            # Wait for market data to be received
            wait_time = 5  # seconds
            self.ib.sleep(wait_time)
            
            # Process the received data
            for symbol, ticker in tickers.items():
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
                
                results[symbol] = last_price
                
                # Cancel the market data subscription
                contract = symbol_to_contract.get(symbol)
                if contract:
                    self.ib.cancelMktData(contract)
        
        return results
    
    def get_option_chain(self, symbol, right='C', exchange='SMART'):
        """
        Get option chain for a stock
        
        Args:
            symbol (str): Stock symbol
            right (str): Option right ('C' for call, 'P' for put)
            exchange (str): Exchange
            
        Returns:
            list: List of option contracts
        """
        if not self.is_connected():
            logger.warning("Not connected to IB. Attempting to connect...")
            if not self.connect():
                return None
            
        # Get stock contract
        stock = Contract()
        stock.symbol = symbol
        stock.secType = 'STK'
        stock.exchange = exchange
        stock.currency = 'USD'
        
        try:
            self.ib.qualifyContracts(stock)
            
            # Request option chain
            chains = self.ib.reqSecDefOptParams(stock.symbol, '', stock.secType, stock.conId)
            
            if not chains:
                logger.error(f"No option chain found for {symbol}")
                return None
            
            chain = next((c for c in chains if c.exchange == exchange), None)
            if not chain:
                logger.error(f"No option chain found for {symbol} on exchange {exchange}")
                return None
            
            expirations = chain.expirations
            strikes = chain.strikes
            
            # Build option contracts
            options = []
            for expiration in expirations:
                for strike in strikes:
                    option = Option(symbol, expiration, strike, right, exchange)
                    option.currency = 'USD'
                    option.multiplier = '100'  # Standard for equity options
                    options.append(option)
            
            return options
        except Exception as e:
            logger.error(f"Error retrieving option chain for {symbol}: {e}")
            return None
    
    def get_available_expirations(self, symbol, exchange='SMART'):
        """
        Get available option expirations for a symbol
        
        Args:
            symbol (str): Stock symbol
            exchange (str): Exchange
            
        Returns:
            list: List of available expirations in YYYYMMDD format
        """
        if not self.is_connected():
            logger.warning("Not connected to IB. Attempting to connect...")
            if not self.connect():
                return []
        
        # Create a stock contract
        stock = Contract()
        stock.symbol = symbol
        stock.secType = 'STK'
        stock.exchange = exchange
        stock.currency = 'USD'
        
        try:
            self.ib.qualifyContracts(stock)
            
            # Request option chain
            logger.info(f"Requesting option chain for {symbol}")
            chains = self.ib.reqSecDefOptParams(stock.symbol, '', stock.secType, stock.conId)
            
            if not chains:
                logger.warning(f"No option chain found for {symbol}")
                return []
            
            chain = next((c for c in chains if c.exchange == exchange), None)
            if not chain:
                logger.warning(f"No option chain found for {symbol} on exchange {exchange}")
                return []
            
            logger.info(f"Found {len(chain.expirations)} expirations for {symbol}")
            return sorted(chain.expirations)
        
        except Exception as e:
            logger.error(f"Error getting option expirations for {symbol}: {e}")
            return []
            
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
            max_wait = 5  # seconds
            logger.debug(f"Waiting up to {max_wait} seconds for option market data...")
            
            for i in range(max_wait):
                self.ib.sleep(1)
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
    
    def get_multiple_option_prices(self, symbol, expiration, strikes, rights=None, exchange='SMART'):
        """
        Get option prices for multiple strikes and option types at once
        
        Args:
            symbol (str): Stock symbol
            expiration (str): Option expiration (format: YYYYMMDD)
            strikes (list): List of strike prices
            rights (list): List of option rights ('C' for calls, 'P' for puts, None for both)
            exchange (str): Exchange
            
        Returns:
            dict: Dictionary with strike and right as keys, option data as values
        """
        if not self.is_connected():
            logger.warning("Not connected to IB. Attempting to connect...")
            if not self.connect():
                return {}
                
        if rights is None:
            rights = ['C', 'P']  # Default to both calls and puts
            
        logger.info(f"Creating option contracts for {symbol} {expiration} with {len(strikes)} strikes and {len(rights)} rights")
        
        # Create all option contracts
        options = []
        for strike in strikes:
            for right in rights:
                option = Option(symbol, expiration, strike, right, exchange)
                option.currency = 'USD'
                option.multiplier = '100'  # Standard for equity options
                options.append((strike, right, option))
        
        # Qualify all contracts at once
        logger.info(f"Qualifying {len(options)} option contracts...")
        qualified_options = []
        results = {}
        
        try:
            # Split into batches if there are many options (IB has limits)
            batch_size = 25
            for i in range(0, len(options), batch_size):
                batch = options[i:i+batch_size]
                batch_contracts = [opt[2] for opt in batch]
                
                # Process each contract in the batch individually to handle ambiguous contracts
                for j, contract in enumerate(batch_contracts):
                    strike, right, _ = batch[j]
                    
                    try:
                        # Try to qualify the contract
                        qualified = self.ib.qualifyContracts(contract)
                        if qualified:
                            qualified_options.append((strike, right, qualified[0]))
                    except Exception as e:
                        error_msg = str(e)
                        if "ambiguous" in error_msg.lower():
                            logger.warning(f"Ambiguous contract: {contract.symbol} {contract.lastTradeDateOrContractMonth} {contract.strike} {contract.right}")
                            
                            # Try to create a more specific contract
                            try:
                                from ib_insync import Contract
                                # Create a full contract specification
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
                                qualified = self.ib.qualifyContracts(detailed_contract)
                                if qualified:
                                    qualified_options.append((strike, right, qualified[0]))
                            except Exception as inner_e:
                                logger.warning(f"Error handling ambiguous contract: {inner_e}")
                        else:
                            logger.warning(f"Could not qualify contract for {contract.symbol} {contract.lastTradeDateOrContractMonth} {contract.strike} {contract.right}: {e}")
            
            logger.info(f"Successfully qualified {len(qualified_options)} option contracts")
            
            # If none of the contracts could be qualified, return empty results
            if not qualified_options:
                logger.error("Could not qualify any of the option contracts")
                return {}
                
            # Request market data for all qualified options
            logger.info(f"Requesting market data for {len(qualified_options)} options...")
            tickers = {}
            
            # Request market data for all qualified options
            for strike, right, contract in qualified_options:
                ticker = self.ib.reqMktData(contract)
                tickers[(strike, right)] = (contract, ticker)
            
            # Wait for data to come in
            logger.info("Waiting for market data (5 seconds)...")
            self.ib.sleep(5)
            
            # Process all the ticker data
            for (strike, right), (contract, ticker) in tickers.items():
                key = (strike, right)
                
                result = {
                    'symbol': symbol,
                    'expiration': expiration,
                    'strike': strike,
                    'right': right,
                    'last': ticker.last,
                    'bid': ticker.bid,
                    'ask': ticker.ask,
                    'volume': ticker.volume,
                    'open_interest': ticker.open_interest if hasattr(ticker, 'open_interest') else None,
                    'underlying': ticker.underlying if hasattr(ticker, 'underlying') else None
                }
                
                results[key] = result
                
                # Cancel market data subscription
                self.ib.cancelMktData(contract)
            
            logger.info(f"Retrieved data for {len(results)} options")
            return results
            
        except Exception as e:
            logger.error(f"Error getting multiple option prices: {e}")
            return {}
    
    def get_multiple_stocks_option_prices(self, symbols, expiration, strikes_map=None, rights=None, exchange='SMART'):
        """
        Get option prices for multiple stocks in a single batch
        
        Args:
            symbols (list): List of stock symbols
            expiration (str): Option expiration date in format YYYYMMDD
            strikes_map (dict): Dictionary mapping symbols to lists of strikes.
                                If None, the same strikes will be used for all symbols.
            rights (list): List of option types, defaults to ['C', 'P']
            exchange (str): Exchange to use
            
        Returns:
            dict: Dictionary with symbol as key and option data as nested dict
        """
        if not self.is_connected():
            logger.warning("Not connected to IB. Attempting to connect...")
            if not self.connect():
                return {}
        
        if rights is None:
            rights = ['C', 'P']
        
        # Create all the option contracts for each symbol
        all_contracts = []
        
        logger.info(f"Creating option contracts for {len(symbols)} symbols with expiration {expiration}")
        
        for symbol in symbols:
            # Determine strikes for this symbol
            symbol_strikes = []
            if strikes_map and symbol in strikes_map:
                symbol_strikes = strikes_map[symbol]
            elif strikes_map and '__default__' in strikes_map:
                symbol_strikes = strikes_map['__default__']
            else:
                logger.warning(f"No strikes specified for {symbol} and no default strikes found")
                continue
            
            logger.info(f"Processing {len(symbol_strikes)} strikes for {symbol}")
            
            # Create contracts for each strike and right
            for strike in symbol_strikes:
                for right in rights:
                    contract = Option(symbol, expiration, strike, right, exchange, 'USD')
                    contract.multiplier = '100'  # Standard for equity options
                    # Store contract details along with the contract
                    all_contracts.append((contract, symbol, strike, right))
        
        if not all_contracts:
            logger.error("No valid option contracts created")
            return {}
        
        # Qualify each contract individually to handle ambiguous cases
        logger.info(f"Qualifying {len(all_contracts)} option contracts...")
        qualified_contracts = []
        
        for contract, symbol, strike, right in all_contracts:
            try:
                # Try to qualify the contract first
                qualified = self.ib.qualifyContracts(contract)
                if qualified:
                    qualified_contracts.append((qualified[0], symbol, strike, right))
            except Exception as e:
                error_msg = str(e)
                if "ambiguous" in error_msg.lower():
                    logger.warning(f"Ambiguous contract: {symbol} {expiration} {strike} {right}")
                    
                    # Try to create a more specific contract
                    try:
                        from ib_insync import Contract
                        # Create a full contract specification
                        detailed_contract = Contract(
                            secType='OPT',
                            symbol=symbol,
                            lastTradeDateOrContractMonth=expiration,
                            strike=strike,
                            right=right,
                            multiplier='100',  # Standard for equity options
                            exchange='SMART',
                            currency='USD'
                        )
                        
                        # Try again with the detailed contract
                        qualified = self.ib.qualifyContracts(detailed_contract)
                        if qualified:
                            qualified_contracts.append((qualified[0], symbol, strike, right))
                    except Exception as inner_e:
                        logger.warning(f"Error handling ambiguous contract: {inner_e}")
                else:
                    logger.warning(f"Could not qualify contract for {symbol} {expiration} {strike} {right}: {e}")
        
        if not qualified_contracts:
            logger.error("Could not qualify any option contracts")
            return {}
        
        logger.info(f"Successfully qualified {len(qualified_contracts)} option contracts")
        
        # Request market data for all contracts
        logger.info(f"Requesting market data for {len(qualified_contracts)} options...")
        tickers = {}
        
        for qc, symbol, strike, right in qualified_contracts:
            ticker = self.ib.reqMktData(qc)
            tickers[(qc, symbol, strike, right)] = ticker
        
        # Wait for data to arrive
        wait_time = 5  # seconds
        logger.info(f"Waiting for market data ({wait_time} seconds)...")
        self.ib.sleep(wait_time)
        
        # Collect the results organized by symbol
        results = {symbol: {} for symbol in symbols}
        
        for (qc, symbol, strike, right), ticker in tickers.items():
            # Process the results
            option_data = {
                'bid': ticker.bid if hasattr(ticker, 'bid') and ticker.bid > 0 else None,
                'ask': ticker.ask if hasattr(ticker, 'ask') and ticker.ask > 0 else None,
                'last': ticker.last if hasattr(ticker, 'last') and ticker.last > 0 else None
            }
            
            # Add to results dictionary
            if symbol not in results:
                results[symbol] = {}
            
            results[symbol][(strike, right)] = option_data
            
            # Cancel the market data subscription
            self.ib.cancelMktData(qc)
        
        logger.info(f"Retrieved option data for {len(results)} symbols")
        return results

    def create_option_contract(self, ticker, expiration_date, strike, right):
        """
        Create an option contract
        
        Args:
            ticker (str): Stock ticker symbol
            expiration_date (str): Option expiration date in YYYYMMDD format
            strike (float): Strike price
            right (str): Option right ('C' for call, 'P' for put)
            
        Returns:
            Contract: IB option contract
        """
        from ib_insync import Option
        contract = Option(ticker, expiration_date, strike, right, 'SMART', '100', 'USD')
        return contract

    def get_portfolio(self):
        """
        Get current portfolio positions and account information from IB
        
        Returns:
            dict: Dictionary containing account information and positions
        """
        is_market_open = self._is_market_hours()
        
        if not self.is_connected():
            if is_market_open:
                logger.warning("Not connected to IB during market hours. Attempting to connect...")
                if not self.connect():
                    raise ConnectionError("Failed to connect to IB during market hours")
            else:
                logger.info("Market is closed. Using mock portfolio data.")
                return self._generate_mock_portfolio()
        
        try:
            # Get account summary
            account_id = self.ib.managedAccounts()[0]
            account_values = self.ib.accountSummary(account_id)
            
            if not account_values and is_market_open:
                raise ValueError("No account data available during market hours")
            
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
            
            if not positions and is_market_open:
                raise ValueError("No position data available during market hours")
            elif not positions:
                logger.info("No positions found during closed market. Using mock portfolio data.")
                return self._generate_mock_portfolio()
            
            return {
                'account_id': account_id,
                'available_cash': account_info.get('available_cash', 0),
                'account_value': account_info.get('account_value', 0),
                'positions': positions
            }
        
        except Exception as e:
            if is_market_open:
                logger.error(f"Error getting portfolio during market hours: {str(e)}")
                raise
            else:
                logger.info(f"Error getting portfolio during closed market. Using mock portfolio data.")
                return self._generate_mock_portfolio()

    def get_options_chain(self, ticker, expiration=None, strikes=10, interval=5):
        """Get options chain for a ticker around current price"""
        # Implementation details...
        
    def get_full_options_chain(self, ticker, expiration=None):
        """
        Get the full options chain with greeks for a ticker
        
        Args:
            ticker (str): Stock ticker symbol
            expiration (str, optional): Expiration date in YYYYMMDD format
            
        Returns:
            dict: Dictionary with calls and puts with full option data including greeks
        """
        try:
            if not self.is_connected():
                logger.error("Not connected to IB")
                return None
                
            # Create qualifier for the stock
            stock = Stock(ticker, 'SMART', 'USD')
                
            # Get current stock price to determine strikes range
            self.ib.qualifyContracts(stock)
            # Request snapshot to make sure we have current data
            self.ib.reqMktData(stock)
            self.ib.sleep(1)  # Wait for data to arrive
            
            ticker_obj = self.ib.reqTickers(stock)[0]
            current_price = ticker_obj.marketPrice()
            
            if expiration is None:
                # Get available expirations and use the closest one
                expirations = self.get_option_expirations(ticker)
                if not expirations:
                    logger.error(f"No expirations found for {ticker}")
                    return None
                # Use the closest expiration
                expiration = expirations[0]
            
            # Create wide strike range around current price to get all strikes
            min_strike = int(current_price * 0.5)  # 50% below current price
            max_strike = int(current_price * 1.5)  # 50% above current price
            
            # Create chains object with all strikes
            chains = self.ib.reqSecDefOptParams(stock.symbol, '', stock.secType, stock.conId)
            
            if not chains:
                logger.error(f"No option chains found for {ticker}")
                return None
                
            # Filter for the exchange we want
            chain = next((c for c in chains if c.exchange == 'SMART'), None)
            if chain is None:
                logger.error(f"No SMART exchange found for {ticker}")
                return None
                
            # Get all strikes within our range
            strikes = [strike for strike in chain.strikes 
                      if min_strike <= strike <= max_strike]
                
            if not strikes:
                logger.error(f"No strikes found for {ticker}")
                return None
                
            # Create list of option contracts
            option_contracts = []
            
            for strike in strikes:
                # Create a call and put contract for each strike
                call = Option(ticker, expiration, strike, 'C', 'SMART', 'USD')
                put = Option(ticker, expiration, strike, 'P', 'SMART', 'USD')
                option_contracts.extend([call, put])
                
            # Qualify all contracts at once
            qualified_contracts = self.ib.qualifyContracts(*option_contracts)
            
            if not qualified_contracts:
                logger.error(f"Failed to qualify option contracts for {ticker}")
                return None
                
            # Request market data for all contracts
            tickers = self.ib.reqTickers(*qualified_contracts)
            
            # Organize the data
            calls = []
            puts = []
            
            for ticker_obj in tickers:
                contract = ticker_obj.contract
                
                # Skip if we couldn't get market data
                if not hasattr(ticker_obj, 'modelGreeks') or ticker_obj.modelGreeks is None:
                    continue
                    
                option_data = {
                    'strike': float(contract.strike),
                    'bid': float(ticker_obj.bid) if ticker_obj.bid else 0,
                    'ask': float(ticker_obj.ask) if ticker_obj.ask else 0,
                    'last': float(ticker_obj.last) if ticker_obj.last else 0,
                    'volume': int(ticker_obj.volume) if ticker_obj.volume else 0,
                    'openInterest': int(ticker_obj.open_interest) if hasattr(ticker_obj, 'open_interest') else 0,
                    'impliedVol': float(ticker_obj.impliedVol) if ticker_obj.impliedVol else 0,
                    'delta': float(ticker_obj.modelGreeks.delta) if ticker_obj.modelGreeks else 0,
                    'gamma': float(ticker_obj.modelGreeks.gamma) if ticker_obj.modelGreeks else 0,
                    'vega': float(ticker_obj.modelGreeks.vega) if ticker_obj.modelGreeks else 0,
                    'theta': float(ticker_obj.modelGreeks.theta) if ticker_obj.modelGreeks else 0,
                }
                
                if contract.right == 'C':
                    calls.append(option_data)
                else:
                    puts.append(option_data)
                    
            # Sort calls and puts by strike
            calls.sort(key=lambda x: x['strike'])
            puts.sort(key=lambda x: x['strike'])
            
            return {
                'calls': calls,
                'puts': puts,
                'underlying_price': current_price,
                'expiration': expiration
            }
            
        except Exception as e:
            logger.error(f"Error getting full options chain for {ticker}: {e}")
            logger.error(traceback.format_exc())
            return None
    
    def get_option_price(self, option_contract):
        """Get price for a specific option contract"""
        # ... existing code ... 

    def get_historical_data(self, symbol, duration='1 D', bar_size='1 day', what_to_show='TRADES', use_rth=True):
        """
        Get historical data for a stock
        
        Args:
            symbol (str): Stock symbol
            duration (str): Time duration (e.g., '1 D', '1 W', '1 M')
            bar_size (str): Size of bars (e.g., '1 day', '1 hour', '15 mins')
            what_to_show (str): Type of data to show
            use_rth (bool): Whether to use regular trading hours only
            
        Returns:
            dict: Historical data or None if error
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
            
            # Get end time (current time if market closed, or previous close if needed)
            end_time = ''  # Empty string means current time
            
            # Request historical data
            logger.info(f"Getting historical data for {symbol} for duration {duration}")
            
            bars = self.ib.reqHistoricalData(
                qualified_contract,
                endDateTime=end_time,
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow=what_to_show,
                useRTH=use_rth,
                formatDate=1
            )
            
            if not bars:
                logger.warning(f"No historical data available for {symbol}")
                return None
            
            # Get the latest bar
            latest_bar = bars[-1]
            
            # Build and return the result
            result = {
                'symbol': symbol,
                'last': latest_bar.close,
                'bid': latest_bar.close,  # Use close price as a substitute
                'ask': latest_bar.close,  # Use close price as a substitute
                'high': latest_bar.high,
                'low': latest_bar.low,
                'close': latest_bar.close,
                'open': latest_bar.open,
                'volume': latest_bar.volume,
                'halted': False,
                'timestamp': latest_bar.date.isoformat() if hasattr(latest_bar, 'date') else datetime.now().isoformat(),
                'is_historical': True  # Flag to indicate this is historical data
            }
            
            logger.info(f"Successfully retrieved historical data for {symbol} (close: {latest_bar.close})")
            return result
            
        except Exception as e:
            error_msg = str(e)
            if "There is no current event loop" in error_msg:
                logger.error("Asyncio event loop error in get_historical_data. Retrying with new event loop.")
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    return self.get_historical_data(symbol, duration, bar_size, what_to_show, use_rth)
                except Exception as retry_error:
                    logger.error(f"Failed to get historical data after event loop retry: {str(retry_error)}")
                    return None
            else:
                logger.error(f"Error getting historical data for {symbol}: {error_msg}")
                logger.debug(traceback.format_exc())
                return None
                
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
        Check if the US market is currently open
        
        Returns:
            bool: True if market is open, False otherwise
        """
        # Get current US Eastern time
        eastern = pytz.timezone('US/Eastern')
        now = datetime.now(eastern)
        
        # Check if it's a weekday
        if now.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
            return False
            
        # Regular market hours are 9:30 AM to 4:00 PM Eastern
        market_open = time(9, 30)
        market_close = time(16, 0)
        current_time = now.time()
        
        return market_open <= current_time <= market_close

    def get_stock_data(self, symbol):
        """
        Get comprehensive stock data including price, volume, and other metrics
        
        Args:
            symbol (str): Stock symbol
            
        Returns:
            dict: Dictionary with stock data or None if error
        """
        is_market_open = self._is_market_hours()
        
        if not self.is_connected():
            if is_market_open:
                logger.warning("Not connected to IB during market hours. Attempting to connect...")
                if not self.connect():
                    raise ConnectionError("Failed to connect to IB during market hours")
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
            if is_market_open and last_price is None:
                raise ValueError(f"No real-time price data available for {symbol} during market hours")
            
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
                'is_historical': False
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

    def get_historical_option_data(self, symbol, expiration, right='C', strike=None, duration='1 D', bar_size='1 day'):
        """
        Get historical data for options
        
        Args:
            symbol (str): Stock symbol
            expiration (str): Option expiration date in format YYYYMMDD
            right (str): Option right ('C' for call, 'P' for put)
            strike (float): Strike price (if None, will get data for ATM option)
            duration (str): Time duration (e.g., '1 D', '1 W', '1 M')
            bar_size (str): Size of bars (e.g., '1 day', '1 hour', '15 mins')
            
        Returns:
            dict: Historical options data or None if error
        """
        if not self.is_connected():
            logger.warning("Not connected to IB. Attempting to connect...")
            if not self.connect():
                # If can't connect, use mock data
                if strike is None:
                    # Use a reasonable mock strike if none provided
                    strike = 100.0
                return self._generate_mock_option_data(symbol, expiration, right, strike)
                
        try:
            # Ensure event loop exists for this thread
            self._ensure_event_loop()
            
            # If no strike provided, get current stock price and find ATM strike
            if strike is None:
                # Get stock data (which may itself use historical data)
                stock_data = self.get_stock_data(symbol)
                if not stock_data:
                    logger.error(f"Could not get stock data for {symbol}")
                    return self._generate_mock_option_data(symbol, expiration, right, 100.0)
                
                stock_price = stock_data.get('last')
                
                # Find the closest standard strike to the current price
                strike = self._adjust_to_standard_strike(stock_price)
                logger.info(f"Using closest strike {strike} to current price {stock_price}")
            
            # Create the option contract
            option = Option(symbol, expiration, strike, right, 'SMART', '100', 'USD')
            
            # Try to qualify the contract
            try:
                qualified_contracts = self.ib.qualifyContracts(option)
                if not qualified_contracts:
                    logger.error(f"Could not qualify option contract: {symbol} {expiration} {strike} {right}")
                    return self._generate_mock_option_data(symbol, expiration, right, strike)
                    
                qualified_contract = qualified_contracts[0]
            except Exception as e:
                logger.error(f"Error qualifying option contract: {e}")
                return self._generate_mock_option_data(symbol, expiration, right, strike)
            
            # Request historical data
            logger.info(f"Getting historical data for option {symbol} {expiration} {strike} {right}")
            
            # Empty string for endDateTime means current time
            bars = self.ib.reqHistoricalData(
                qualified_contract,
                endDateTime='',
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )
            
            if not bars or len(bars) == 0:
                logger.warning(f"No historical data available for option {symbol} {expiration} {strike} {right}")
                return self._generate_mock_option_data(symbol, expiration, right, strike)
                
            # Get the latest bar
            latest_bar = bars[-1]
            
            # Create option data
            option_data = {
                'symbol': symbol,
                'expiration': expiration,
                'strike': strike,
                'right': right,
                'bid': latest_bar.close * 0.95,  # Estimate
                'ask': latest_bar.close * 1.05,  # Estimate
                'last': latest_bar.close,
                'volume': latest_bar.volume,
                'open_interest': 0,  # Not available in historical data
                'underlying': None,  # Not available in historical data
                'delta': None,       # Not available in historical data
                'gamma': None,       # Not available in historical data
                'theta': None,       # Not available in historical data
                'vega': None,        # Not available in historical data
                'is_historical': True,
                'timestamp': latest_bar.date.isoformat() if hasattr(latest_bar, 'date') else datetime.now().isoformat()
            }
            
            logger.info(f"Successfully retrieved historical data for option {symbol} {expiration} {strike} {right}")
            return option_data
            
        except Exception as e:
            logger.error(f"Error getting historical option data: {e}")
            logger.debug(traceback.format_exc())
            return self._generate_mock_option_data(symbol, expiration, right, strike)
            
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