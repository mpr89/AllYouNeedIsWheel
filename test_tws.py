#!/usr/bin/env python3
"""
Test script to check TWS API connection
"""

import sys
import time
import random
from core.logging_config import get_logger
from core.connection import IBConnection

# Configure logging
logger = get_logger('test_tws', 'tws')

def main():
    """
    Test TWS API connection
    """
    # Try both common TWS ports
    ports = [7497, 7496]
    connection_successful = False
    
    for port in ports:
        # Generate a unique client ID
        unique_client_id = int(time.time() % 10000) + random.randint(1000, 9999)
        logger.info(f"Creating TWS connection with client ID: {unique_client_id} on port {port}")
        
        # Create connection
        conn = IBConnection(
            host='127.0.0.1',
            port=port,
            client_id=unique_client_id,
            timeout=10,  # Shorter timeout
            readonly=True
        )
        
        # Connect to TWS
        logger.info(f"Connecting to TWS on port {port}...")
        if conn.connect():
            logger.info(f"Connected to TWS on port {port}")
            connection_successful = True
            
            # Test get_stock_price
            ticker = "AAPL"
            logger.info(f"Getting stock price for {ticker}...")
            price = conn.get_stock_price(ticker)
            logger.info(f"Stock price for {ticker}: {price}")
            
            # Test get_stock_data if it exists
            logger.info(f"Getting stock data for {ticker}...")
            if hasattr(conn, 'get_stock_data'):
                stock_data = conn.get_stock_data(ticker)
                logger.info(f"Stock data for {ticker}: {stock_data}")
            else:
                logger.error("get_stock_data method doesn't exist")
            
            # Disconnect
            logger.info("Disconnecting from TWS...")
            conn.disconnect()
            logger.info("Disconnected from TWS")
            
            # We found a working connection, no need to try other ports
            break
        else:
            logger.error(f"Failed to connect to TWS on port {port}")
    
    if not connection_successful:
        logger.error("Could not connect to TWS on any port")
        sys.exit(1)
    else:
        logger.info("Connection test completed successfully")

if __name__ == '__main__':
    main() 