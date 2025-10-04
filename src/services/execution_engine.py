"""
Auto-Execution Engine with Rollback Mechanisms.

This module handles the automated execution of approved cost optimizations
with comprehensive rollback capabilities and safety mechanisms.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import uuid
import traceback

from src.core.config import settings
from src.core.database import get_db
from src.models.optimization import OptimizationOpportunity, OptimizationExecution, OptimizationStatus
from src.services.cloud_providers import CloudProviderService
from src.core.monitoring import track_metric, log_event


class ExecutionStatus(Enum):
    """Execution status for optimizations."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class ExecutionPhase(Enum):
    """Phases of optimization execution."""
    PREPARATION = "preparation"
    VALIDATION = "validation"
    BACKUP = "backup"
    EXECUTION = "execution"
    VERIFICATION = "verification"
    COMPLETION = "completion"
    ROLLBACK = "rollback"


@dataclass
class ExecutionStep:
    """Represents a single step in the execution process."""
    id: str
    name: str
    description: str
    phase: ExecutionPhase
    order: int
    timeout_minutes: int
    retry_count: int = 0
    max_retries: int = 3
    status: ExecutionStatus = ExecutionStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    rollback_steps: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionContext:
    """Context for optimization execution."""
    opportunity_id: str
    execution_id: str
    resource_id: str
    cloud_provider: str
    region: str
    optimization_type: str
    current_config: Dict[str, Any]
    target_config: Dict[str, Any]
    backup_data: Dict[str, Any] = field(default_factory=dict)
    execution_log: List[Dict[str, Any]] = field(default_factory=list)
    rollback_data: Dict[str, Any] = field(default_factory=dict)


class ExecutionEngine:
    """Engine for executing cost optimizations with rollback capabilities."""
    
    def __init__(self):
        self.cloud_provider_service = CloudProviderService()
        self.active_executions = {}
        self.execution_handlers = {}
        
    async def initialize(self):
        """Initialize the execution engine."""
        try:
            await self.cloud_provider_service.initialize()
            await self._register_execution_handlers()
            log_event("execution_engine_initialized", {"status": "success"})
        except Exception as e:
            log_event("execution_engine_initialization_failed", {"error": str(e)})
            raise
    
    async def _register_execution_handlers(self):
        """Register handlers for different optimization types."""
        self.execution_handlers = {
            "rightsizing": self._execute_rightsizing,
            "scheduling": self._execute_scheduling,
            "unused_resources": self._execute_unused_resource_removal,
            "storage_optimization": self._execute_storage_optimization,
            "reserved_instances": self._execute_reserved_instance_purchase,
            "spot_instances": self._execute_spot_instance_migration
        }
    
    async def execute_optimization(self, opportunity: OptimizationOpportunity, 
                                 approver_id: str) -> OptimizationExecution:
        """Execute an approved optimization."""
        try:
            log_event("optimization_execution_started", {
                "opportunity_id": opportunity.id,
                "optimization_type": opportunity.optimization_type.value
            })
            
            # Create execution record
            execution = OptimizationExecution(
                id=str(uuid.uuid4()),
                opportunity_id=opportunity.id,
                status=OptimizationStatus.EXECUTING,
                started_at=datetime.utcnow(),
                executed_by=approver_id
            )
            
            # Create execution context
            context = await self._create_execution_context(opportunity, execution)
            
            # Store active execution
            self.active_executions[execution.id] = {
                "execution": execution,
                "context": context,
                "status": ExecutionStatus.RUNNING
            }
            
            # Execute the optimization
            try:
                await self._run_execution_pipeline(context, opportunity)
                execution.status = OptimizationStatus.COMPLETED
                execution.completed_at = datetime.utcnow()
                
                log_event("optimization_execution_completed", {
                    "execution_id": execution.id,
                    "opportunity_id": opportunity.id
                })
                
            except Exception as e:
                # Execution failed, attempt rollback
                await self._handle_execution_failure(execution, context, str(e))
                raise
            
            finally:
                # Clean up active execution
                if execution.id in self.active_executions:
                    del self.active_executions[execution.id]
            
            return execution
            
        except Exception as e:
            log_event("optimization_execution_failed", {
                "opportunity_id": opportunity.id,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            raise
    
    async def _create_execution_context(self, opportunity: OptimizationOpportunity, 
                                      execution: OptimizationExecution) -> ExecutionContext:
        """Create execution context for an optimization."""
        # Get current resource configuration
        current_config = await self.cloud_provider_service.get_resource_config(
            opportunity.resource_id, opportunity.cloud_provider.value
        )
        
        # Determine target configuration based on optimization type
        target_config = await self._calculate_target_config(opportunity, current_config)
        
        return ExecutionContext(
            opportunity_id=str(opportunity.id),
            execution_id=execution.id,
            resource_id=opportunity.resource_id,
            cloud_provider=opportunity.cloud_provider.value,
            region=opportunity.region,
            optimization_type=opportunity.optimization_type.value,
            current_config=current_config,
            target_config=target_config
        )
    
    async def _calculate_target_config(self, opportunity: OptimizationOpportunity, 
                                     current_config: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate target configuration for optimization."""
        target_config = current_config.copy()
        
        if opportunity.optimization_type.value == "rightsizing":
            # Calculate optimal instance size based on utilization
            target_config["instance_type"] = await self._calculate_optimal_instance_size(
                current_config, opportunity
            )
        elif opportunity.optimization_type.value == "scheduling":
            # Add scheduling configuration
            target_config["scheduling"] = {
                "start_schedule": "0 8 * * 1-5",  # 8 AM weekdays
                "stop_schedule": "0 18 * * 1-5",  # 6 PM weekdays
                "timezone": "UTC"
            }
        elif opportunity.optimization_type.value == "storage_optimization":
            # Calculate optimal storage class
            target_config["storage_class"] = await self._calculate_optimal_storage_class(
                current_config, opportunity
            )
        
        return target_config
    
    async def _run_execution_pipeline(self, context: ExecutionContext, 
                                    opportunity: OptimizationOpportunity):
        """Run the complete execution pipeline."""
        execution_steps = await self._create_execution_steps(context, opportunity)
        
        for step in execution_steps:
            try:
                await self._execute_step(step, context)
                context.execution_log.append({
                    "step_id": step.id,
                    "step_name": step.name,
                    "status": step.status.value,
                    "completed_at": step.completed_at.isoformat() if step.completed_at else None,
                    "duration_seconds": (step.completed_at - step.started_at).total_seconds() 
                                      if step.completed_at and step.started_at else None
                })
                
                # Check if execution should be aborted
                if step.status == ExecutionStatus.FAILED and step.retry_count >= step.max_retries:
                    raise Exception(f"Step {step.name} failed after {step.max_retries} retries: {step.error_message}")
                
            except Exception as e:
                log_event("execution_step_failed", {
                    "step_id": step.id,
                    "step_name": step.name,
                    "error": str(e)
                })
                
                # Attempt rollback
                await self._rollback_execution(context, step)
                raise
    
    async def _create_execution_steps(self, context: ExecutionContext, 
                                    opportunity: OptimizationOpportunity) -> List[ExecutionStep]:
        """Create execution steps for the optimization."""
        base_steps = [
            ExecutionStep(
                id=f"{context.execution_id}_preparation",
                name="Preparation",
                description="Prepare execution environment",
                phase=ExecutionPhase.PREPARATION,
                order=1,
                timeout_minutes=5
            ),
            ExecutionStep(
                id=f"{context.execution_id}_validation",
                name="Validation",
                description="Validate current state and prerequisites",
                phase=ExecutionPhase.VALIDATION,
                order=2,
                timeout_minutes=10
            ),
            ExecutionStep(
                id=f"{context.execution_id}_backup",
                name="Backup",
                description="Create backup of current configuration",
                phase=ExecutionPhase.BACKUP,
                order=3,
                timeout_minutes=15
            ),
            ExecutionStep(
                id=f"{context.execution_id}_execution",
                name="Execution",
                description=f"Execute {context.optimization_type} optimization",
                phase=ExecutionPhase.EXECUTION,
                order=4,
                timeout_minutes=opportunity.estimated_execution_time
            ),
            ExecutionStep(
                id=f"{context.execution_id}_verification",
                name="Verification",
                description="Verify optimization was successful",
                phase=ExecutionPhase.VERIFICATION,
                order=5,
                timeout_minutes=10
            ),
            ExecutionStep(
                id=f"{context.execution_id}_completion",
                name="Completion",
                description="Complete execution and cleanup",
                phase=ExecutionPhase.COMPLETION,
                order=6,
                timeout_minutes=5
            )
        ]
        
        # Add optimization-specific steps
        optimization_steps = await self._get_optimization_specific_steps(context, opportunity)
        all_steps = base_steps + optimization_steps
        
        return sorted(all_steps, key=lambda x: x.order)
    
    async def _get_optimization_specific_steps(self, context: ExecutionContext, 
                                             opportunity: OptimizationOpportunity) -> List[ExecutionStep]:
        """Get optimization-specific execution steps."""
        handler = self.execution_handlers.get(context.optimization_type)
        if handler:
            return await handler(context, opportunity)
        else:
            raise ValueError(f"No handler found for optimization type: {context.optimization_type}")
    
    async def _execute_step(self, step: ExecutionStep, context: ExecutionContext):
        """Execute a single step."""
        try:
            step.status = ExecutionStatus.RUNNING
            step.started_at = datetime.now()
            
            # Execute step based on phase
            if step.phase == ExecutionPhase.PREPARATION:
                await self._execute_preparation_step(step, context)
            elif step.phase == ExecutionPhase.VALIDATION:
                await self._execute_validation_step(step, context)
            elif step.phase == ExecutionPhase.BACKUP:
                await self._execute_backup_step(step, context)
            elif step.phase == ExecutionPhase.EXECUTION:
                await self._execute_optimization_step(step, context)
            elif step.phase == ExecutionPhase.VERIFICATION:
                await self._execute_verification_step(step, context)
            elif step.phase == ExecutionPhase.COMPLETION:
                await self._execute_completion_step(step, context)
            
            step.status = ExecutionStatus.COMPLETED
            step.completed_at = datetime.now()
            
            log_event("execution_step_completed", {
                "step_id": step.id,
                "step_name": step.name,
                "duration_seconds": (step.completed_at - step.started_at).total_seconds()
            })
            
        except Exception as e:
            step.status = ExecutionStatus.FAILED
            step.error_message = str(e)
            step.retry_count += 1
            
            log_event("execution_step_failed", {
                "step_id": step.id,
                "step_name": step.name,
                "error": str(e),
                "retry_count": step.retry_count
            })
            
            # Retry if within limits
            if step.retry_count < step.max_retries:
                await asyncio.sleep(5)  # Wait before retry
                await self._execute_step(step, context)
            else:
                raise
    
    async def _execute_preparation_step(self, step: ExecutionStep, context: ExecutionContext):
        """Execute preparation step."""
        # Validate cloud provider connection
        await self.cloud_provider_service.validate_connection(context.cloud_provider)
        
        # Check resource accessibility
        resource_exists = await self.cloud_provider_service.resource_exists(
            context.resource_id, context.cloud_provider
        )
        
        if not resource_exists:
            raise Exception(f"Resource {context.resource_id} not found")
        
        step.metadata["preparation_completed"] = True
    
    async def _execute_validation_step(self, step: ExecutionStep, context: ExecutionContext):
        """Execute validation step."""
        # Validate prerequisites
        prerequisites = context.current_config.get("prerequisites", [])
        for prerequisite in prerequisites:
            if not await self._validate_prerequisite(prerequisite, context):
                raise Exception(f"Prerequisite not met: {prerequisite}")
        
        # Validate target configuration
        if not await self._validate_target_config(context.target_config, context):
            raise Exception("Target configuration is invalid")
        
        step.metadata["validation_completed"] = True
    
    async def _execute_backup_step(self, step: ExecutionStep, context: ExecutionContext):
        """Execute backup step."""
        # Create backup of current configuration
        backup_data = await self.cloud_provider_service.create_resource_backup(
            context.resource_id, context.cloud_provider
        )
        
        context.backup_data = backup_data
        step.metadata["backup_completed"] = True
        step.metadata["backup_size"] = len(json.dumps(backup_data))
    
    async def _execute_optimization_step(self, step: ExecutionStep, context: ExecutionContext):
        """Execute the main optimization step."""
        handler = self.execution_handlers.get(context.optimization_type)
        if handler:
            await handler(context, step)
        else:
            raise Exception(f"No handler for optimization type: {context.optimization_type}")
    
    async def _execute_verification_step(self, step: ExecutionStep, context: ExecutionContext):
        """Execute verification step."""
        # Verify optimization was successful
        current_config = await self.cloud_provider_service.get_resource_config(
            context.resource_id, context.cloud_provider
        )
        
        # Check if configuration matches target
        verification_passed = await self._verify_optimization_result(
            context.target_config, current_config, context
        )
        
        if not verification_passed:
            raise Exception("Optimization verification failed")
        
        step.metadata["verification_completed"] = True
    
    async def _execute_completion_step(self, step: ExecutionStep, context: ExecutionContext):
        """Execute completion step."""
        # Update resource tags
        await self.cloud_provider_service.update_resource_tags(
            context.resource_id, context.cloud_provider, {
                "optimized": "true",
                "optimization_type": context.optimization_type,
                "optimized_at": datetime.now().isoformat(),
                "execution_id": context.execution_id
            }
        )
        
        step.metadata["completion_completed"] = True
    
    # Optimization-specific handlers
    async def _execute_rightsizing(self, context: ExecutionContext, opportunity: OptimizationOpportunity) -> List[ExecutionStep]:
        """Execute rightsizing optimization."""
        return [
            ExecutionStep(
                id=f"{context.execution_id}_rightsizing",
                name="Instance Rightsizing",
                description=f"Change instance type from {context.current_config.get('instance_type')} to {context.target_config.get('instance_type')}",
                phase=ExecutionPhase.EXECUTION,
                order=4,
                timeout_minutes=20,
                rollback_steps=[
                    "Stop instance",
                    "Change instance type back to original",
                    "Start instance"
                ]
            )
        ]
    
    async def _execute_scheduling(self, context: ExecutionContext, opportunity: OptimizationOpportunity) -> List[ExecutionStep]:
        """Execute scheduling optimization."""
        return [
            ExecutionStep(
                id=f"{context.execution_id}_scheduling",
                name="Resource Scheduling",
                description="Configure automatic start/stop schedule",
                phase=ExecutionPhase.EXECUTION,
                order=4,
                timeout_minutes=15,
                rollback_steps=[
                    "Remove scheduled actions",
                    "Start resource manually"
                ]
            )
        ]
    
    async def _execute_unused_resource_removal(self, context: ExecutionContext, opportunity: OptimizationOpportunity) -> List[ExecutionStep]:
        """Execute unused resource removal."""
        return [
            ExecutionStep(
                id=f"{context.execution_id}_removal",
                name="Unused Resource Removal",
                description="Remove unused resource",
                phase=ExecutionPhase.EXECUTION,
                order=4,
                timeout_minutes=10,
                rollback_steps=[
                    "Restore from backup",
                    "Recreate resource configuration"
                ]
            )
        ]
    
    async def _execute_storage_optimization(self, context: ExecutionContext, opportunity: OptimizationOpportunity) -> List[ExecutionStep]:
        """Execute storage optimization."""
        return [
            ExecutionStep(
                id=f"{context.execution_id}_storage",
                name="Storage Optimization",
                description="Migrate to optimal storage class",
                phase=ExecutionPhase.EXECUTION,
                order=4,
                timeout_minutes=30,
                rollback_steps=[
                    "Migrate back to original storage class",
                    "Remove lifecycle policies"
                ]
            )
        ]
    
    async def _execute_reserved_instance_purchase(self, context: ExecutionContext, opportunity: OptimizationOpportunity) -> List[ExecutionStep]:
        """Execute reserved instance purchase."""
        return [
            ExecutionStep(
                id=f"{context.execution_id}_reserved",
                name="Reserved Instance Purchase",
                description="Purchase reserved instances",
                phase=ExecutionPhase.EXECUTION,
                order=4,
                timeout_minutes=5,
                rollback_steps=[
                    "Cancel reserved instance purchase"
                ]
            )
        ]
    
    async def _execute_spot_instance_migration(self, context: ExecutionContext, opportunity: OptimizationOpportunity) -> List[ExecutionStep]:
        """Execute spot instance migration."""
        return [
            ExecutionStep(
                id=f"{context.execution_id}_spot",
                name="Spot Instance Migration",
                description="Migrate to spot instances",
                phase=ExecutionPhase.EXECUTION,
                order=4,
                timeout_minutes=25,
                rollback_steps=[
                    "Stop spot instance",
                    "Start on-demand instance",
                    "Update load balancer configuration"
                ]
            )
        ]
    
    async def _handle_execution_failure(self, execution: OptimizationExecution, 
                                      context: ExecutionContext, error_message: str):
        """Handle execution failure and perform rollback."""
        try:
            log_event("execution_failure_handling_started", {
                "execution_id": execution.id,
                "error": error_message
            })
            
            # Mark execution as failed
            execution.status = OptimizationStatus.FAILED
            execution.error_message = error_message
            execution.completed_at = datetime.utcnow()
            
            # Perform rollback
            rollback_success = await self._rollback_execution(context)
            
            if rollback_success:
                execution.status = OptimizationStatus.ROLLED_BACK
                log_event("execution_rollback_successful", {
                    "execution_id": execution.id
                })
            else:
                log_event("execution_rollback_failed", {
                    "execution_id": execution.id
                })
            
        except Exception as e:
            log_event("execution_failure_handling_failed", {
                "execution_id": execution.id,
                "error": str(e)
            })
    
    async def _rollback_execution(self, context: ExecutionContext) -> bool:
        """Perform rollback of failed execution."""
        try:
            log_event("rollback_started", {
                "execution_id": context.execution_id,
                "resource_id": context.resource_id
            })
            
            # Restore from backup
            if context.backup_data:
                await self.cloud_provider_service.restore_resource_from_backup(
                    context.resource_id, context.cloud_provider, context.backup_data
                )
            
            # Verify rollback
            current_config = await self.cloud_provider_service.get_resource_config(
                context.resource_id, context.cloud_provider
            )
            
            rollback_successful = await self._verify_rollback_success(
                context.current_config, current_config
            )
            
            if rollback_successful:
                log_event("rollback_completed_successfully", {
                    "execution_id": context.execution_id
                })
            else:
                log_event("rollback_verification_failed", {
                    "execution_id": context.execution_id
                })
            
            return rollback_successful
            
        except Exception as e:
            log_event("rollback_failed", {
                "execution_id": context.execution_id,
                "error": str(e)
            })
            return False
    
    # Helper methods
    async def _validate_prerequisite(self, prerequisite: str, context: ExecutionContext) -> bool:
        """Validate a prerequisite condition."""
        # Implementation would check specific prerequisites
        return True
    
    async def _validate_target_config(self, target_config: Dict[str, Any], 
                                    context: ExecutionContext) -> bool:
        """Validate target configuration."""
        # Implementation would validate configuration
        return True
    
    async def _verify_optimization_result(self, target_config: Dict[str, Any], 
                                        current_config: Dict[str, Any], 
                                        context: ExecutionContext) -> bool:
        """Verify optimization result."""
        # Implementation would verify optimization was successful
        return True
    
    async def _verify_rollback_success(self, original_config: Dict[str, Any], 
                                     current_config: Dict[str, Any]) -> bool:
        """Verify rollback was successful."""
        # Implementation would verify rollback
        return True
    
    async def _calculate_optimal_instance_size(self, current_config: Dict[str, Any], 
                                             opportunity: OptimizationOpportunity) -> str:
        """Calculate optimal instance size."""
        # Implementation would calculate optimal size based on utilization
        return "t3.medium"
    
    async def _calculate_optimal_storage_class(self, current_config: Dict[str, Any], 
                                             opportunity: OptimizationOpportunity) -> str:
        """Calculate optimal storage class."""
        # Implementation would calculate optimal storage class
        return "STANDARD_IA"
    
    async def get_execution_status(self, execution_id: str) -> Dict[str, Any]:
        """Get execution status."""
        if execution_id in self.active_executions:
            execution_data = self.active_executions[execution_id]
            return {
                "execution_id": execution_id,
                "status": execution_data["status"].value,
                "context": execution_data["context"].__dict__,
                "is_active": True
            }
        else:
            return {
                "execution_id": execution_id,
                "status": "not_found",
                "is_active": False
            }
    
    async def cancel_execution(self, execution_id: str, reason: str) -> bool:
        """Cancel an active execution."""
        try:
            if execution_id in self.active_executions:
                execution_data = self.active_executions[execution_id]
                
                # Perform rollback
                await self._rollback_execution(execution_data["context"])
                
                # Mark as cancelled
                execution_data["execution"].status = OptimizationStatus.CANCELLED
                execution_data["execution"].error_message = f"Cancelled: {reason}"
                
                # Remove from active executions
                del self.active_executions[execution_id]
                
                log_event("execution_cancelled", {
                    "execution_id": execution_id,
                    "reason": reason
                })
                
                return True
            
            return False
            
        except Exception as e:
            log_event("execution_cancellation_failed", {
                "execution_id": execution_id,
                "error": str(e)
            })
            return False
