"""
Options API routes
"""

from flask import Blueprint, request, jsonify, current_app
from api.services.options_service import OptionsService
import traceback
import logging
import time
import json

# Set up logger
logger = logging.getLogger('api.routes.options')

bp = Blueprint('options', __name__, url_prefix='/api/options')
options_service = OptionsService()

# Market status is now checked directly in the route functions

# Helper function to check market status with better error handling
@bp.route('/otm', methods=['GET'])
def otm_options():
    """
    Get option data based on OTM percentage from current price.
    """
    # Get parameters from request
    ticker = request.args.get('tickers')
    otm_percentage = float(request.args.get('otm', 10))
    
    # Use the existing module-level instance instead of creating a new one
    # Call the service with appropriate parameters
    result = options_service.get_otm_options(
        ticker=ticker,
        otm_percentage=otm_percentage
    )
    
    return jsonify(result)

@bp.route('/order', methods=['POST'])
def save_order():
    """
    Save an option order to the database
    """
    try:
        # Get order data from request
        order_data = request.json
        if not order_data:
            return jsonify({"error": "No order data provided"}), 400
            
        # Validate required fields
        required_fields = ['ticker', 'option_type', 'strike', 'expiration']
        for field in required_fields:
            if field not in order_data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Save order to database
        order_id = options_service.db.save_order(order_data)
        
        if order_id:
            return jsonify({"success": True, "order_id": order_id}), 201
        else:
            return jsonify({"error": "Failed to save order"}), 500
    except Exception as e:
        logger.error(f"Error saving order: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@bp.route('/pending-orders', methods=['GET'])
def get_pending_orders():
    """
    Get pending option orders from the database
    """
    try:
        # Get executed parameter (optional)
        executed = request.args.get('executed', 'false').lower() == 'true'
        
        # Get pending orders from database
        orders = options_service.db.get_pending_orders(executed=executed)
        
        return jsonify({"orders": orders})
    except Exception as e:
        logger.error(f"Error getting pending orders: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@bp.route('/order/<int:order_id>', methods=['DELETE'])
def delete_order(order_id):
    """
    Delete/cancel an order from the database.
    
    Args:
        order_id (int): ID of the order to delete
        
    Returns:
        JSON response with success status
    """
    logger.info(f"DELETE /order/{order_id} request received")
    
    try:
        # Get the database instance
        db = current_app.config.get('database')
        if not db:
            logger.error("Database not initialized")
            return jsonify({"error": "Database not initialized"}), 500
            
        # Try to get the order first to ensure it exists
        order = db.get_order(order_id)
        if not order:
            logger.error(f"Order with ID {order_id} not found")
            return jsonify({"error": f"Order with ID {order_id} not found"}), 404
            
        # Delete the order
        success = db.delete_order(order_id)
        
        if success:
            logger.info(f"Order with ID {order_id} successfully deleted")
            return jsonify({"success": True, "message": f"Order with ID {order_id} deleted"}), 200
        else:
            logger.error(f"Failed to delete order with ID {order_id}")
            return jsonify({"error": "Failed to delete order"}), 500
            
    except Exception as e:
        logger.error(f"Error deleting order: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@bp.route('/execute/<int:order_id>', methods=['POST'])
def execute_order(order_id):
    """
    Execute an order by sending it to TWS.
    
    Args:
        order_id (int): ID of the order to execute
        
    Returns:
        JSON response with execution details
    """
    logger.info(f"POST /execute/{order_id} request received")
    
    try:
        # Get the database instance
        db = current_app.config.get('database')
        if not db:
            logger.error("Database not initialized")
            return jsonify({"error": "Database not initialized"}), 500
            
        # Use the options service to execute the order
        response, status_code = options_service.execute_order(order_id, db)
        
        # Return the response from the service
        return jsonify(response), status_code
            
    except Exception as e:
        logger.error(f"Error executing order: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500
       