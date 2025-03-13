"""
Options API routes
"""

from flask import Blueprint, request, jsonify
from api.services.options_service import OptionsService

bp = Blueprint('options', __name__, url_prefix='/api/options')
options_service = OptionsService()

        

     
@bp.route('/otm')
def otm_options():
    """Get options based on OTM percentage."""
    try:
        import inspect
        import traceback
        import logging
        logger = logging.getLogger('api.routes.options')
        
        logger.info("OTM options endpoint called")
        
        # Get and log all request parameters
        tickers = request.args.get('tickers')
        otm_percentage = request.args.get('otm', 10, type=float)
        monthly = request.args.get('monthly', 'false').lower() == 'true'
        real_time = request.args.get('real_time', 'false').lower() == 'true'
        options_only = request.args.get('options_only', 'false').lower() == 'true'
        for_calls = request.args.get('calls', 'true').lower() == 'true'
        for_puts = request.args.get('puts', 'true').lower() == 'true'
        
        logger.info(f"Request params: tickers={tickers}, otm={otm_percentage}, "
                   f"monthly={monthly}, real_time={real_time}, options_only={options_only}, "
                   f"for_calls={for_calls}, for_puts={for_puts}")
        
        if tickers:
            tickers = tickers.split(',')
            logger.info(f"Parsed tickers: {tickers}")
        
        # Create options service
        logger.info("Creating OptionsService instance")
        try:
            options_service = OptionsService(real_time=real_time)
            logger.info("OptionsService instance created successfully")
        except Exception as svc_err:
            stack = traceback.format_exc()
            logger.error(f"Error creating OptionsService: {str(svc_err)}\n{stack}")
            return jsonify({'error': f"Service initialization error: {str(svc_err)}"}), 500
        
        # Call get_otm_options with detailed error handling
        logger.info("Calling get_otm_options")
        try:
            result = options_service.get_otm_options(
                tickers=tickers,
                otm_percentage=otm_percentage,
                for_calls=for_calls,
                for_puts=for_puts,
                monthly=monthly,
                options_only=options_only
            )
            logger.info("get_otm_options completed successfully")
        except Exception as opt_err:
            stack = traceback.format_exc()
            logger.error(f"Error in get_otm_options: {str(opt_err)}\n{stack}")
            return jsonify({'error': f"Options retrieval error: {str(opt_err)}"}), 500
        
        # Return the result
        return jsonify(result)
        
    except Exception as e:
        stack = traceback.format_exc()
        print(f"Unhandled error in OTM options endpoint: {str(e)}\n{stack}")
        return jsonify({'error': str(e)}), 500 