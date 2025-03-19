import sqlite3
from log import logger

class OptionsDatabase:
    def update_order_quantity(self, order_id, quantity):
        """
        Update the quantity of a specific order
        
        Args:
            order_id (int): ID of the order to update
            quantity (int): New quantity value
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Update the order quantity
                cursor.execute("""
                    UPDATE option_orders 
                    SET quantity = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (quantity, order_id))
                
                # Check if any rows were updated
                if cursor.rowcount == 0:
                    logger.error(f"No order found with ID {order_id}")
                    return False
                    
                conn.commit()
                logger.info(f"Successfully updated quantity to {quantity} for order {order_id}")
                return True
                
        except sqlite3.Error as e:
            logger.error(f"Database error updating order quantity: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error updating order quantity: {str(e)}")
            return False 