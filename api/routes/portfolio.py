"""
Portfolio API routes
"""

from flask import Blueprint, request, jsonify
from api.services.portfolio_service import PortfolioService

bp = Blueprint('portfolio', __name__, url_prefix='/api/portfolio')
portfolio_service = PortfolioService()

@bp.route('/', methods=['GET'])
def get_portfolio():
    """
    Get the current portfolio information
    """
    try:
        results = portfolio_service.get_portfolio_summary()
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/positions', methods=['GET'])
def get_positions():
    """
    Get the current portfolio positions
    
    Query Parameters:
        type: Filter by position type (STK, OPT). If not provided, returns all positions.
    """
    try:
        # Get the position_type from query parameters
        position_type = request.args.get('type')
        # Validate position_type
        if position_type and position_type not in ['STK', 'OPT']:
            return jsonify({'error': 'Invalid position type. Supported types: STK, OPT'}), 400
            
        results = portfolio_service.get_positions(position_type)
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/weekly-income', methods=['GET'])
def get_weekly_income():
    """
    Get option positions expiring next Friday and calculate potential income
    """
    try:
        results = portfolio_service.get_weekly_option_income()
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
