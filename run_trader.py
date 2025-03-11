#!/usr/bin/env python3
import os
import sys
import argparse
import time
import logging
import datetime
from pathlib import Path
import pandas as pd
import numpy as np
import traceback

# Add the root directory to Python path
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.append(root_dir)

# Configure logging - set ib_insync to WARNING level to reduce noise
logging.getLogger('ib_insync').setLevel(logging.WARNING)
logging.getLogger('ib_insync.wrapper').setLevel(logging.WARNING)
logging.getLogger('ib_insync.client').setLevel(logging.WARNING)
logging.getLogger('ib_insync.ticker').setLevel(logging.WARNING)

# Import from autotrader modules
from autotrader.core.connection import IBConnection, Option, suppress_ib_logs
from autotrader.core.processing import SimpleOptionsStrategy, print_stock_summary, format_currency, format_percentage
from autotrader.core.utils import get_closest_friday, get_next_monthly_expiration, setup_logging, rotate_reports
from autotrader.config import Config

# Suppress ib_insync logs globally
suppress_ib_logs()

# Default configuration
DEFAULT_CONFIG = {
    'host': '127.0.0.1',
    'port': 7497,
    'client_id': 1,
    'readonly': True,
    'default_interval': 15,
    'default_strikes': 10,
    'log_level': 'INFO',
    'report_dir': 'reports',
}

def main():
    parser = argparse.ArgumentParser(description='AutoTrader - Automated Options Trading Helper')
    parser.add_argument('--config', type=str, help='Path to configuration file')
    parser.add_argument('--tickers', type=str, help='Comma-separated stock tickers to analyze')
    parser.add_argument('--interval', type=int, help='Strike price interval')
    parser.add_argument('--monthly', action='store_true', help='Use monthly options expiration')
    parser.add_argument('--strikes', type=int, help='Number of strikes to analyze on each side')
    args = parser.parse_args()
    
    # Load configuration
    config = Config(DEFAULT_CONFIG, args.config)
    
    # Setup logging
    logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    log_file = setup_logging(logs_dir, config.get('log_level', 'INFO'))
    logger = logging.getLogger('autotrader')
    
    # Make sure required directories exist
    reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), config.get('report_dir', 'reports'))
    os.makedirs(reports_dir, exist_ok=True)
    
    # Clean up old reports
    rotate_reports(reports_dir, max_reports=5)
    
    # Get tickers to analyze
    tickers = []
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(',')]
    else:
        logger.error("No tickers specified. Use --tickers=SYMBOL1,SYMBOL2")
        return 1
        
    # Determine expiration date
    use_monthly = args.monthly or config.get('use_monthly_options', False)
    if use_monthly:
        expiration_date = get_next_monthly_expiration()
    else:
        expiration_date = get_closest_friday().strftime('%Y%m%d')
        
    # Get interval and number of strikes
    interval = args.interval or config.get('default_interval', 5)
    num_strikes = args.strikes or config.get('default_strikes', 10)
    
    # Initialize connection to IB
    try:
        ib_connection = IBConnection(
            host=config.get('host', '127.0.0.1'),
            port=config.get('port', 7497),
            client_id=config.get('client_id', 1),
            readonly=config.get('readonly', True)
        )
        
        logger.debug(f"Connecting to IB at {config.get('host')}:{config.get('port')}")
        connected = ib_connection.connect()
        
        if not connected:
            logger.error("Failed to connect to Interactive Brokers. Check connection settings.")
            return 1
            
        # Initialize options strategy engine
        strategy = SimpleOptionsStrategy(ib_connection, config.to_dict())
        
        # Get portfolio data for position-aware recommendations
        portfolio = ib_connection.get_portfolio()
        if portfolio:
            logger.debug(f"Retrieved portfolio with {len(portfolio.get('positions', []))} positions")
            
            # Display portfolio summary
            print("\n=== PORTFOLIO SUMMARY ===")
            print(f"Account: {portfolio.get('account_id', 'Unknown')}")
            print(f"Available Cash: {format_currency(portfolio.get('available_cash', 0))}")
            print(f"Net Liquidation Value: {format_currency(portfolio.get('net_liquidation_value', 0))}")
            
            if portfolio.get('positions'):
                print("\nPositions:")
                try:
                    for position in portfolio.get('positions', []):
                        if isinstance(position, dict) and 'contract' in position and hasattr(position['contract'], 'symbol'):
                            ticker = position['contract'].symbol
                            secType = position['contract'].secType
                            
                            if secType == 'STK':
                                shares = position['position']
                                avg_cost = position.get('avgCost', 0)
                                market_value = position.get('marketValue', 0)
                                pnl = position.get('unrealizedPNL', 0)
                                
                                print(f"  {ticker}: {shares} shares @ {format_currency(avg_cost)}/share, " + 
                                      f"Value: {format_currency(market_value)}, " + 
                                      f"P&L: {format_currency(pnl)} ({format_percentage(pnl/market_value) if market_value else 'N/A'})")
                        else:
                            logger.warning(f"Unexpected position format: {position}")
                except Exception as e:
                    logger.error(f"Error: {str(e)}")
                    logger.error(traceback.format_exc())
            print()
        else:
            logger.warning("Could not retrieve portfolio data. Proceeding with market analysis only.")
            
        # Process each ticker
        all_results = []
        for ticker in tickers:
            logger.debug(f"Processing {ticker} with expiration {expiration_date}")
            
            # Process the stock with our strategy engine
            result = strategy.process_stock(ticker, portfolio)
            
            if result:
                all_results.append(result)
                
                # Print summary to console
                print(f"\n=== {ticker} OPTIONS SUMMARY ===")
                print(f"{ticker} Price: ${result['price']:.2f}")
                
                # Print position details if available
                if result['position']['size'] != 0:
                    print("\nCURRENT POSITION:")
                    print(f"  Shares: {result['position']['size']}")
                    print(f"  Average Cost: ${result['position']['avg_cost']:.2f}")
                    print(f"  Market Value: ${result['position']['market_value']:.2f}")
                    print(f"  Unrealized P&L: ${result['position']['unrealized_pnl']:.2f}")
                
                # Print recommendation
                print("\nRECOMMENDED STRATEGY:")
                rec = result['recommendation']
                option_type = rec['type']
                strike = rec['strike']
                expiration = rec['expiration']
                action = rec['action']
                
                option_data = result['options']['put'] if option_type == 'PUT' else result['options']['call']
                
                print(f"{action} {option_type}  @ Strike ${strike:.2f} " + 
                      (f"({(strike/result['price'] - 1)*100:.0f}%)" if option_type == 'CALL' else f"({(strike/result['price'] - 1)*100:.0f}%)"))
                
                # Handle None values in option data
                bid = option_data.get('bid', 0) or 0
                ask = option_data.get('ask', 0) or 0
                last = option_data.get('last', 0) or 0
                print(f"  Bid: ${bid:.2f}, Ask: ${ask:.2f}, Last: ${last:.2f}")
                
                # Print earnings estimate if available
                if rec.get('earnings'):
                    earnings = rec['earnings']
                    print(f"  Potential Earnings ({earnings['strategy']}):")
                    print(f"  Max Contracts: {earnings['max_contracts']}")
                    print(f"  Premium per Contract: ${earnings['premium_per_contract']:.2f}")
                    print(f"  Total Premium: ${earnings['total_premium']:.2f}")
                    
                    if 'return_on_cash' in earnings:
                        print(f"  Return on Cash: {earnings['return_on_cash']:.2f}%")
                    elif 'return_on_capital' in earnings:
                        print(f"  Return on Capital: {earnings['return_on_capital']:.2f}%")
                
                # Print alternative strategy if available
                if 'alternative' in rec:
                    alt = rec['alternative']
                    alt_type = alt['type']
                    alt_strike = alt['strike']
                    alt_action = alt['action']
                    
                    alt_option_data = result['options']['put'] if alt_type == 'PUT' else result['options']['call']
                    
                    print(f"{alt_action} {alt_type}  @ Strike ${alt_strike:.2f} " + 
                          (f"({(alt_strike/result['price'] - 1)*100:.0f}%)" if alt_type == 'CALL' else f"({(alt_strike/result['price'] - 1)*100:.0f}%)"))
                    
                    # Handle None values in option data
                    alt_bid = alt_option_data.get('bid', 0) or 0
                    alt_ask = alt_option_data.get('ask', 0) or 0
                    alt_last = alt_option_data.get('last', 0) or 0
                    print(f"  Bid: ${alt_bid:.2f}, Ask: ${alt_ask:.2f}, Last: ${alt_last:.2f}")
            else:
                logger.error(f"Failed to process {ticker}")
        
        # Generate HTML report
        if all_results:
            report_file = os.path.join(reports_dir, f"options_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
            strategy.generate_html_report(all_results, report_file)
            logger.debug(f"Report generated: {report_file}")
            
            # Clean up old reports
            old_reports = sorted(Path(reports_dir).glob("options_report_*.html"))
            if len(old_reports) > 5:  # Keep only the 5 most recent reports
                for old_report in old_reports[:-5]:
                    logger.debug(f"Deleted old report file: {old_report}")
                    old_report.unlink()
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        logger.error(traceback.format_exc())
        return 1
    finally:
        if 'ib_connection' in locals() and ib_connection.is_connected():
            ib_connection.disconnect()
            
    return 0

if __name__ == "__main__":
    sys.exit(main()) 