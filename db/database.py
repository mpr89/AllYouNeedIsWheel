"""
Database module for SQLite logging of trades
"""

import sqlite3
import os
import json
from datetime import datetime
from pathlib import Path


class TradeLogger:
    """
    Class for logging trades to SQLite database
    """
    def __init__(self, db_path=None):
        """
        Initialize the trade logger
        
        Args:
            db_path (str, optional): Path to the SQLite database. 
                                    If None, creates 'trades.db' in current directory.
        """
        if db_path is None:
            db_path = Path.cwd() / 'trades.db'
        else:
            db_path = Path(db_path)
            
        self.db_path = db_path
        self._create_tables_if_not_exist()
    
    def _create_tables_if_not_exist(self):
        """Create necessary tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create trades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                contract_type TEXT NOT NULL,
                action TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                expiration TEXT,
                strike REAL,
                order_id TEXT,
                commission REAL,
                details TEXT,
                strategy TEXT
            )
        ''')
        
        # Create a table for backtesting results
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS backtest_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                strategy TEXT NOT NULL,
                params TEXT,
                start_date TEXT,
                end_date TEXT,
                initial_capital REAL,
                final_capital REAL,
                profit_loss REAL,
                max_drawdown REAL,
                win_rate REAL,
                details TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def log_trade(self, symbol, contract_type, action, quantity, price, 
                 expiration=None, strike=None, order_id=None, commission=0.0,
                 details=None, strategy=None):
        """
        Log a trade to the database
        
        Args:
            symbol (str): The ticker symbol
            contract_type (str): 'option' or 'stock'
            action (str): 'buy' or 'sell'
            quantity (int): Number of contracts/shares
            price (float): Execution price
            expiration (str, optional): Option expiration date
            strike (float, optional): Option strike price
            order_id (str, optional): Order ID from broker
            commission (float, optional): Commission paid
            details (dict, optional): Additional trade details
            strategy (str, optional): Strategy name
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = datetime.now().isoformat()
        
        if details is not None and isinstance(details, dict):
            details = json.dumps(details)
        
        cursor.execute('''
            INSERT INTO trades (
                timestamp, symbol, contract_type, action, quantity, price, 
                expiration, strike, order_id, commission, details, strategy
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            timestamp, symbol, contract_type, action, quantity, price,
            expiration, strike, order_id, commission, details, strategy
        ))
        
        conn.commit()
        conn.close()
    
    def log_backtest(self, strategy, params, start_date, end_date, 
                    initial_capital, final_capital, profit_loss, 
                    max_drawdown, win_rate, details=None):
        """
        Log backtest results to the database
        
        Args:
            strategy (str): Strategy name
            params (dict): Strategy parameters
            start_date (str): Start date of backtest
            end_date (str): End date of backtest
            initial_capital (float): Initial capital
            final_capital (float): Final capital
            profit_loss (float): Profit/loss
            max_drawdown (float): Maximum drawdown
            win_rate (float): Win rate
            details (dict, optional): Additional details
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = datetime.now().isoformat()
        
        if params is not None and isinstance(params, dict):
            params = json.dumps(params)
            
        if details is not None and isinstance(details, dict):
            details = json.dumps(details)
        
        cursor.execute('''
            INSERT INTO backtest_results (
                timestamp, strategy, params, start_date, end_date,
                initial_capital, final_capital, profit_loss, 
                max_drawdown, win_rate, details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            timestamp, strategy, params, start_date, end_date,
            initial_capital, final_capital, profit_loss,
            max_drawdown, win_rate, details
        ))
        
        conn.commit()
        conn.close()
    
    def get_trades(self, limit=100, symbol=None, strategy=None):
        """
        Get trades from database
        
        Args:
            limit (int, optional): Maximum number of trades to return
            symbol (str, optional): Filter by symbol
            strategy (str, optional): Filter by strategy
            
        Returns:
            list: List of trades
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM trades"
        params = []
        
        if symbol or strategy:
            query += " WHERE"
            if symbol:
                query += " symbol = ?"
                params.append(symbol)
            if strategy:
                if symbol:
                    query += " AND"
                query += " strategy = ?"
                params.append(strategy)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        result = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return result
    
    def get_backtest_results(self, limit=100, strategy=None):
        """
        Get backtest results from database
        
        Args:
            limit (int, optional): Maximum number of results to return
            strategy (str, optional): Filter by strategy
            
        Returns:
            list: List of backtest results
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM backtest_results"
        params = []
        
        if strategy:
            query += " WHERE strategy = ?"
            params.append(strategy)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        result = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return result

class OptionsDatabase:
    """
    Class for logging options recommendations to SQLite database
    """
    def __init__(self, db_path=None):
        """
        Initialize the options database
        
        Args:
            db_path (str, optional): Path to the SQLite database. 
                                    If None, creates 'options.db' in current directory.
        """
        if db_path is None:
            db_path = Path.cwd() / 'options.db'
        else:
            db_path = Path(db_path)
            
        self.db_path = db_path
        self._create_tables_if_not_exist()
    
    def _create_tables_if_not_exist(self):
        """Create necessary tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create recommendations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                ticker TEXT NOT NULL,
                option_type TEXT NOT NULL,
                action TEXT NOT NULL,
                strike REAL NOT NULL,
                expiration TEXT NOT NULL,
                premium REAL,
                details TEXT
            )
        ''')
        
        # Create pending orders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pending_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                ticker TEXT NOT NULL,
                option_type TEXT NOT NULL,
                action TEXT NOT NULL,
                strike REAL NOT NULL,
                expiration TEXT NOT NULL,
                premium REAL,
                quantity INTEGER DEFAULT 1,
                status TEXT DEFAULT 'pending',
                executed BOOLEAN DEFAULT 0,
                details TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def save_recommendation(self, recommendation):
        """
        Save an option recommendation to the database
        
        Args:
            recommendation (dict): Option recommendation data
            
        Returns:
            int: ID of the inserted record
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Extract data from recommendation
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ticker = recommendation.get('ticker', '')
            option_type = recommendation.get('type', '')
            action = recommendation.get('action', '')
            strike = recommendation.get('strike', 0)
            expiration = recommendation.get('expiration', '')
            
            # Get premium if available
            premium = 0
            if 'earnings' in recommendation and recommendation['earnings']:
                premium = recommendation['earnings'].get('premium_per_contract', 0)
                
            # Convert recommendation to JSON for details
            details = json.dumps(recommendation)
            
            # Insert into database
            cursor.execute('''
                INSERT INTO recommendations 
                (timestamp, ticker, option_type, action, strike, expiration, premium, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (timestamp, ticker, option_type, action, strike, expiration, premium, details))
            
            record_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return record_id
        except Exception as e:
            print(f"Error saving recommendation: {str(e)}")
            return None
    
    def save_order(self, order_data):
        """
        Save an option order to the database
        
        Args:
            order_data (dict): Option order data
            
        Returns:
            int: ID of the inserted record
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Extract data from order
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ticker = order_data.get('ticker', '')
            option_type = order_data.get('option_type', '')
            action = 'SELL'  # Default action is sell for options
            strike = order_data.get('strike', 0)
            expiration = order_data.get('expiration', '')
            premium = order_data.get('premium', 0)
            quantity = order_data.get('quantity', 1)
            
            # Convert order_data to JSON for details
            details = json.dumps(order_data)
            
            # Insert into database
            cursor.execute('''
                INSERT INTO pending_orders 
                (timestamp, ticker, option_type, action, strike, expiration, premium, quantity, status, executed, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (timestamp, ticker, option_type, action, strike, expiration, premium, quantity, 'pending', False, details))
            
            record_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return record_id
        except Exception as e:
            print(f"Error saving order: {str(e)}")
            return None
            
    
    def get_pending_orders(self, executed=False, limit=50):
        """
        Get pending orders from the database
        
        Args:
            executed (bool): Whether to return executed orders (True) or pending orders (False)
            limit (int): Maximum number of orders to return
            
        Returns:
            list: List of order dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # This enables column access by name
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM pending_orders
                WHERE executed = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (executed, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            # Convert rows to dictionaries
            orders = []
            for row in rows:
                order = dict(row)
                # Parse details JSON if available
                if 'details' in order and order['details']:
                    try:
                        order['details'] = json.loads(order['details'])
                    except:
                        pass
                orders.append(order)
                
            return orders
        except Exception as e:
            print(f"Error getting pending orders: {str(e)}")
            return []
    
    def update_order_status(self, order_id, status, executed=False):
        """
        Update the status of an order
        
        Args:
            order_id (int): ID of the order to update
            status (str): New status
            executed (bool): Whether the order has been executed
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE pending_orders
                SET status = ?, executed = ?
                WHERE id = ?
            ''', (status, executed, order_id))
            
            conn.commit()
            conn.close()
            
            return True
        except Exception as e:
            print(f"Error updating order status: {str(e)}")
            return False 