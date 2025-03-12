#!/usr/bin/env python3
"""
Auto-Trader API Server
Script to start the Auto-Trader API server using gunicorn
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('autotrader.server')

def main():
    """
    Start the API server using gunicorn
    """
    try:
        # Get port from environment variable or use default
        port = os.environ.get('PORT', '5000')
        workers = os.environ.get('WORKERS', '4')
        
        # Start the server
        logger.info(f"Starting Auto-Trader API server on port {port} with {workers} workers")
        
        # Build the gunicorn command
        cmd = f"gunicorn --workers={workers} --bind=0.0.0.0:{port} app:app"
        
        # Run gunicorn
        os.system(cmd)
        
    except Exception as e:
        logger.error(f"Error starting API server: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main() 