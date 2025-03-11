#!/usr/bin/env python
"""
Example of a simple options trading strategy using Auto-Trader
"""

import asyncio
import logging
from ib_insync import IB, Option, Contract, util
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('autotrader')

async def run_strategy():
    """Run a simple options trading strategy"""
    # Connect to Interactive Brokers
    ib = IB()
    try:
        # In paper trading mode
        await ib.connectAsync('127.0.0.1', 7497, clientId=1)
        logger.info("Connected to IB")
        
        # Define the underlying stock
        stock = Contract()
        stock.symbol = 'AAPL'
        stock.secType = 'STK'
        stock.exchange = 'SMART'
        stock.currency = 'USD'
        
        # Request market data for the stock
        ib.qualifyContracts(stock)
        stock_ticker = ib.reqMktData(stock)
        await asyncio.sleep(2)  # Wait for market data to arrive
        
        logger.info(f"Current price of {stock.symbol}: ${stock_ticker.last:.2f}")
        
        # Calculate the nearest expiration Friday
        today = datetime.now()
        days_until_friday = (4 - today.weekday()) % 7
        if days_until_friday == 0 and today.hour >= 16:  # After market close on Friday
            days_until_friday = 7
        next_friday = today + timedelta(days=days_until_friday)
        expiration = next_friday.strftime('%Y%m%d')
        
        # Define a call option slightly out of the money
        call_strike = round(stock_ticker.last * 1.05 / 5) * 5  # Round to nearest $5
        call_option = Option(stock.symbol, expiration, call_strike, 'C', 'SMART')
        ib.qualifyContracts(call_option)
        
        # Get market data for the option
        option_ticker = ib.reqMktData(call_option)
        await asyncio.sleep(2)
        
        logger.info(f"Call option {stock.symbol} {expiration} ${call_strike} ask: ${option_ticker.ask:.2f}")
        
        # Here you would implement your actual trading logic
        # For example:
        # - Sell a cash-secured put if you're bullish
        # - Create a bull call spread
        # - Set up an iron condor
        
        logger.info("Strategy execution completed")
        
    except Exception as e:
        logger.error(f"Error in strategy execution: {e}")
    finally:
        ib.disconnect()
        logger.info("Disconnected from IB")

if __name__ == '__main__':
    asyncio.run(run_strategy()) 