"""
Optimization endpoints for the Autonomous Cloud Cost Optimizer API.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from typing import List, Optional, Dict, Any
from datetime import datetime

from src.services.cost_optimizer import CostOptimizerService
from src.services.approval_workflow import ApprovalWorkflowService
from src.core.monitoring import log_event

router = APIRouter()

async def get_cost_optimizer_service() -> CostOptimizerService:
    """Dependency to get cost optimizer service."""
    # This would be injected from the main app
    return CostOptimizerService()

async def get_approval_workflow_service() -> ApprovalWorkflowService:
    """Dependency to get approval workflow service."""
    # This would be injected from the main app
    return ApprovalWorkflowService()

@router.get("/opportunities", response_model=Dict[str, Any])
async def get_optimization_opportunities(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    provider: Optional[str] = Query(None),
    optimization_type: Optional[str] = Query(None),
    cost_service: CostOptimizerService = Depends(get_cost_optimizer_service)
):
    """Get optimization opportunities."""
    try:
        opportunities = await cost_service.analyze_cost_optimization_opportunities()
        
        # Apply filters
        if provider:
            opportunities = [o for o in opportunities if o.cloud_provider == provider]
        if optimization_type:
            opportunities = [o for o in opportunities if o.optimization_type.value == optimization_type]
        
        # Apply pagination
        total = len(opportunities)
        paginated_opportunities = opportunities[offset:offset + limit]
        
        return {
            "opportunities": [
                {
                    "id": o.id,
                    "service_name": o.service_name,
                    "resource_id": o.resource_id,
                    "optimization_type": o.optimization_type.value,
                    "cloud_provider": o.cloud_provider,
                    "region": o.region,
                    "current_cost": o.current_cost,
                    "potential_savings": o.potential_savings,
                    "confidence_score": o.confidence_score,
                    "risk_level": o.risk_level.value,
                    "description": o.description,
                    "created_at": o.created_at.isoformat(),
                    "expires_at": o.expires_at.isoformat() if o.expires_at else None
                }
                for o in paginated_opportunities
            ],
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total
            }
        }
        
    except Exception as e:
        log_event("optimization_opportunities_fetch_failed", {"error": str(e)})
        raise HTTPException(status_code=500, detail="Failed to fetch optimization opportunities")

@router.get("/opportunities/{opportunity_id}", response_model=Dict[str, Any])
async def get_optimization_opportunity(
    opportunity_id: str = Path(..., description="Optimization opportunity ID"),
    cost_service: CostOptimizerService = Depends(get_cost_optimizer_service)
):
    """Get a specific optimization opportunity."""
    try:
        # In a real implementation, this would fetch from database
        opportunity_data = {
            "id": opportunity_id,
            "service_name": "EC2 Instance",
            "resource_id": "i-1234567890abcdef0",
            "optimization_type": "rightsizing",
            "cloud_provider": "aws",
            "region": "us-east-1",
            "current_cost": 85.50,
            "potential_savings": 34.20,
            "confidence_score": 0.92,
            "risk_level": "low",
            "description": "Right-size t3.large instance to t3.medium based on CPU utilization patterns",
            "implementation_steps": [
                "Create snapshot of current instance",
                "Stop the instance",
                "Change instance type to t3.medium",
                "Start the instance",
                "Verify application functionality"
            ],
            "rollback_steps": [
                "Stop the instance",
                "Change back to t3.large",
                "Start the instance"
            ],
            "prerequisites": [
                "Application can handle brief downtime",
                "Backup/snapshot capability available"
            ],
            "estimated_execution_time": 15,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now().timestamp() + 604800).isoformat()
        }
        
        return opportunity_data
        
    except Exception as e:
        log_event("optimization_opportunity_fetch_failed", {
            "opportunity_id": opportunity_id,
            "error": str(e)
        })
        raise HTTPException(status_code=404, detail="Optimization opportunity not found")

@router.post("/opportunities/{opportunity_id}/approve")
async def approve_optimization_opportunity(
    opportunity_id: str = Path(..., description="Optimization opportunity ID"),
    approver_id: str = Query(..., description="Approver ID"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    approval_service: ApprovalWorkflowService = Depends(get_approval_workflow_service)
):
    """Approve an optimization opportunity."""
    try:
        # In a real implementation, this would:
        # 1. Validate the opportunity exists
        # 2. Check if user has permission to approve
        # 3. Create approval record
        # 4. Trigger execution
        
        log_event("optimization_approved", {
            "opportunity_id": opportunity_id,
            "approver_id": approver_id
        })
        
        return {
            "status": "approved",
            "opportunity_id": opportunity_id,
            "approver_id": approver_id,
            "approved_at": datetime.now().isoformat(),
            "message": "Optimization opportunity approved successfully"
        }
        
    except Exception as e:
        log_event("optimization_approval_failed", {
            "opportunity_id": opportunity_id,
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail="Failed to approve optimization opportunity")

@router.post("/opportunities/{opportunity_id}/reject")
async def reject_optimization_opportunity(
    opportunity_id: str = Path(..., description="Optimization opportunity ID"),
    approver_id: str = Query(..., description="Approver ID"),
    reason: str = Query(..., description="Rejection reason"),
    approval_service: ApprovalWorkflowService = Depends(get_approval_workflow_service)
):
    """Reject an optimization opportunity."""
    try:
        log_event("optimization_rejected", {
            "opportunity_id": opportunity_id,
            "approver_id": approver_id,
            "reason": reason
        })
        
        return {
            "status": "rejected",
            "opportunity_id": opportunity_id,
            "approver_id": approver_id,
            "rejected_at": datetime.now().isoformat(),
            "reason": reason,
            "message": "Optimization opportunity rejected"
        }
        
    except Exception as e:
        log_event("optimization_rejection_failed", {
            "opportunity_id": opportunity_id,
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail="Failed to reject optimization opportunity")

@router.get("/metrics", response_model=Dict[str, Any])
async def get_optimization_metrics(
    cost_service: CostOptimizerService = Depends(get_cost_optimizer_service)
):
    """Get optimization metrics and statistics."""
    try:
        metrics = await cost_service.get_optimization_metrics()
        return {
            "status": "success",
            "data": metrics,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        log_event("optimization_metrics_fetch_failed", {"error": str(e)})
        raise HTTPException(status_code=500, detail="Failed to fetch optimization metrics")

@router.post("/analyze")
async def trigger_optimization_analysis(
    background_tasks: BackgroundTasks = BackgroundTasks(),
    cost_service: CostOptimizerService = Depends(get_cost_optimizer_service)
):
    """Trigger a new optimization analysis."""
    try:
        # Start analysis in background
        background_tasks.add_task(cost_service.analyze_cost_optimization_opportunities)
        
        return {
            "status": "started",
            "message": "Optimization analysis started in background",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        log_event("optimization_analysis_trigger_failed", {"error": str(e)})
        raise HTTPException(status_code=500, detail="Failed to start optimization analysis")
