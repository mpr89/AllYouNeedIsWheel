"""
Option selling strategies for the auto-trader
"""

import logging
from datetime import datetime, timedelta
from ib_insync import Option, Contract, Order, TagValue, util

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('autotrader.strategies.option_sellers')


class OptionSellerBase:
    """
    Base class for option selling strategies
    """
    def __init__(self, ib_connection):
        """
        Initialize the option seller strategy
        
        Args:
            ib_connection (IBConnection): Connection to Interactive Brokers
        """
        self.ib_connection = ib_connection
        self.ib = ib_connection.get_ib()
    
    def get_option_expiration(self, days_to_expiration=30):
        """
        Get the option expiration date
        
        Args:
            days_to_expiration (int): Number of days to expiration
            
        Returns:
            str: Option expiration date in YYYYMMDD format
        """
        today = datetime.today()
        expiry_date = today + timedelta(days=days_to_expiration)
        
        # Find the closest Friday
        days_to_friday = 4 - expiry_date.weekday()  # Friday is 4
        if days_to_friday < 0:
            days_to_friday += 7
        
        expiry_date = expiry_date + timedelta(days=days_to_friday)
        return expiry_date.strftime('%Y%m%d')
    
    def get_stock_price(self, symbol):
        """
        Get the current stock price
        
        Args:
            symbol (str): Stock symbol
            
        Returns:
            float: Current stock price
        """
        if not self.ib_connection.is_connected():
            self.ib_connection.connect()
        
        stock = Contract()
        stock.symbol = symbol
        stock.secType = 'STK'
        stock.exchange = 'SMART'
        stock.currency = 'USD'
        
        self.ib.qualifyContracts(stock)
        
        # Request market data
        ticker = self.ib.reqMktData(stock)
        self.ib.sleep(0.2)  # Wait for data
        
        # Get the last price or midpoint
        if ticker.last > 0:
            price = ticker.last
        elif ticker.close > 0:
            price = ticker.close
        else:
            # Use midpoint if last and close are not available
            price = (ticker.bid + ticker.ask) / 2 if ticker.bid > 0 and ticker.ask > 0 else None
        
        # Cancel market data subscription
        self.ib.cancelMktData(stock)
        
        return price


class PutSeller(OptionSellerBase):
    """
    Strategy for selling cash-secured puts
    """
    def __init__(self, ib_connection):
        """
        Initialize the put seller strategy
        
        Args:
            ib_connection (IBConnection): Connection to Interactive Brokers
        """
        super().__init__(ib_connection)
    
    def sell_put(self, symbol, quantity=1, delta=0.3, days_to_expiration=30, limit_price=None):
        """
        Sell a cash-secured put
        
        Args:
            symbol (str): Stock symbol
            quantity (int): Number of contracts to sell
            delta (float): Target delta for the put option (0-1)
            days_to_expiration (int): Number of days to expiration
            limit_price (float, optional): Limit price for the order
            
        Returns:
            dict: Order information
        """
        logger.info(f"Selling {quantity} cash-secured put(s) for {symbol} with delta {delta}")
        
        # Get the current stock price
        stock_price = self.get_stock_price(symbol)
        if stock_price is None:
            logger.error(f"Could not get stock price for {symbol}")
            return None
        
        logger.info(f"Current price of {symbol}: ${stock_price:.2f}")
        
        # Get the expiration date
        expiration = self.get_option_expiration(days_to_expiration)
        logger.info(f"Using expiration date: {expiration}")
        
        # Calculate a reasonable strike price based on delta
        # This is a simplification - in practice, you would need to get the actual options chain
        # and find the strike with the closest delta to the target
        strike_price = round(stock_price * (1 - delta), 0)
        logger.info(f"Selected strike price: ${strike_price:.2f}")
        
        # Create the option contract
        option = Option(symbol, expiration, strike_price, 'P', 'SMART')
        self.ib.qualifyContracts(option)
        
        # Get option market data
        ticker = self.ib.reqMktData(option)
        self.ib.sleep(2)  # Wait for data
        
        # Determine limit price if not provided
        if limit_price is None:
            if ticker.bid > 0:
                limit_price = ticker.bid  # Conservative approach: sell at bid
            else:
                logger.error(f"Could not determine limit price for {symbol} put")
                self.ib.cancelMktData(option)
                return None
        
        logger.info(f"Using limit price: ${limit_price:.2f}")
        
        # Create a sell order
        order = Order()
        order.action = 'SELL'
        order.orderType = 'LMT'
        order.totalQuantity = quantity
        order.lmtPrice = limit_price
        order.transmit = True
        
        # Place the order
        trade = self.ib.placeOrder(option, order)
        self.ib.sleep(1)  # Give time for order to be processed
        
        # Cancel market data subscription
        self.ib.cancelMktData(option)
        
        # Return order details
        order_details = {
            'symbol': symbol,
            'strategy': 'sell_put',
            'expiration': expiration,
            'strike': strike_price,
            'quantity': quantity,
            'limit_price': limit_price,
            'order_id': trade.order.orderId,
            'status': trade.orderStatus.status
        }
        
        logger.info(f"Put sell order placed: {order_details}")
        return order_details


class CallSeller(OptionSellerBase):
    """
    Strategy for selling covered calls
    """
    def __init__(self, ib_connection):
        """
        Initialize the call seller strategy
        
        Args:
            ib_connection (IBConnection): Connection to Interactive Brokers
        """
        super().__init__(ib_connection)
    
    def sell_call(self, symbol, quantity=1, delta=0.3, days_to_expiration=30, limit_price=None):
        """
        Sell a covered call
        
        Args:
            symbol (str): Stock symbol
            quantity (int): Number of contracts to sell
            delta (float): Target delta for the call option (0-1)
            days_to_expiration (int): Number of days to expiration
            limit_price (float, optional): Limit price for the order
            
        Returns:
            dict: Order information
        """
        logger.info(f"Selling {quantity} covered call(s) for {symbol} with delta {delta}")
        
        # Check if we own the stock
        self._check_stock_position(symbol, quantity * 100)
        
        # Get the current stock price
        stock_price = self.get_stock_price(symbol)
        if stock_price is None:
            logger.error(f"Could not get stock price for {symbol}")
            return None
        
        logger.info(f"Current price of {symbol}: ${stock_price:.2f}")
        
        # Get the expiration date
        expiration = self.get_option_expiration(days_to_expiration)
        logger.info(f"Using expiration date: {expiration}")
        
        # Calculate a reasonable strike price based on delta
        # This is a simplification - in practice, you would need to get the actual options chain
        strike_price = round(stock_price * (1 + delta), 0)
        logger.info(f"Selected strike price: ${strike_price:.2f}")
        
        # Create the option contract
        option = Option(symbol, expiration, strike_price, 'C', 'SMART')
        self.ib.qualifyContracts(option)
        
        # Get option market data
        ticker = self.ib.reqMktData(option)
        self.ib.sleep(2)  # Wait for data
        
        # Determine limit price if not provided
        if limit_price is None:
            if ticker.bid > 0:
                limit_price = ticker.bid  # Conservative approach: sell at bid
            else:
                logger.error(f"Could not determine limit price for {symbol} call")
                self.ib.cancelMktData(option)
                return None
        
        logger.info(f"Using limit price: ${limit_price:.2f}")
        
        # Create a sell order
        order = Order()
        order.action = 'SELL'
        order.orderType = 'LMT'
        order.totalQuantity = quantity
        order.lmtPrice = limit_price
        order.transmit = True
        
        # Place the order
        trade = self.ib.placeOrder(option, order)
        self.ib.sleep(1)  # Give time for order to be processed
        
        # Cancel market data subscription
        self.ib.cancelMktData(option)
        
        # Return order details
        order_details = {
            'symbol': symbol,
            'strategy': 'sell_call',
            'expiration': expiration,
            'strike': strike_price,
            'quantity': quantity,
            'limit_price': limit_price,
            'order_id': trade.order.orderId,
            'status': trade.orderStatus.status
        }
        
        logger.info(f"Call sell order placed: {order_details}")
        return order_details
    
    def _check_stock_position(self, symbol, required_shares):
        """
        Check if we own enough shares of the stock
        
        Args:
            symbol (str): Stock symbol
            required_shares (int): Number of shares required
            
        Returns:
            bool: True if we own enough shares, False otherwise
        """
        positions = self.ib.positions()
        for position in positions:
            contract = position.contract
            if contract.symbol == symbol and contract.secType == 'STK':
                if position.position >= required_shares:
                    logger.info(f"Sufficient shares of {symbol} found: {position.position}")
                    return True
                else:
                    logger.warning(f"Insufficient shares of {symbol}: {position.position}, need {required_shares}")
                    return False
        
        logger.warning(f"No position found for {symbol}")
        return False 