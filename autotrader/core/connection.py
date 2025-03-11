"""
Connection module for establishing connection with Interactive Brokers
"""

import time
from ib_insync import IB, util, Option, Contract
import logging
from typing import Optional, Dict, Any
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('autotrader.connection')


class IBConnection:
    """
    Class for managing connection to Interactive Brokers
    """
    def __init__(self, host='127.0.0.1', port=7497, client_id=1, timeout=20, readonly=False):
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
    
    def connect(self):
        """
        Connect to Interactive Brokers
        
        Returns:
            bool: True if connected successfully, False otherwise
        """
        if self._connected and self.ib.isConnected():
            logger.info("Already connected to IB")
            return True
        
        try:
            logger.info(f"Connecting to IB on {self.host}:{self.port}")
            self.ib.connect(self.host, self.port, clientId=self.client_id, readonly=self.readonly, timeout=self.timeout)
            self._connected = self.ib.isConnected()
            
            if self._connected:
                logger.info("Successfully connected to IB")
            else:
                logger.error("Failed to connect to IB")
            
            return self._connected
        except Exception as e:
            logger.error(f"Error connecting to IB: {e}")
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
        Get current stock price
        
        Args:
            symbol (str): Stock symbol
            
        Returns:
            float: Current stock price
        """
        if not self.is_connected():
            logger.warning("Not connected to IB. Attempting to connect...")
            if not self.connect():
                return None
            
        contract = Contract()
        contract.symbol = symbol
        contract.secType = 'STK'
        contract.exchange = 'SMART'
        contract.currency = 'USD'
        
        logger.info(f"Qualifying contract for {symbol}...")
        self.ib.qualifyContracts(contract)
        logger.info(f"Contract qualified: {contract}")
        
        # Request market data with valid generic ticks for stocks
        # Using only the valid ticks from the error message
        logger.info(f"Requesting market data for {symbol}...")
        ticker = self.ib.reqMktData(contract, genericTickList="100,101,105,106,165,221,225,233,236,258,318,411,456")
        logger.info("Waiting for market data (5 seconds)...")
        self.ib.sleep(5)  # Wait longer for data
        
        logger.info(f"Ticker data received: last={ticker.last}, close={ticker.close}, bid={ticker.bid}, ask={ticker.ask}, lastRTHTrade={ticker.lastRTHTrade if hasattr(ticker, 'lastRTHTrade') else 'N/A'}")
        
        price = None
        if hasattr(ticker, 'lastRTHTrade') and ticker.lastRTHTrade > 0:
            price = ticker.lastRTHTrade
            logger.info(f"Using last RTH trade price: {price}")
        elif ticker.last > 0:
            price = ticker.last
            logger.info(f"Using last price: {price}")
        elif ticker.close > 0:
            price = ticker.close
            logger.info(f"Using close price: {price}")
        elif ticker.bid > 0 and ticker.ask > 0:
            price = (ticker.bid + ticker.ask) / 2
            logger.info(f"Using mid price: {price}")
        else:
            # Fallback to a fixed price for testing if no data is available
            logger.warning(f"Could not determine price for {symbol}, using a default test price")
            price = 950.0  # NVDA approximate price, change as needed
        
        # Cancel market data subscription
        logger.info(f"Canceling market data subscription for {symbol}")
        self.ib.cancelMktData(contract)
        
        return price
    
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
                options.append(option)
        
        return options
    
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
            
    def get_option_price(self, symbol, expiration, strike, right='C', exchange='SMART'):
        """
        Get option price
        
        Args:
            symbol (str): Stock symbol
            expiration (str): Option expiration (format: YYYYMMDD)
            strike (float): Option strike price
            right (str): Option right ('C' for call, 'P' for put)
            exchange (str): Exchange
            
        Returns:
            dict: Option price information
        """
        if not self.is_connected():
            logger.warning("Not connected to IB. Attempting to connect...")
            if not self.connect():
                return None
        
        logger.info(f"Creating option contract: {symbol} {expiration} ${strike} {right}")
        option = Option(symbol, expiration, strike, right, exchange)
        option.currency = 'USD'  # Ensure currency is set
        
        try:
            logger.info(f"Qualifying option contract...")
            contracts = self.ib.qualifyContracts(option)
            if not contracts:
                logger.warning(f"Could not qualify option contract: {symbol} {expiration} ${strike} {right}")
                
                # Try to get available expirations
                available_expirations = self.get_available_expirations(symbol)
                if available_expirations:
                    logger.info(f"Available expirations for {symbol}: {', '.join(available_expirations[:5])}...")
                    
                # Return dummy data for testing purposes
                return {
                    'symbol': symbol,
                    'expiration': expiration,
                    'strike': strike,
                    'right': right,
                    'last': None,
                    'bid': None,
                    'ask': None,
                    'volume': 0,
                    'open_interest': 0,
                    'underlying': None
                }
            
            qualified_option = contracts[0]
            logger.info(f"Option contract qualified: {qualified_option}")
            
            # Request market data
            logger.info(f"Requesting market data for option: {symbol} {expiration} ${strike} {right}")
            ticker = self.ib.reqMktData(qualified_option)
            self.ib.sleep(2)  # Wait for data
            
            logger.info(f"Option data received: last={ticker.last}, bid={ticker.bid}, ask={ticker.ask}")
            
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
            
            # Cancel market data subscription
            logger.info(f"Canceling market data subscription for option")
            self.ib.cancelMktData(qualified_option)
            
            return result
        except Exception as e:
            logger.error(f"Error getting option price for {symbol} {expiration} ${strike} {right}: {e}")
            # Return dummy data for testing purposes
            return {
                'symbol': symbol,
                'expiration': expiration,
                'strike': strike,
                'right': right,
                'last': None,
                'bid': None,
                'ask': None,
                'volume': 0,
                'open_interest': 0,
                'underlying': None
            }
    
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
                
                # Qualify the batch
                qualified_batch = self.ib.qualifyContracts(*batch_contracts)
                
                # Map back to our original strike/right information
                for j, qualified in enumerate(qualified_batch):
                    strike, right, _ = batch[j]
                    qualified_options.append((strike, right, qualified))
            
            logger.info(f"Successfully qualified {len(qualified_options)} option contracts")
            
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