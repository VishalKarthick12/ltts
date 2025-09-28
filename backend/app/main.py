from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import logging
from datetime import datetime

from app.database import check_database_health, supabase_manager
from app.models import HealthCheck
from app.routers import question_banks, auth, tests, analytics, test_taking, test_sharing

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Question Bank Management API",
    description="Backend API for managing question banks with file uploads",
    version="1.0.0"
)

# Configure CORS with environment awareness
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ltts-frontend.onrender.com"],  # hard-coded
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(auth.router)
app.include_router(question_banks.router)
app.include_router(tests.router)
app.include_router(analytics.router)
app.include_router(test_taking.router)
app.include_router(test_sharing.router)

@app.on_event("startup")
async def startup_event():
    """Initialize database connections on startup"""
    try:
        # Test database connection
        health = await check_database_health()
        if health["status"] == "healthy":
            logger.info("Database connection established successfully")
        else:
            logger.warning(f"Database connection issues: {health}")
    except Exception as e:
        logger.error(f"Failed to connect to database on startup: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up database connections on shutdown"""
    await supabase_manager.close()
    logger.info("Database connections closed")

@app.get("/")
async def root():
    return {"message": "Question Bank Management API", "version": "1.0.0"}

@app.get("/api/health", response_model=HealthCheck)
async def health_check():
    """Enhanced health check endpoint with database status"""
    try:
        db_health = await check_database_health()
        
        return HealthCheck(
            status="ok",
            message="Backend is running successfully",
            database_status=db_health,
            timestamp=datetime.utcnow()
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "error",
                "message": "Health check failed",
                "error": str(e)
            }
        )

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors"""
    logger.error(f"Unhandled exception: {exc}")
    return HTTPException(
        status_code=500,
        detail="Internal server error"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
