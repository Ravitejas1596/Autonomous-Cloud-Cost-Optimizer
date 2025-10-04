"""
API v1 Router for Autonomous Cloud Cost Optimizer.

This module defines all API endpoints for the cost optimization platform.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Path
from fastapi.security import HTTPBearer
from typing import List, Optional, Dict, Any
from datetime import datetime

from src.api.v1.endpoints import (
    optimizations,
    approvals,
    executions,
    notifications,
    analytics,
    health
)

# Security
security = HTTPBearer()

# Create API router
api_router = APIRouter()

# Include endpoint routers
api_router.include_router(
    optimizations.router,
    prefix="/optimizations",
    tags=["Optimizations"]
)

api_router.include_router(
    approvals.router,
    prefix="/approvals",
    tags=["Approvals"]
)

api_router.include_router(
    executions.router,
    prefix="/executions",
    tags=["Executions"]
)

api_router.include_router(
    notifications.router,
    prefix="/notifications",
    tags=["Notifications"]
)

api_router.include_router(
    analytics.router,
    prefix="/analytics",
    tags=["Analytics"]
)

api_router.include_router(
    health.router,
    prefix="/health",
    tags=["Health"]
)
