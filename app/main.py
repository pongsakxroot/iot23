"""
FastAPI application main entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.config import settings
from app.database import init_db
from app.services.mqtt_client import mqtt_client
from app.api import orders, webhook

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events - startup and shutdown"""
    # Startup
    logger.info("Starting PromptPay Payment Verification System")
    
    # Initialize database
    init_db()
    
    # Connect to MQTT broker
    try:
        mqtt_client.connect()
    except Exception as e:
        logger.warning(f"MQTT connection failed on startup: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    try:
        mqtt_client.disconnect()
    except Exception as e:
        logger.warning(f"MQTT disconnect error: {e}")


# Create FastAPI app
app = FastAPI(
    title="PromptPay Payment Verification API",
    description="Semi-automated payment verification system for Thai PromptPay with hardware trigger",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(orders.router)
app.include_router(webhook.router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "PromptPay Payment Verification API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "mqtt_connected": mqtt_client.connected
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
