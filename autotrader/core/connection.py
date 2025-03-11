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
        
        logger.info(f"Qualifying contract for {symbol}...")
        
        # Create a stock contract
        contract = Contract(symbol=symbol, secType='STK', exchange='SMART', currency='USD')
        
        try:
            # Qualify the contract
            qualified_contracts = self.ib.qualifyContracts(contract)
            if not qualified_contracts:
                logger.error(f"Failed to qualify contract for {symbol}")
                return None
            
            qualified_contract = qualified_contracts[0]
            logger.info(f"Contract qualified: {qualified_contract}")
            
            # Request market data
            logger.info(f"Requesting market data for {symbol}...")
            ticker = self.ib.reqMktData(qualified_contract)
            
            # Wait for market data to be received
            wait_time = 5  # seconds
            logger.info(f"Waiting for market data ({wait_time} seconds)...")
            self.ib.sleep(wait_time)
            
            # Get the last price
            last_price = ticker.last if ticker.last else (ticker.close if ticker.close else None)
            bid_price = ticker.bid if ticker.bid else None
            ask_price = ticker.ask if ticker.ask else None
            last_rth_trade = ticker.lastRTHTrade.price if hasattr(ticker, 'lastRTHTrade') and ticker.lastRTHTrade else None
            
            logger.info(f"Ticker data received: last={last_price}, close={ticker.close}, bid={bid_price}, ask={ask_price}, lastRTHTrade={last_rth_trade}")
            
            # If no last price is available, check other prices
            if last_price is None:
                if bid_price and ask_price:
                    # Use midpoint of bid-ask spread
                    last_price = (bid_price + ask_price) / 2
                    logger.info(f"Using bid-ask midpoint: {last_price}")
                elif bid_price:
                    last_price = bid_price
                    logger.info(f"Using bid price: {last_price}")
                elif ask_price:
                    last_price = ask_price
                    logger.info(f"Using ask price: {last_price}")
                elif last_rth_trade:
                    last_price = last_rth_trade
                    logger.info(f"Using last RTH trade: {last_price}")
            
            # Cancel the market data subscription
            logger.info(f"Canceling market data subscription for {symbol}")
            self.ib.cancelMktData(qualified_contract)
            
            if last_price is None:
                logger.error(f"Could not get price for {symbol}")
                return None
                
            logger.info(f"Using last price: {last_price}")
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
        logger.info(f"Qualifying contracts for {len(symbols)} stocks...")
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
                logger.info(f"Contract qualified: {qualified_contract}")
                
                qualified_contracts.append(qualified_contract)
                symbol_to_contract[qualified_contract.symbol] = qualified_contract
                
            except Exception as e:
                logger.error(f"Error qualifying contract for {symbol}: {e}")
                results[symbol] = None
        
        # Step 2: Request market data for all qualified contracts
        if qualified_contracts:
            tickers = {}
            logger.info(f"Requesting market data for {len(qualified_contracts)} stocks...")
            
            # Request market data for all contracts
            for contract in qualified_contracts:
                symbol = contract.symbol
                ticker = self.ib.reqMktData(contract)
                tickers[symbol] = ticker
            
            # Wait for market data to be received
            wait_time = 5  # seconds
            logger.info(f"Waiting for market data ({wait_time} seconds)...")
            self.ib.sleep(wait_time)
            
            # Process the received data
            for symbol, ticker in tickers.items():
                # Get the last price
                last_price = ticker.last if ticker.last else (ticker.close if ticker.close else None)
                bid_price = ticker.bid if ticker.bid else None
                ask_price = ticker.ask if ticker.ask else None
                last_rth_trade = ticker.lastRTHTrade.price if hasattr(ticker, 'lastRTHTrade') and ticker.lastRTHTrade else None
                
                logger.info(f"Ticker data for {symbol}: last={last_price}, close={ticker.close}, bid={bid_price}, ask={ask_price}, lastRTHTrade={last_rth_trade}")
                
                # If no last price is available, check other prices
                if last_price is None:
                    if bid_price and ask_price:
                        # Use midpoint of bid-ask spread
                        last_price = (bid_price + ask_price) / 2
                        logger.info(f"Using bid-ask midpoint for {symbol}: {last_price}")
                    elif bid_price:
                        last_price = bid_price
                        logger.info(f"Using bid price for {symbol}: {last_price}")
                    elif ask_price:
                        last_price = ask_price
                        logger.info(f"Using ask price for {symbol}: {last_price}")
                    elif last_rth_trade:
                        last_price = last_rth_trade
                        logger.info(f"Using last RTH trade for {symbol}: {last_price}")
                
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
            
    def get_option_price(self, contract):
        """
        Get the price data for an option contract
        
        Args:
            contract (Contract): IB option contract
            
        Returns:
            dict: Dictionary with bid, ask, and last prices
        """
        try:
            # Qualify the contract first
            qualified_contracts = self.ib.qualifyContracts(contract)
            if not qualified_contracts:
                return None
            
            qualified_contract = qualified_contracts[0]
            
            # Request market data
            ticker = self.ib.reqMktData(qualified_contract)
            
            # Wait for market data to arrive
            self.ib.sleep(3)
            
            # Get price data
            bid = ticker.bid if hasattr(ticker, 'bid') and ticker.bid is not None and ticker.bid > 0 else None
            ask = ticker.ask if hasattr(ticker, 'ask') and ticker.ask is not None and ticker.ask > 0 else None
            last = ticker.last if hasattr(ticker, 'last') and ticker.last is not None and ticker.last > 0 else None
            
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
                    # Store contract details along with the contract
                    all_contracts.append((contract, symbol, strike, right))
        
        if not all_contracts:
            logger.error("No valid option contracts created")
            return {}
        
        # Qualify all contracts at once
        logger.info(f"Qualifying {len(all_contracts)} option contracts...")
        qualified_contracts = []
        
        for contract, symbol, strike, right in all_contracts:
            try:
                # Qualify the contract
                qualified = self.ib.qualifyContracts(contract)
                if qualified:
                    qualified_contracts.append((qualified[0], symbol, strike, right))
            except Exception as e:
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
                - account_value: Total account value
                - available_cash: Available cash for trading
                - positions: Dictionary of current positions, keyed by symbol
                    - Each position contains: shares, avg_cost, market_value, etc.
        """
        if not self.is_connected():
            logger.warning("Not connected to IB. Attempting to connect...")
            if not self.connect():
                return None
        
        try:
            # If in readonly mode, return mock data for demo purposes
            if self.readonly:
                logger.info("Using mock portfolio data (readonly mode)")
                # Create mock positions for common stocks
                mock_positions = {}
                mock_stocks = {
                    'AAPL': {'price': 150.0, 'shares': 100},
                    'TSLA': {'price': 220.0, 'shares': 50},
                    'NVDA': {'price': 100.0, 'shares': 200},
                    'MSFT': {'price': 380.0, 'shares': 75},
                    'AMZN': {'price': 190.0, 'shares': 60},
                    'GOOG': {'price': 165.0, 'shares': 40}
                }
                
                # Get stock prices for positions that exist
                for symbol, data in mock_stocks.items():
                    # Try to get current price if available
                    current_price = None
                    try:
                        # First try to get live price
                        current_price = self.get_stock_price(symbol)
                    except:
                        pass
                        
                    # If we couldn't get a live price, use the mock price
                    if current_price is None:
                        current_price = data['price']
                        
                    shares = data['shares']
                    avg_cost = current_price * 0.9  # Mock average cost below current price
                    market_value = current_price * shares
                    unrealized_pnl = market_value - (avg_cost * shares)
                    
                    mock_positions[symbol] = {
                        'shares': shares,
                        'avg_cost': avg_cost,
                        'market_price': current_price,
                        'market_value': market_value,
                        'unrealized_pnl': unrealized_pnl,
                        'realized_pnl': 0
                    }
                
                return {
                    'account_value': 500000.0,
                    'available_cash': 100000.0,
                    'positions': mock_positions
                }
            
            # Get account summary
            account_id = self.ib.managedAccounts()[0]
            account_values = self.ib.accountSummary(account_id)
            
            # Extract relevant account information
            account_info = {}
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
            
            return {
                'account_value': account_info.get('account_value', 0),
                'available_cash': account_info.get('available_cash', 0),
                'positions': positions
            }
        
        except Exception as e:
            logger.error(f"Error getting portfolio: {e}")
            return None 