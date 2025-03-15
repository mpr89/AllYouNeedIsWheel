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
        """Create necessary tables with flattened structure"""
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
        
        # Create orders table with flattened structure 
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
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
                
                -- Price data
                bid REAL DEFAULT 0,
                ask REAL DEFAULT 0,
                last REAL DEFAULT 0,
                
                -- Greeks
                delta REAL DEFAULT 0,
                gamma REAL DEFAULT 0,
                theta REAL DEFAULT 0,
                vega REAL DEFAULT 0,
                implied_volatility REAL DEFAULT 0,
                
                -- Market data
                open_interest INTEGER DEFAULT 0,
                volume INTEGER DEFAULT 0,
                is_mock BOOLEAN DEFAULT 0,
                
                -- Earnings data
                earnings_max_contracts INTEGER DEFAULT 0,
                earnings_premium_per_contract REAL DEFAULT 0,
                earnings_total_premium REAL DEFAULT 0,
                earnings_return_on_cash REAL DEFAULT 0,
                earnings_return_on_capital REAL DEFAULT 0,
                
                -- Execution data
                ib_order_id TEXT,
                ib_status TEXT,
                filled INTEGER DEFAULT 0,
                remaining INTEGER DEFAULT 0,
                avg_fill_price REAL DEFAULT 0
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
        Save an option order to the database using flattened structure
        
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
            action = order_data.get('action', 'SELL')  # Default action is sell for options
            strike = order_data.get('strike', 0)
            expiration = order_data.get('expiration', '')
            premium = order_data.get('premium', 0)
            quantity = order_data.get('quantity', 1)
            
            # Extract pricing data
            bid = order_data.get('bid', 0)
            ask = order_data.get('ask', 0)
            last = order_data.get('last', 0)
            
            # Extract greeks
            delta = order_data.get('delta', 0)
            gamma = order_data.get('gamma', 0)
            theta = order_data.get('theta', 0)
            vega = order_data.get('vega', 0)
            implied_volatility = order_data.get('implied_volatility', 0)
            
            # Extract market data
            open_interest = order_data.get('open_interest', 0)
            volume = order_data.get('volume', 0)
            is_mock = order_data.get('is_mock', False)
            
            # Extract earnings data
            earnings_max_contracts = order_data.get('earnings_max_contracts', 0)
            earnings_premium_per_contract = order_data.get('earnings_premium_per_contract', 0)
            earnings_total_premium = order_data.get('earnings_total_premium', 0)
            earnings_return_on_cash = order_data.get('earnings_return_on_cash', 0)
            earnings_return_on_capital = order_data.get('earnings_return_on_capital', 0)
            
            # Insert order with all fields using the flattened structure
            cursor.execute('''
                INSERT INTO orders 
                (timestamp, ticker, option_type, action, strike, expiration, premium, quantity, 
                 bid, ask, last, delta, gamma, theta, vega, implied_volatility, 
                 open_interest, volume, is_mock,
                 earnings_max_contracts, earnings_premium_per_contract, 
                 earnings_total_premium, earnings_return_on_cash, 
                 earnings_return_on_capital, status, executed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                timestamp, ticker, option_type, action, strike, expiration, premium, quantity, 
                bid, ask, last, delta, gamma, theta, vega, implied_volatility, 
                open_interest, volume, is_mock,
                earnings_max_contracts, earnings_premium_per_contract, 
                earnings_total_premium, earnings_return_on_cash, 
                earnings_return_on_capital, 'pending', False
            ))
            
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
        return self.get_orders(executed=executed, limit=limit)
    
    def update_order_status(self, order_id, status, executed=False, execution_details=None):
        """
        Update the status of an order
        
        Args:
            order_id (int): ID of the order to update
            status (str): New status
            executed (bool): Whether the order has been executed
            execution_details (dict): Optional details about the execution
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Start with basic update query
            update_query = '''
                UPDATE orders
                SET status = ?, executed = ?
                WHERE id = ?
            '''
            params = [status, executed, order_id]
            
            # If we have execution details, update those fields too
            if execution_details and isinstance(execution_details, dict):
                set_clauses = []
                
                # Map execution details to database fields
                field_mappings = {
                    'ib_order_id': 'ib_order_id',
                    'ib_status': 'ib_status',
                    'filled': 'filled',
                    'remaining': 'remaining',
                    'avg_fill_price': 'avg_fill_price',
                    'is_mock': 'is_mock'
                }
                
                # Check for each field in the mapping
                for api_field, db_field in field_mappings.items():
                    if api_field in execution_details:
                        set_clauses.append(f"{db_field} = ?")
                        params.append(execution_details[api_field])
                
                # If we have additional fields to set, add them to the query
                if set_clauses:
                    # Reconstruct the query with the additional fields
                    update_query = '''
                        UPDATE orders
                        SET status = ?, executed = ?, {}
                        WHERE id = ?
                    '''.format(', '.join(set_clauses))
            
            # Execute the query
            cursor.execute(update_query, params)
            conn.commit()
            conn.close()
            
            return True
        except Exception as e:
            print(f"Error updating order status: {str(e)}")
            return False
            
    def delete_order(self, order_id):
        """
        Delete an order from the database
        
        Args:
            order_id (int): ID of the order to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM orders
                WHERE id = ?
            ''', (order_id,))
            
            # Check if any rows were affected
            affected_rows = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            # Return True if at least one row was deleted
            return affected_rows > 0
        except Exception as e:
            print(f"Error deleting order: {str(e)}")
            return False
            
    def get_order(self, order_id):
        """
        Get a specific order by ID
        
        Args:
            order_id (int): ID of the order to retrieve
            
        Returns:
            dict: Order data or None if not found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # This enables column access by name
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM orders
                WHERE id = ?
            ''', (order_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
                
            # Convert row to dictionary
            order = dict(row)
            return order
            
        except Exception as e:
            print(f"Error getting order: {str(e)}")
            return None
            
    def get_orders(self, status=None, executed=None, ticker=None, limit=50):
        """
        Get orders from the database with flexible filtering
        
        Args:
            status (str): Filter by status (e.g., 'pending', 'completed', 'cancelled')
            executed (bool): Filter by executed flag
            ticker (str): Filter by ticker symbol
            limit (int): Maximum number of orders to return
            
        Returns:
            list: List of order dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # This enables column access by name
            cursor = conn.cursor()
            
            # Build the query based on filters
            query = "SELECT * FROM orders WHERE 1=1"
            params = []
            
            if status is not None:
                query += " AND status = ?"
                params.append(status)
                
            if executed is not None:
                query += " AND executed = ?"
                params.append(executed)
                
            if ticker is not None:
                query += " AND ticker = ?"
                params.append(ticker)
                
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            
            rows = cursor.fetchall()
            conn.close()
            
            # Convert rows to dictionaries
            orders = []
            for row in rows:
                order = dict(row)
                orders.append(order)
                
            return orders
        except Exception as e:
            print(f"Error getting orders: {str(e)}")
            return [] 