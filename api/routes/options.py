"""
Options API routes
"""

from flask import Blueprint, request, jsonify
from api.services.options_service import OptionsService
import traceback
import logging
import time

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
    tickers = request.args.get('tickers')
    otm_percentage = float(request.args.get('otm_percentage', 10))

    options_service = OptionsService(real_time=use_real_time)
    
     # Call the service with appropriate parameters
    result = options_service.get_otm_options(
        tickers=tickers,
        otm_percentage=otm_percentage
    )
    
    return jsonify(result)
       