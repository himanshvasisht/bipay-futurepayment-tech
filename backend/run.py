#!/usr/bin/env python3
"""
BiPay Backend Application Runner - SIMPLIFIED FOR STABILITY
"""

import uvicorn
from loguru import logger
import sys
import os

# Add the current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def main():
    """Main application entry point"""
    logger.info("🚀 Starting BiPay Backend...")
    logger.info("📍 Environment: Development")
    logger.info("🌐 Server will run on: http://localhost:8000")
    
    try:
        # Use a more stable configuration
        uvicorn.run(
            "app.main:app",
            host="127.0.0.1",  # Changed from 0.0.0.0 for Windows stability
            port=8000,
            reload=False,  # Disabled reload for stability
            log_level="info",
            access_log=True
        )
    except KeyboardInterrupt:
        logger.info("🛑 Application stopped by user")
    except Exception as e:
        logger.error(f"❌ Failed to start application: {e}")
        logger.error(f"Error details: {type(e).__name__}")
        sys.exit(1)

if __name__ == "__main__":
    main()
