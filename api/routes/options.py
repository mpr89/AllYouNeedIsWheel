"""
Options API routes
"""

from flask import Blueprint, request, jsonify, current_app
from api.services.options_service import OptionsService
import traceback
import logging
import time
from core.connection import IBConnection, suppress_ib_logs
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
            
        # Try to get the order first to ensure it exists
        order = db.get_order(order_id)
        if not order:
            logger.error(f"Order with ID {order_id} not found")
            return jsonify({"error": f"Order with ID {order_id} not found"}), 404
            
        # Check if order is in executable state
        if order['status'] != 'pending':
            logger.error(f"Cannot execute order with status '{order['status']}'")
            return jsonify({"error": f"Cannot execute order with status '{order['status']}'. Only 'pending' orders can be executed."}), 400
            
        # Get connection to TWS
        connection_config = current_app.config.get('connection_config', {})
        suppress_ib_logs()
        
        ib_conn = IBConnection(
            host=connection_config.get('host', '127.0.0.1'),
            port=connection_config.get('port', 7497),
            client_id=connection_config.get('client_id', 1),
            readonly=connection_config.get('readonly', False)
        )
        
        # Connect to TWS
        if not ib_conn.connect():
            logger.error("Failed to connect to TWS")
            return jsonify({"error": "Failed to connect to TWS"}), 500
            
        # Parse order details
        details = order.get('details', {})
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except:
                details = {}
                
        # Extract order information
        symbol = details.get('symbol', order.get('ticker'))
        if not symbol:
            ib_conn.disconnect()
            return jsonify({"error": "Missing symbol in order details"}), 400
            
        quantity = int(order.get('quantity', 0))
        if quantity <= 0:
            ib_conn.disconnect()
            return jsonify({"error": "Invalid quantity"}), 400
            
        order_type = details.get('order_type', 'LMT')
        action = details.get('action', 'SELL')  # Default to SELL for options
        
        # Extract option details
        expiry = details.get('expiry')
        strike = details.get('strike')
        option_type = details.get('option_type')
        
        if not all([expiry, strike, option_type]):
            ib_conn.disconnect()
            return jsonify({"error": "Missing option details (expiry, strike, or option_type)"}), 400
            
        # Get limit price
        limit_price = details.get('limit_price')
        if order_type.upper() == 'LMT' and not limit_price:
            ib_conn.disconnect()
            return jsonify({"error": "Missing limit price for limit order"}), 400
            
        # Create contract
        contract = ib_conn.create_option_contract(
            symbol=symbol,
            expiry=expiry,
            strike=float(strike),
            option_type=option_type
        )
        
        if not contract:
            ib_conn.disconnect()
            return jsonify({"error": "Failed to create option contract"}), 500
            
        # Create order
        ib_order = ib_conn.create_order(
            action=action,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price
        )
        
        if not ib_order:
            ib_conn.disconnect()
            return jsonify({"error": "Failed to create order"}), 500
            
        # Place order
        result = ib_conn.place_order(contract, ib_order)
        ib_conn.disconnect()
        
        if not result:
            return jsonify({"error": "Failed to place order"}), 500
            
        # Update order status in database
        execution_details = {
            "ib_order_id": result.get('order_id'),
            "ib_status": result.get('status'),
            "filled": result.get('filled'),
            "remaining": result.get('remaining'),
            "avg_fill_price": result.get('avg_fill_price'),
            "is_mock": result.get('is_mock', False)
        }
        
        # Update order status to 'processing'
        db.update_order_status(
            order_id=order_id,
            status="processing",
            execution_details=execution_details
        )
        
        logger.info(f"Order with ID {order_id} sent to TWS, IB order ID: {result.get('order_id')}")
        return jsonify({
            "success": True,
            "message": "Order sent to TWS",
            "order_id": order_id,
            "ib_order_id": result.get('order_id'),
            "status": "processing",
            "execution_details": execution_details
        }), 200
            
    except Exception as e:
        logger.error(f"Error executing order: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500
       