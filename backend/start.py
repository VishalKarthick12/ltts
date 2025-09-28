#!/usr/bin/env python3
"""
Production startup script for LTTS FastAPI backend
Optimized for Render deployment with proper logging and error handling
"""

import os
import sys
import logging
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Main startup function with environment validation"""
    
    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    environment = os.getenv("ENVIRONMENT", "development")
    
    # Validate required environment variables
    required_vars = [
        "DATABASE_URL",
        "SUPABASE_URL", 
        "SUPABASE_SERVICE_ROLE_KEY",
        "JWT_SECRET_KEY"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please check your .env file or Render environment variables")
        sys.exit(1)
    
    # Log startup information
    logger.info("="*60)
    logger.info("🚀 Starting LTTS FastAPI Backend")
    logger.info("="*60)
    logger.info(f"Environment: {environment}")
    logger.info(f"Host: {host}")
    logger.info(f"Port: {port}")
    logger.info(f"Database: {os.getenv('DATABASE_URL', '').split('@')[1] if '@' in os.getenv('DATABASE_URL', '') else 'Not configured'}")
    logger.info(f"Supabase: {os.getenv('SUPABASE_URL', 'Not configured')}")
    logger.info("="*60)
    
    # Production configuration
    if environment == "production":
        logger.info("🔧 Production mode: optimized settings enabled")
        uvicorn.run(
            "app.main:app",
            host=host,
            port=port,
            workers=1,  # Single worker for Render's resource limits
            log_level="info",
            access_log=True,
            loop="asyncio",
            http="httptools",
            lifespan="on"
        )
    else:
        logger.info("🔧 Development mode: debug settings enabled")
        uvicorn.run(
            "app.main:app",
            host=host,
            port=port,
            reload=True,
            log_level="debug",
            access_log=True
        )

if __name__ == "__main__":
    main()
