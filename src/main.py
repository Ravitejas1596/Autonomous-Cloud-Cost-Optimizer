"""
Autonomous Cloud Cost Optimizer - Main Application Entry Point

This is the main FastAPI application that orchestrates all components of the
Autonomous Cloud Cost Optimizer platform.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer
import structlog
import uvicorn

from src.core.config import settings
from src.core.database import init_database, get_db
from src.core.middleware import LoggingMiddleware, SecurityMiddleware
from src.api.v1.api import api_router
from src.services.cost_optimizer import CostOptimizerService
from src.services.notification import NotificationService
from src.services.approval_workflow import ApprovalWorkflowService
from src.tasks.optimization_tasks import start_optimization_scheduler
from src.core.monitoring import setup_monitoring, health_check

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Global services
cost_optimizer_service: CostOptimizerService = None
notification_service: NotificationService = None
approval_workflow_service: ApprovalWorkflowService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    global cost_optimizer_service, notification_service, approval_workflow_service
    
    logger.info("Starting Autonomous Cloud Cost Optimizer", version=settings.VERSION)
    
    try:
        # Initialize database
        await init_database()
        logger.info("Database initialized successfully")
        
        # Setup monitoring
        setup_monitoring()
        logger.info("Monitoring setup completed")
        
        # Initialize core services
        cost_optimizer_service = CostOptimizerService()
        notification_service = NotificationService()
        approval_workflow_service = ApprovalWorkflowService()
        
        await cost_optimizer_service.initialize()
        await notification_service.initialize()
        await approval_workflow_service.initialize()
        
        logger.info("Core services initialized successfully")
        
        # Start background tasks
        optimization_task = asyncio.create_task(start_optimization_scheduler())
        logger.info("Optimization scheduler started")
        
        yield
        
    except Exception as e:
        logger.error("Failed to initialize application", error=str(e))
        raise
    finally:
        # Cleanup
        if 'optimization_task' in locals():
            optimization_task.cancel()
            try:
                await optimization_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Application shutdown completed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title="Autonomous Cloud Cost Optimizer",
        description="Enterprise-grade AI-powered cloud cost optimization platform",
        version=settings.VERSION,
        docs_url="/docs" if settings.ENVIRONMENT == "development" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT == "development" else None,
        openapi_url="/openapi.json" if settings.ENVIRONMENT == "development" else None,
        lifespan=lifespan
    )
    
    # Security middleware
    app.add_middleware(
        TrustedHostMiddleware, 
        allowed_hosts=settings.ALLOWED_HOSTS
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Custom middleware
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(SecurityMiddleware)
    
    # Include API routes
    app.include_router(api_router, prefix="/api/v1")
    
    # Health check endpoint
    @app.get("/health", tags=["Health"])
    async def health():
        """Health check endpoint for monitoring."""
        return await health_check()
    
    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root():
        """Root endpoint with basic API information."""
        return {
            "name": "Autonomous Cloud Cost Optimizer",
            "version": settings.VERSION,
            "status": "operational",
            "environment": settings.ENVIRONMENT,
            "documentation": "/docs" if settings.ENVIRONMENT == "development" else "Contact support for API documentation"
        }
    
    return app


# Create the application instance
app = create_app()


# Dependency injection for services
async def get_cost_optimizer_service() -> CostOptimizerService:
    """Get the cost optimizer service instance."""
    if cost_optimizer_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return cost_optimizer_service


async def get_notification_service() -> NotificationService:
    """Get the notification service instance."""
    if notification_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return notification_service


async def get_approval_workflow_service() -> ApprovalWorkflowService:
    """Get the approval workflow service instance."""
    if approval_workflow_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return approval_workflow_service


# Global dependency
security = HTTPBearer()


@app.get("/api/v1/metrics", tags=["Metrics"])
async def get_metrics(
    background_tasks: BackgroundTasks,
    cost_service: CostOptimizerService = Depends(get_cost_optimizer_service)
):
    """Get current optimization metrics and performance statistics."""
    try:
        metrics = await cost_service.get_optimization_metrics()
        return {
            "status": "success",
            "data": metrics,
            "timestamp": "2024-01-15T10:30:00Z"
        }
    except Exception as e:
        logger.error("Failed to retrieve metrics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development",
        log_level="info",
        access_log=True
    )
