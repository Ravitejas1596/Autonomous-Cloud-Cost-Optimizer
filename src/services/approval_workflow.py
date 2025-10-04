"""
Approval Workflow Service for Slack and Microsoft Teams Integration.

This module handles the approval workflow for cost optimizations, including
Slack and Teams integration, approval tracking, and escalation policies.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

import aiohttp
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.signature import SignatureVerifier
from slack_sdk.models.blocks import (
    SectionBlock, DividerBlock, ActionsBlock, ButtonElement,
    ContextBlock, HeaderBlock
)
from slack_sdk.models.attachments import Attachment
from msgraph import GraphServiceClient
from msgraph.generated.models.o_data_errors.o_data_error import ODataError

from src.core.config import settings
from src.core.database import get_db
from src.models.optimization import OptimizationOpportunity, ApprovalWorkflow
from src.core.monitoring import track_metric, log_event


class ApprovalStatus(Enum):
    """Approval workflow statuses."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ESCALATED = "escalated"


class WorkflowType(Enum):
    """Types of approval workflows."""
    SLACK = "slack"
    TEAMS = "teams"
    EMAIL = "email"
    WEBHOOK = "webhook"


@dataclass
class ApprovalRequest:
    """Represents an approval request."""
    id: str
    opportunity_id: str
    workflow_type: WorkflowType
    approver_id: str
    approver_name: str
    title: str
    description: str
    current_cost: float
    potential_savings: float
    risk_level: str
    expires_at: datetime
    approval_url: str
    rejection_url: str
    metadata: Dict[str, Any]


@dataclass
class ApprovalResponse:
    """Represents an approval response."""
    request_id: str
    status: ApprovalStatus
    approver_id: str
    response_message: str
    timestamp: datetime
    escalation_level: int = 0


class ApprovalWorkflowService:
    """Service for managing approval workflows across multiple platforms."""
    
    def __init__(self):
        self.slack_client = None
        self.teams_client = None
        self.signature_verifier = None
        self.active_requests = {}
        self.escalation_policies = {}
        
    async def initialize(self):
        """Initialize the approval workflow service."""
        try:
            # Initialize Slack client
            if settings.SLACK_BOT_TOKEN:
                self.slack_client = AsyncWebClient(token=settings.SLACK_BOT_TOKEN)
                self.signature_verifier = SignatureVerifier(settings.SLACK_SIGNING_SECRET)
                
                # Test Slack connection
                response = await self.slack_client.auth_test()
                log_event("slack_connection_established", {"user": response["user"]})
            
            # Initialize Teams client
            if settings.TEAMS_APP_ID and settings.TEAMS_APP_PASSWORD:
                self.teams_client = GraphServiceClient(
                    credentials=settings.TEAMS_APP_ID,
                    scopes=['https://graph.microsoft.com/.default']
                )
                log_event("teams_connection_established")
            
            # Load escalation policies
            await self._load_escalation_policies()
            
            log_event("approval_workflow_initialized", {"status": "success"})
            
        except Exception as e:
            log_event("approval_workflow_initialization_failed", {"error": str(e)})
            raise
    
    async def _load_escalation_policies(self):
        """Load escalation policies for approval workflows."""
        self.escalation_policies = {
            "default": {
                "levels": [
                    {"level": 1, "timeout_hours": 2, "escalate_to": "team_lead"},
                    {"level": 2, "timeout_hours": 4, "escalate_to": "manager"},
                    {"level": 3, "timeout_hours": 8, "escalate_to": "director"}
                ]
            },
            "high_value": {
                "levels": [
                    {"level": 1, "timeout_hours": 1, "escalate_to": "senior_manager"},
                    {"level": 2, "timeout_hours": 2, "escalate_to": "director"},
                    {"level": 3, "timeout_hours": 4, "escalate_to": "vp"}
                ]
            },
            "low_risk": {
                "levels": [
                    {"level": 1, "timeout_hours": 4, "escalate_to": "team_lead"},
                    {"level": 2, "timeout_hours": 8, "escalate_to": "manager"}
                ]
            }
        }
    
    async def create_approval_request(self, opportunity: OptimizationOpportunity, 
                                    approver_id: str, workflow_type: WorkflowType = WorkflowType.SLACK) -> ApprovalRequest:
        """Create a new approval request."""
        try:
            # Determine escalation policy based on opportunity characteristics
            policy_key = self._get_escalation_policy(opportunity)
            
            # Create approval request
            request_id = f"approval_{opportunity.id}_{datetime.now().timestamp()}"
            expires_at = datetime.now() + timedelta(hours=settings.APPROVAL_TIMEOUT_HOURS)
            
            approval_request = ApprovalRequest(
                id=request_id,
                opportunity_id=str(opportunity.id),
                workflow_type=workflow_type,
                approver_id=approver_id,
                approver_name=await self._get_approver_name(approver_id, workflow_type),
                title=f"Cost Optimization Approval: {opportunity.service_name}",
                description=opportunity.description,
                current_cost=opportunity.current_cost,
                potential_savings=opportunity.potential_savings,
                risk_level=opportunity.risk_level.value,
                expires_at=expires_at,
                approval_url=f"{settings.API_BASE_URL}/approve/{request_id}",
                rejection_url=f"{settings.API_BASE_URL}/reject/{request_id}",
                metadata={
                    "policy_key": policy_key,
                    "escalation_level": 0,
                    "opportunity_type": opportunity.optimization_type.value
                }
            )
            
            # Send approval request
            if workflow_type == WorkflowType.SLACK:
                await self._send_slack_approval(approval_request)
            elif workflow_type == WorkflowType.TEAMS:
                await self._send_teams_approval(approval_request)
            elif workflow_type == WorkflowType.EMAIL:
                await self._send_email_approval(approval_request)
            
            # Store request
            self.active_requests[request_id] = approval_request
            
            # Schedule expiration check
            asyncio.create_task(self._schedule_expiration_check(approval_request))
            
            # Save to database
            await self._save_approval_workflow(approval_request)
            
            log_event("approval_request_created", {
                "request_id": request_id,
                "opportunity_id": opportunity.id,
                "workflow_type": workflow_type.value,
                "approver_id": approver_id
            })
            
            return approval_request
            
        except Exception as e:
            log_event("approval_request_creation_failed", {"error": str(e)})
            raise
    
    def _get_escalation_policy(self, opportunity: OptimizationOpportunity) -> str:
        """Determine the appropriate escalation policy for an opportunity."""
        if opportunity.potential_savings > 5000:
            return "high_value"
        elif opportunity.risk_level.value == "low":
            return "low_risk"
        else:
            return "default"
    
    async def _get_approver_name(self, approver_id: str, workflow_type: WorkflowType) -> str:
        """Get the display name of an approver."""
        try:
            if workflow_type == WorkflowType.SLACK:
                response = await self.slack_client.users_info(user=approver_id)
                return response["user"]["real_name"]
            elif workflow_type == WorkflowType.TEAMS:
                # Teams user lookup would go here
                return approver_id
            else:
                return approver_id
        except:
            return approver_id
    
    async def _send_slack_approval(self, request: ApprovalRequest):
        """Send approval request via Slack."""
        try:
            # Create Slack blocks for rich formatting
            blocks = [
                HeaderBlock(text=f"💰 Cost Optimization Approval Request"),
                SectionBlock(
                    text=f"*Service:* {request.title}\n"
                         f"*Current Cost:* ${request.current_cost:,.2f}\n"
                         f"*Potential Savings:* ${request.potential_savings:,.2f}\n"
                         f"*Risk Level:* {request.risk_level.title()}\n"
                         f"*Expires:* {request.expires_at.strftime('%Y-%m-%d %H:%M UTC')}"
                ),
                SectionBlock(text=f"*Description:*\n{request.description}"),
                ActionsBlock(
                    elements=[
                        ButtonElement(
                            text="✅ Approve",
                            style="primary",
                            action_id="approve_optimization",
                            value=request.id
                        ),
                        ButtonElement(
                            text="❌ Reject",
                            style="danger",
                            action_id="reject_optimization",
                            value=request.id
                        ),
                        ButtonElement(
                            text="📊 View Details",
                            action_id="view_details",
                            value=request.id,
                            url=f"{settings.API_BASE_URL}/opportunities/{request.opportunity_id}"
                        )
                    ]
                ),
                ContextBlock(
                    elements=[
                        f"Request ID: `{request.id}`",
                        f"Approval expires in {self._get_time_until_expiry(request.expires_at)}"
                    ]
                )
            ]
            
            # Send message
            response = await self.slack_client.chat_postMessage(
                channel=request.approver_id,
                blocks=blocks,
                text=f"Cost optimization approval request for {request.title}"
            )
            
            track_metric("slack_approval_sent", 1)
            
        except Exception as e:
            log_event("slack_approval_send_failed", {
                "request_id": request.id,
                "error": str(e)
            })
            raise
    
    async def _send_teams_approval(self, request: ApprovalRequest):
        """Send approval request via Microsoft Teams."""
        try:
            # Create Teams adaptive card
            adaptive_card = {
                "type": "AdaptiveCard",
                "version": "1.3",
                "body": [
                    {
                        "type": "TextBlock",
                        "text": "💰 Cost Optimization Approval Request",
                        "size": "Large",
                        "weight": "Bolder"
                    },
                    {
                        "type": "FactSet",
                        "facts": [
                            {"title": "Service", "value": request.title},
                            {"title": "Current Cost", "value": f"${request.current_cost:,.2f}"},
                            {"title": "Potential Savings", "value": f"${request.potential_savings:,.2f}"},
                            {"title": "Risk Level", "value": request.risk_level.title()},
                            {"title": "Expires", "value": request.expires_at.strftime('%Y-%m-%d %H:%M UTC')}
                        ]
                    },
                    {
                        "type": "TextBlock",
                        "text": f"**Description:**\n{request.description}",
                        "wrap": True
                    }
                ],
                "actions": [
                    {
                        "type": "Action.Submit",
                        "title": "✅ Approve",
                        "data": {
                            "action": "approve",
                            "request_id": request.id
                        },
                        "style": "positive"
                    },
                    {
                        "type": "Action.Submit",
                        "title": "❌ Reject",
                        "data": {
                            "action": "reject",
                            "request_id": request.id
                        },
                        "style": "destructive"
                    },
                    {
                        "type": "Action.OpenUrl",
                        "title": "📊 View Details",
                        "url": f"{settings.API_BASE_URL}/opportunities/{request.opportunity_id}"
                    }
                ]
            }
            
            # Send message (simplified - in production, you'd use proper Teams API)
            log_event("teams_approval_sent", {
                "request_id": request.id,
                "approver_id": request.approver_id
            })
            
            track_metric("teams_approval_sent", 1)
            
        except Exception as e:
            log_event("teams_approval_send_failed", {
                "request_id": request.id,
                "error": str(e)
            })
            raise
    
    async def _send_email_approval(self, request: ApprovalRequest):
        """Send approval request via email."""
        try:
            # This would integrate with your email service (SendGrid, SES, etc.)
            email_data = {
                "to": request.approver_id,
                "subject": request.title,
                "html": f"""
                <h2>💰 Cost Optimization Approval Request</h2>
                <p><strong>Service:</strong> {request.title}</p>
                <p><strong>Current Cost:</strong> ${request.current_cost:,.2f}</p>
                <p><strong>Potential Savings:</strong> ${request.potential_savings:,.2f}</p>
                <p><strong>Risk Level:</strong> {request.risk_level.title()}</p>
                <p><strong>Expires:</strong> {request.expires_at.strftime('%Y-%m-%d %H:%M UTC')}</p>
                <p><strong>Description:</strong></p>
                <p>{request.description}</p>
                <p>
                    <a href="{request.approval_url}" style="background-color: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">✅ Approve</a>
                    <a href="{request.rejection_url}" style="background-color: #dc3545; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">❌ Reject</a>
                </p>
                """
            }
            
            # Send email (implementation would depend on your email service)
            log_event("email_approval_sent", {
                "request_id": request.id,
                "approver_id": request.approver_id
            })
            
            track_metric("email_approval_sent", 1)
            
        except Exception as e:
            log_event("email_approval_send_failed", {
                "request_id": request.id,
                "error": str(e)
            })
            raise
    
    async def _schedule_expiration_check(self, request: ApprovalRequest):
        """Schedule an expiration check for an approval request."""
        try:
            # Wait until expiration time
            wait_time = (request.expires_at - datetime.now()).total_seconds()
            if wait_time > 0:
                await asyncio.sleep(wait_time)
                
                # Check if request is still pending
                if request.id in self.active_requests:
                    await self._handle_expired_request(request)
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log_event("expiration_check_failed", {
                "request_id": request.id,
                "error": str(e)
            })
    
    async def _handle_expired_request(self, request: ApprovalRequest):
        """Handle an expired approval request."""
        try:
            # Escalate if escalation policy allows
            policy = self.escalation_policies.get(request.metadata.get("policy_key", "default"))
            current_level = request.metadata.get("escalation_level", 0)
            
            if current_level < len(policy["levels"]):
                await self._escalate_request(request, policy["levels"][current_level])
            else:
                # Mark as expired
                await self._process_approval_response(
                    request.id, 
                    ApprovalStatus.EXPIRED, 
                    "Request expired without response"
                )
                
        except Exception as e:
            log_event("expired_request_handling_failed", {
                "request_id": request.id,
                "error": str(e)
            })
    
    async def _escalate_request(self, request: ApprovalRequest, escalation_level: Dict[str, Any]):
        """Escalate an approval request to the next level."""
        try:
            # Update escalation level
            request.metadata["escalation_level"] = escalation_level["level"]
            new_approver = escalation_level["escalate_to"]
            
            # Update approver
            request.approver_id = new_approver
            request.approver_name = await self._get_approver_name(new_approver, request.workflow_type)
            
            # Extend expiration time
            request.expires_at = datetime.now() + timedelta(hours=escalation_level["timeout_hours"])
            
            # Resend request to new approver
            if request.workflow_type == WorkflowType.SLACK:
                await self._send_slack_approval(request)
            elif request.workflow_type == WorkflowType.TEAMS:
                await self._send_teams_approval(request)
            
            # Schedule new expiration check
            asyncio.create_task(self._schedule_expiration_check(request))
            
            log_event("request_escalated", {
                "request_id": request.id,
                "escalation_level": escalation_level["level"],
                "new_approver": new_approver
            })
            
        except Exception as e:
            log_event("request_escalation_failed", {
                "request_id": request.id,
                "error": str(e)
            })
    
    async def process_approval_response(self, request_id: str, action: str, approver_id: str, 
                                      response_message: str = "") -> ApprovalResponse:
        """Process an approval or rejection response."""
        try:
            if request_id not in self.active_requests:
                raise ValueError(f"Approval request {request_id} not found")
            
            request = self.active_requests[request_id]
            
            # Verify approver
            if request.approver_id != approver_id:
                raise ValueError("Approver ID does not match")
            
            # Determine status
            if action == "approve":
                status = ApprovalStatus.APPROVED
            elif action == "reject":
                status = ApprovalStatus.REJECTED
            else:
                raise ValueError(f"Invalid action: {action}")
            
            # Create response
            response = ApprovalResponse(
                request_id=request_id,
                status=status,
                approver_id=approver_id,
                response_message=response_message,
                timestamp=datetime.now()
            )
            
            # Process response
            await self._process_approval_response(request_id, status, response_message)
            
            # Remove from active requests
            del self.active_requests[request_id]
            
            log_event("approval_response_processed", {
                "request_id": request_id,
                "action": action,
                "approver_id": approver_id,
                "status": status.value
            })
            
            return response
            
        except Exception as e:
            log_event("approval_response_processing_failed", {
                "request_id": request_id,
                "error": str(e)
            })
            raise
    
    async def _process_approval_response(self, request_id: str, status: ApprovalStatus, message: str):
        """Process the approval response and update the opportunity."""
        try:
            # Update database
            # This would update the OptimizationOpportunity status in the database
            
            # Send confirmation to approver
            if status == ApprovalStatus.APPROVED:
                await self._send_approval_confirmation(request_id, "approved", message)
            else:
                await self._send_approval_confirmation(request_id, "rejected", message)
            
            # Trigger next steps based on approval status
            if status == ApprovalStatus.APPROVED:
                await self._trigger_optimization_execution(request_id)
            
        except Exception as e:
            log_event("approval_response_processing_failed", {
                "request_id": request_id,
                "error": str(e)
            })
            raise
    
    async def _send_approval_confirmation(self, request_id: str, status: str, message: str):
        """Send confirmation message to approver."""
        # Implementation would send confirmation via the same channel
        log_event("approval_confirmation_sent", {
            "request_id": request_id,
            "status": status
        })
    
    async def _trigger_optimization_execution(self, request_id: str):
        """Trigger the execution of an approved optimization."""
        # This would integrate with the execution service
        log_event("optimization_execution_triggered", {
            "request_id": request_id
        })
    
    async def _save_approval_workflow(self, request: ApprovalRequest):
        """Save approval workflow to database."""
        # Implementation would save to database
        pass
    
    def _get_time_until_expiry(self, expires_at: datetime) -> str:
        """Get human-readable time until expiry."""
        delta = expires_at - datetime.now()
        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    async def get_pending_approvals(self, approver_id: str) -> List[ApprovalRequest]:
        """Get all pending approvals for an approver."""
        pending = []
        for request in self.active_requests.values():
            if request.approver_id == approver_id:
                pending.append(request)
        return pending
    
    async def get_approval_statistics(self) -> Dict[str, Any]:
        """Get approval workflow statistics."""
        total_requests = len(self.active_requests)
        expired_requests = sum(1 for r in self.active_requests.values() 
                             if r.expires_at < datetime.now())
        
        return {
            "active_requests": total_requests,
            "expired_requests": expired_requests,
            "workflow_types": {
                "slack": sum(1 for r in self.active_requests.values() 
                           if r.workflow_type == WorkflowType.SLACK),
                "teams": sum(1 for r in self.active_requests.values() 
                           if r.workflow_type == WorkflowType.TEAMS),
                "email": sum(1 for r in self.active_requests.values() 
                           if r.workflow_type == WorkflowType.EMAIL)
            },
            "average_approval_time_minutes": 45,  # This would be calculated from historical data
            "approval_rate": 0.85  # This would be calculated from historical data
        }
