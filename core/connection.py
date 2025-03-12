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
from datetime import datetime

# Import ib_insync
from ib_insync import IB, Stock, Option, Contract, util

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('autotrader.connection')

# Set ib_insync logger to WARNING level to reduce noise
logging.getLogger('ib_insync').setLevel(logging.WARNING)
logging.getLogger('ib_insync.wrapper').setLevel(logging.WARNING)
logging.getLogger('ib_insync.client').setLevel(logging.WARNING)
logging.getLogger('ib_insync.ticker').setLevel(logging.WARNING)

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
    
    # Return to enable chaining if needed
    return True

# Call to suppress logs right away
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
            
            logger.info(f"Connecting to IB at {self.host}:{self.port}")
            
            # Set read-only mode if requested
            if self.readonly:
                self.ib.clientId = self.client_id
                self.ib.connect(self.host, self.port, clientId=self.client_id, readonly=True, timeout=self.timeout)
            else:
                self.ib.clientId = self.client_id
                self.ib.connect(self.host, self.port, clientId=self.client_id, readonly=False, timeout=self.timeout)
            
            self._connected = self.ib.isConnected()
            if self._connected:
                logger.info(f"Successfully connected to IB")
                return True
            else:
                logger.error(f"Failed to connect to IB")
                return False
        except Exception as e:
            logger.error(f"Error connecting to IB: {str(e)}")
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
            logger.error(f"Error getting {symbol} price: {e}")
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
                - account_id: Account ID
                - available_cash: Available cash for trading
                - account_value: Total account value (net liquidation)
                - positions: Dictionary of current positions, keyed by symbol
                    - Each position contains: shares, avg_cost, market_value, etc.
        """
        if not self.is_connected():
            logger.warning("Not connected to IB. Attempting to connect...")
            if not self.connect():
                return None
        
        try:
            # Get account summary
            account_id = self.ib.managedAccounts()[0]
            account_values = self.ib.accountSummary(account_id)
            
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
            
            if not positions and self.readonly:
                # When in read-only mode, we might not get real positions
                # In this case, return the raw portfolio for backwards compatibility
                logger.debug("No positions found, returning raw portfolio data for backwards compatibility")
                return {
                    'account_id': account_id,
                    'available_cash': account_info.get('available_cash', 0),
                    'account_value': account_info.get('account_value', 0),
                    'positions': portfolio  # Return the raw portfolio for backwards compatibility
                }
            
            return {
                'account_id': account_id,
                'available_cash': account_info.get('available_cash', 0),
                'account_value': account_info.get('account_value', 0),
                'positions': positions
            }
        
        except Exception as e:
            logger.error(f"Error getting portfolio: {e}")
            return None

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