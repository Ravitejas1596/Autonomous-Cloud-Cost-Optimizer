"""
Database models for optimization opportunities and executions.

This module defines the SQLAlchemy models for storing optimization data,
recommendations, and execution history.
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, Dict, Any, List

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, JSON, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

Base = declarative_base()


class OptimizationStatus(PyEnum):
    """Status of optimization opportunities."""
    DISCOVERED = "discovered"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class OptimizationType(PyEnum):
    """Types of optimizations."""
    RIGHTSIZING = "rightsizing"
    SCHEDULING = "scheduling"
    RESERVED_INSTANCES = "reserved_instances"
    SPOT_INSTANCES = "spot_instances"
    STORAGE_OPTIMIZATION = "storage_optimization"
    UNUSED_RESOURCES = "unused_resources"


class RiskLevel(PyEnum):
    """Risk levels for optimizations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CloudProvider(PyEnum):
    """Supported cloud providers."""
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"


class OptimizationOpportunity(Base):
    """Model for storing optimization opportunities."""
    
    __tablename__ = "optimization_opportunities"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic information
    service_name = Column(String(255), nullable=False)
    resource_id = Column(String(255), nullable=False)
    optimization_type = Column(Enum(OptimizationType), nullable=False)
    cloud_provider = Column(Enum(CloudProvider), nullable=False)
    region = Column(String(100), nullable=False)
    
    # Cost information
    current_cost = Column(Float, nullable=False)
    potential_savings = Column(Float, nullable=False)
    confidence_score = Column(Float, nullable=False)
    risk_level = Column(Enum(RiskLevel), nullable=False)
    
    # Description and implementation
    description = Column(Text, nullable=False)
    implementation_steps = Column(JSON, nullable=False)
    rollback_steps = Column(JSON, nullable=False)
    prerequisites = Column(JSON, nullable=False)
    
    # Timing
    estimated_execution_time = Column(Integer, nullable=False)  # minutes
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    
    # Status tracking
    status = Column(Enum(OptimizationStatus), default=OptimizationStatus.DISCOVERED, nullable=False)
    approved_by = Column(String(255), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    
    # Relationships
    executions = relationship("OptimizationExecution", back_populates="opportunity")
    notifications = relationship("OptimizationNotification", back_populates="opportunity")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "service_name": self.service_name,
            "resource_id": self.resource_id,
            "optimization_type": self.optimization_type.value,
            "cloud_provider": self.cloud_provider.value,
            "region": self.region,
            "current_cost": self.current_cost,
            "potential_savings": self.potential_savings,
            "confidence_score": self.confidence_score,
            "risk_level": self.risk_level.value,
            "description": self.description,
            "implementation_steps": self.implementation_steps,
            "rollback_steps": self.rollback_steps,
            "prerequisites": self.prerequisites,
            "estimated_execution_time": self.estimated_execution_time,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "status": self.status.value,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None
        }


class OptimizationExecution(Base):
    """Model for tracking optimization executions."""
    
    __tablename__ = "optimization_executions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    opportunity_id = Column(UUID(as_uuid=True), ForeignKey("optimization_opportunities.id"), nullable=False)
    
    # Execution details
    status = Column(Enum(OptimizationStatus), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    # Results
    actual_savings = Column(Float, nullable=True)
    execution_log = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Rollback information
    rollback_required = Column(Boolean, default=False, nullable=False)
    rollback_completed = Column(Boolean, default=False, nullable=False)
    rollback_log = Column(JSON, nullable=True)
    
    # Executed by
    executed_by = Column(String(255), nullable=False)
    
    # Relationships
    opportunity = relationship("OptimizationOpportunity", back_populates="executions")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "opportunity_id": str(self.opportunity_id),
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "actual_savings": self.actual_savings,
            "execution_log": self.execution_log,
            "error_message": self.error_message,
            "rollback_required": self.rollback_required,
            "rollback_completed": self.rollback_completed,
            "rollback_log": self.rollback_log,
            "executed_by": self.executed_by
        }


class OptimizationNotification(Base):
    """Model for tracking notifications sent for optimizations."""
    
    __tablename__ = "optimization_notifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    opportunity_id = Column(UUID(as_uuid=True), ForeignKey("optimization_opportunities.id"), nullable=False)
    
    # Notification details
    notification_type = Column(String(100), nullable=False)  # email, slack, teams, sms
    recipient = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=True)
    message = Column(Text, nullable=False)
    
    # Delivery status
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    delivery_status = Column(String(50), nullable=False)  # sent, delivered, failed
    delivery_error = Column(Text, nullable=True)
    
    # Relationships
    opportunity = relationship("OptimizationOpportunity", back_populates="notifications")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "opportunity_id": str(self.opportunity_id),
            "notification_type": self.notification_type,
            "recipient": self.recipient,
            "subject": self.subject,
            "message": self.message,
            "sent_at": self.sent_at.isoformat(),
            "delivery_status": self.delivery_status,
            "delivery_error": self.delivery_error
        }


class CostAnalysis(Base):
    """Model for storing cost analysis data."""
    
    __tablename__ = "cost_analyses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Analysis metadata
    analysis_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    cloud_provider = Column(Enum(CloudProvider), nullable=False)
    region = Column(String(100), nullable=False)
    
    # Cost data
    total_monthly_cost = Column(Float, nullable=False)
    total_resources = Column(Integer, nullable=False)
    cost_breakdown = Column(JSON, nullable=False)  # Service-wise breakdown
    
    # Optimization potential
    total_optimization_potential = Column(Float, nullable=False)
    high_impact_opportunities = Column(Integer, nullable=False)
    low_risk_opportunities = Column(Integer, nullable=False)
    
    # Analysis results
    recommendations_count = Column(Integer, nullable=False)
    estimated_monthly_savings = Column(Float, nullable=False)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "analysis_date": self.analysis_date.isoformat(),
            "cloud_provider": self.cloud_provider.value,
            "region": self.region,
            "total_monthly_cost": self.total_monthly_cost,
            "total_resources": self.total_resources,
            "cost_breakdown": self.cost_breakdown,
            "total_optimization_potential": self.total_optimization_potential,
            "high_impact_opportunities": self.high_impact_opportunities,
            "low_risk_opportunities": self.low_risk_opportunities,
            "recommendations_count": self.recommendations_count,
            "estimated_monthly_savings": self.estimated_monthly_savings
        }


class ResourceMetrics(Base):
    """Model for storing resource utilization metrics."""
    
    __tablename__ = "resource_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Resource identification
    resource_id = Column(String(255), nullable=False)
    service_name = Column(String(255), nullable=False)
    cloud_provider = Column(Enum(CloudProvider), nullable=False)
    region = Column(String(100), nullable=False)
    
    # Metrics timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Utilization metrics
    cpu_utilization = Column(Float, nullable=True)
    memory_utilization = Column(Float, nullable=True)
    network_io = Column(Float, nullable=True)
    storage_usage = Column(Float, nullable=True)
    
    # Cost metrics
    hourly_cost = Column(Float, nullable=True)
    monthly_cost_projection = Column(Float, nullable=True)
    
    # Performance metrics
    response_time = Column(Float, nullable=True)
    error_rate = Column(Float, nullable=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "resource_id": self.resource_id,
            "service_name": self.service_name,
            "cloud_provider": self.cloud_provider.value,
            "region": self.region,
            "timestamp": self.timestamp.isoformat(),
            "cpu_utilization": self.cpu_utilization,
            "memory_utilization": self.memory_utilization,
            "network_io": self.network_io,
            "storage_usage": self.storage_usage,
            "hourly_cost": self.hourly_cost,
            "monthly_cost_projection": self.monthly_cost_projection,
            "response_time": self.response_time,
            "error_rate": self.error_rate
        }


class ApprovalWorkflow(Base):
    """Model for tracking approval workflows."""
    
    __tablename__ = "approval_workflows"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    opportunity_id = Column(UUID(as_uuid=True), ForeignKey("optimization_opportunities.id"), nullable=False)
    
    # Workflow details
    workflow_type = Column(String(100), nullable=False)  # slack, teams, email
    approver_id = Column(String(255), nullable=False)
    approver_name = Column(String(255), nullable=False)
    
    # Approval status
    status = Column(String(50), nullable=False)  # pending, approved, rejected, expired
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    responded_at = Column(DateTime, nullable=True)
    response_message = Column(Text, nullable=True)
    
    # Escalation
    escalation_level = Column(Integer, default=0, nullable=False)
    escalated_to = Column(String(255), nullable=True)
    escalated_at = Column(DateTime, nullable=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "opportunity_id": str(self.opportunity_id),
            "workflow_type": self.workflow_type,
            "approver_id": self.approver_id,
            "approver_name": self.approver_name,
            "status": self.status,
            "requested_at": self.requested_at.isoformat(),
            "responded_at": self.responded_at.isoformat() if self.responded_at else None,
            "response_message": self.response_message,
            "escalation_level": self.escalation_level,
            "escalated_to": self.escalated_to,
            "escalated_at": self.escalated_at.isoformat() if self.escalated_at else None
        }
