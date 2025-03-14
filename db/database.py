"""
Database module for SQLite logging of trades
"""

import sqlite3
import os
import json
from datetime import datetime
from pathlib import Path

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