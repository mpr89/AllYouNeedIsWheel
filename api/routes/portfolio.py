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
    """
    try:
        results = portfolio_service.get_positions()
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/performance', methods=['GET'])
def get_performance():
    """
    Get the portfolio performance metrics
    """
    try:
        results = portfolio_service.get_performance_metrics()
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500 