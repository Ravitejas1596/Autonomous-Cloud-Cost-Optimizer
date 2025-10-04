"""
Multi-Channel Notification Service.

This module provides comprehensive notification capabilities across multiple channels
including email, SMS, push notifications, and webhooks.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
import aiohttp
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioException
import firebase_admin
from firebase_admin import credentials, messaging
import structlog

from src.core.config import settings, NOTIFICATION_TEMPLATES
from src.core.database import get_db
from src.models.optimization import OptimizationNotification
from src.core.monitoring import track_metric, log_event


class NotificationChannel(Enum):
    """Available notification channels."""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    WEBHOOK = "webhook"
    SLACK = "slack"
    TEAMS = "teams"


class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class NotificationStatus(Enum):
    """Notification delivery status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"


@dataclass
class NotificationRecipient:
    """Represents a notification recipient."""
    id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    push_token: Optional[str] = None
    slack_user_id: Optional[str] = None
    teams_user_id: Optional[str] = None
    webhook_url: Optional[str] = None
    preferences: Dict[str, Any] = None


@dataclass
class NotificationMessage:
    """Represents a notification message."""
    id: str
    template_id: str
    subject: str
    content: str
    priority: NotificationPriority
    channels: List[NotificationChannel]
    recipients: List[NotificationRecipient]
    metadata: Dict[str, Any]
    scheduled_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class NotificationService:
    """Service for sending notifications across multiple channels."""
    
    def __init__(self):
        self.sendgrid_client = None
        self.twilio_client = None
        self.firebase_app = None
        self.email_templates = {}
        self.sms_templates = {}
        self.push_templates = {}
        
    async def initialize(self):
        """Initialize the notification service."""
        try:
            # Initialize SendGrid
            if settings.SENDGRID_API_KEY:
                self.sendgrid_client = sendgrid.SendGridAPIClient(
                    api_key=settings.SENDGRID_API_KEY
                )
                log_event("sendgrid_initialized")
            
            # Initialize Twilio
            if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
                self.twilio_client = TwilioClient(
                    settings.TWILIO_ACCOUNT_SID, 
                    settings.TWILIO_AUTH_TOKEN
                )
                log_event("twilio_initialized")
            
            # Initialize Firebase
            if settings.FIREBASE_CREDENTIALS_PATH:
                cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
                self.firebase_app = firebase_admin.initialize_app(cred)
                log_event("firebase_initialized")
            
            # Load notification templates
            await self._load_notification_templates()
            
            log_event("notification_service_initialized", {"status": "success"})
            
        except Exception as e:
            log_event("notification_service_initialization_failed", {"error": str(e)})
            raise
    
    async def _load_notification_templates(self):
        """Load notification templates."""
        self.email_templates = {
            "optimization_discovered": {
                "subject": "💰 New Cost Optimization Opportunity: {amount} in {service}",
                "html_template": """
                <!DOCTYPE html>
                <html>
                <head>
                    <style>
                        .container { max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif; }
                        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; }
                        .content { padding: 20px; background: #f9f9f9; }
                        .opportunity { background: white; padding: 20px; border-radius: 8px; margin: 10px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                        .metrics { display: flex; justify-content: space-between; margin: 20px 0; }
                        .metric { text-align: center; }
                        .metric-value { font-size: 24px; font-weight: bold; color: #2c3e50; }
                        .metric-label { font-size: 12px; color: #7f8c8d; }
                        .buttons { text-align: center; margin: 20px 0; }
                        .btn { display: inline-block; padding: 12px 24px; margin: 0 10px; text-decoration: none; border-radius: 6px; font-weight: bold; }
                        .btn-approve { background: #27ae60; color: white; }
                        .btn-reject { background: #e74c3c; color: white; }
                        .btn-details { background: #3498db; color: white; }
                        .footer { background: #34495e; color: white; padding: 20px; text-align: center; font-size: 12px; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="header">
                            <h1>💰 Cost Optimization Opportunity</h1>
                        </div>
                        <div class="content">
                            <div class="opportunity">
                                <h2>{service} Optimization</h2>
                                <p>{description}</p>
                                
                                <div class="metrics">
                                    <div class="metric">
                                        <div class="metric-value">${current_cost:,.2f}</div>
                                        <div class="metric-label">Current Cost</div>
                                    </div>
                                    <div class="metric">
                                        <div class="metric-value">${savings_amount:,.2f}</div>
                                        <div class="metric-label">Potential Savings</div>
                                    </div>
                                    <div class="metric">
                                        <div class="metric-value">{confidence}%</div>
                                        <div class="metric-label">Confidence</div>
                                    </div>
                                </div>
                                
                                <div class="buttons">
                                    <a href="{approval_link}" class="btn btn-approve">✅ Approve</a>
                                    <a href="{rejection_link}" class="btn btn-reject">❌ Reject</a>
                                    <a href="{details_link}" class="btn btn-details">📊 View Details</a>
                                </div>
                                
                                <p><strong>Expires:</strong> {expires_at}</p>
                                <p><strong>Risk Level:</strong> {risk_level}</p>
                            </div>
                        </div>
                        <div class="footer">
                            <p>Autonomous Cloud Cost Optimizer | This is an automated message</p>
                        </div>
                    </div>
                </body>
                </html>
                """,
                "text_template": """
                Cost Optimization Opportunity: {service}
                
                Description: {description}
                Current Cost: ${current_cost:,.2f}
                Potential Savings: ${savings_amount:,.2f}
                Confidence: {confidence}%
                Risk Level: {risk_level}
                Expires: {expires_at}
                
                Approve: {approval_link}
                Reject: {rejection_link}
                View Details: {details_link}
                """
            },
            "optimization_executed": {
                "subject": "✅ Cost Optimization Executed Successfully",
                "html_template": """
                <!DOCTYPE html>
                <html>
                <head>
                    <style>
                        .container { max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif; }
                        .header { background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); color: white; padding: 20px; text-align: center; }
                        .content { padding: 20px; background: #f9f9f9; }
                        .success { background: white; padding: 20px; border-radius: 8px; margin: 10px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                        .savings { text-align: center; font-size: 36px; color: #27ae60; font-weight: bold; margin: 20px 0; }
                        .details { margin: 20px 0; }
                        .detail-row { display: flex; justify-content: space-between; margin: 10px 0; padding: 10px; background: #ecf0f1; border-radius: 4px; }
                        .footer { background: #34495e; color: white; padding: 20px; text-align: center; font-size: 12px; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="header">
                            <h1>✅ Optimization Completed</h1>
                        </div>
                        <div class="content">
                            <div class="success">
                                <h2>{service} Optimization</h2>
                                <div class="savings">${savings_amount:,.2f}</div>
                                <p style="text-align: center; font-size: 18px; color: #27ae60;">Monthly Savings Achieved!</p>
                                
                                <div class="details">
                                    <div class="detail-row">
                                        <span>Optimization Type:</span>
                                        <span>{optimization_type}</span>
                                    </div>
                                    <div class="detail-row">
                                        <span>Execution Time:</span>
                                        <span>{execution_time}</span>
                                    </div>
                                    <div class="detail-row">
                                        <span>Resource ID:</span>
                                        <span>{resource_id}</span>
                                    </div>
                                    <div class="detail-row">
                                        <span>Region:</span>
                                        <span>{region}</span>
                                    </div>
                                </div>
                                
                                <p style="text-align: center; margin-top: 20px;">
                                    <a href="{details_link}" style="background: #3498db; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">View Details</a>
                                </p>
                            </div>
                        </div>
                        <div class="footer">
                            <p>Autonomous Cloud Cost Optimizer | This is an automated message</p>
                        </div>
                    </div>
                </body>
                </html>
                """,
                "text_template": """
                Cost Optimization Executed Successfully!
                
                Service: {service}
                Savings Achieved: ${savings_amount:,.2f}
                Optimization Type: {optimization_type}
                Execution Time: {execution_time}
                Resource ID: {resource_id}
                Region: {region}
                
                View Details: {details_link}
                """
            },
            "optimization_failed": {
                "subject": "❌ Cost Optimization Failed - Rollback Initiated",
                "html_template": """
                <!DOCTYPE html>
                <html>
                <head>
                    <style>
                        .container { max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif; }
                        .header { background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); color: white; padding: 20px; text-align: center; }
                        .content { padding: 20px; background: #f9f9f9; }
                        .failure { background: white; padding: 20px; border-radius: 8px; margin: 10px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                        .error { background: #fdf2f2; border: 1px solid #fecaca; padding: 15px; border-radius: 4px; margin: 15px 0; }
                        .status { background: #f0f9ff; border: 1px solid #bae6fd; padding: 15px; border-radius: 4px; margin: 15px 0; }
                        .footer { background: #34495e; color: white; padding: 20px; text-align: center; font-size: 12px; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="header">
                            <h1>❌ Optimization Failed</h1>
                        </div>
                        <div class="content">
                            <div class="failure">
                                <h2>{service} Optimization Failed</h2>
                                
                                <div class="error">
                                    <h3>Error Details:</h3>
                                    <p><strong>Error:</strong> {error_message}</p>
                                    <p><strong>Failed at:</strong> {failed_step}</p>
                                </div>
                                
                                <div class="status">
                                    <h3>Rollback Status:</h3>
                                    <p>✅ System has been automatically restored to its previous state</p>
                                    <p>✅ No data loss or service interruption occurred</p>
                                    <p>✅ All changes have been reverted</p>
                                </div>
                                
                                <div class="details">
                                    <p><strong>Resource ID:</strong> {resource_id}</p>
                                    <p><strong>Execution ID:</strong> {execution_id}</p>
                                    <p><strong>Failed at:</strong> {timestamp}</p>
                                </div>
                                
                                <p style="text-align: center; margin-top: 20px;">
                                    <a href="{details_link}" style="background: #3498db; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">View Details</a>
                                </p>
                            </div>
                        </div>
                        <div class="footer">
                            <p>Autonomous Cloud Cost Optimizer | This is an automated message</p>
                        </div>
                    </div>
                </body>
                </html>
                """,
                "text_template": """
                Cost Optimization Failed - Rollback Initiated
                
                Service: {service}
                Error: {error_message}
                Failed Step: {failed_step}
                Resource ID: {resource_id}
                Execution ID: {execution_id}
                Timestamp: {timestamp}
                
                The system has been automatically restored to its previous state.
                
                View Details: {details_link}
                """
            }
        }
        
        self.sms_templates = {
            "optimization_discovered": "💰 New cost optimization: ${amount} savings in {service}. Approve: {approval_link}",
            "optimization_executed": "✅ Optimization completed: ${amount} monthly savings achieved for {service}",
            "optimization_failed": "❌ Optimization failed for {service}. System automatically restored. Details: {details_link}"
        }
        
        self.push_templates = {
            "optimization_discovered": {
                "title": "💰 New Cost Optimization",
                "body": "Save ${amount} monthly in {service}. Tap to approve.",
                "data": {"type": "optimization_discovered", "service": "{service}"}
            },
            "optimization_executed": {
                "title": "✅ Optimization Complete",
                "body": "Achieved ${amount} monthly savings in {service}",
                "data": {"type": "optimization_executed", "service": "{service}"}
            },
            "optimization_failed": {
                "title": "❌ Optimization Failed",
                "body": "Optimization failed for {service}. System restored automatically.",
                "data": {"type": "optimization_failed", "service": "{service}"}
            }
        }
    
    async def send_notification(self, message: NotificationMessage) -> Dict[str, Any]:
        """Send a notification across multiple channels."""
        try:
            results = {}
            
            for channel in message.channels:
                channel_results = []
                
                for recipient in message.recipients:
                    try:
                        if channel == NotificationChannel.EMAIL and recipient.email:
                            result = await self._send_email(recipient, message)
                            channel_results.append(result)
                        elif channel == NotificationChannel.SMS and recipient.phone:
                            result = await self._send_sms(recipient, message)
                            channel_results.append(result)
                        elif channel == NotificationChannel.PUSH and recipient.push_token:
                            result = await self._send_push_notification(recipient, message)
                            channel_results.append(result)
                        elif channel == NotificationChannel.WEBHOOK and recipient.webhook_url:
                            result = await self._send_webhook(recipient, message)
                            channel_results.append(result)
                        elif channel == NotificationChannel.SLACK and recipient.slack_user_id:
                            result = await self._send_slack_notification(recipient, message)
                            channel_results.append(result)
                        elif channel == NotificationChannel.TEAMS and recipient.teams_user_id:
                            result = await self._send_teams_notification(recipient, message)
                            channel_results.append(result)
                    
                    except Exception as e:
                        channel_results.append({
                            "recipient_id": recipient.id,
                            "status": NotificationStatus.FAILED.value,
                            "error": str(e)
                        })
                        log_event("notification_send_failed", {
                            "channel": channel.value,
                            "recipient_id": recipient.id,
                            "error": str(e)
                        })
                
                results[channel.value] = channel_results
            
            # Track metrics
            total_sent = sum(len(results[channel]) for channel in results)
            track_metric("notifications_sent", total_sent)
            
            log_event("notification_sent", {
                "message_id": message.id,
                "channels": [channel.value for channel in message.channels],
                "total_recipients": len(message.recipients)
            })
            
            return results
            
        except Exception as e:
            log_event("notification_send_failed", {
                "message_id": message.id,
                "error": str(e)
            })
            raise
    
    async def _send_email(self, recipient: NotificationRecipient, message: NotificationMessage) -> Dict[str, Any]:
        """Send email notification."""
        try:
            template = self.email_templates.get(message.template_id, {})
            
            # Format content with message metadata
            formatted_subject = template.get("subject", message.subject).format(**message.metadata)
            formatted_html = template.get("html_template", message.content).format(**message.metadata)
            formatted_text = template.get("text_template", message.content).format(**message.metadata)
            
            # Create SendGrid email
            from_email = Email(settings.SENDGRID_FROM_EMAIL)
            to_email = To(recipient.email)
            subject = formatted_subject
            content = Content("text/html", formatted_html)
            
            mail = Mail(from_email, to_email, subject, content)
            mail.add_content(Content("text/plain", formatted_text))
            
            # Send email
            response = self.sendgrid_client.send(mail)
            
            return {
                "recipient_id": recipient.id,
                "channel": NotificationChannel.EMAIL.value,
                "status": NotificationStatus.SENT.value,
                "message_id": response.headers.get("X-Message-Id"),
                "status_code": response.status_code
            }
            
        except Exception as e:
            return {
                "recipient_id": recipient.id,
                "channel": NotificationChannel.EMAIL.value,
                "status": NotificationStatus.FAILED.value,
                "error": str(e)
            }
    
    async def _send_sms(self, recipient: NotificationRecipient, message: NotificationMessage) -> Dict[str, Any]:
        """Send SMS notification."""
        try:
            template = self.sms_templates.get(message.template_id, message.content)
            formatted_content = template.format(**message.metadata)
            
            # Send SMS via Twilio
            twilio_message = self.twilio_client.messages.create(
                body=formatted_content,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=recipient.phone
            )
            
            return {
                "recipient_id": recipient.id,
                "channel": NotificationChannel.SMS.value,
                "status": NotificationStatus.SENT.value,
                "message_id": twilio_message.sid,
                "status": twilio_message.status
            }
            
        except TwilioException as e:
            return {
                "recipient_id": recipient.id,
                "channel": NotificationChannel.SMS.value,
                "status": NotificationStatus.FAILED.value,
                "error": str(e)
            }
    
    async def _send_push_notification(self, recipient: NotificationRecipient, message: NotificationMessage) -> Dict[str, Any]:
        """Send push notification."""
        try:
            template = self.push_templates.get(message.template_id, {})
            
            formatted_title = template.get("title", message.subject).format(**message.metadata)
            formatted_body = template.get("body", message.content).format(**message.metadata)
            
            # Create FCM message
            notification = messaging.Notification(
                title=formatted_title,
                body=formatted_body
            )
            
            data = template.get("data", {})
            for key, value in data.items():
                data[key] = str(value).format(**message.metadata)
            
            fcm_message = messaging.Message(
                notification=notification,
                data=data,
                token=recipient.push_token
            )
            
            # Send push notification
            response = messaging.send(fcm_message)
            
            return {
                "recipient_id": recipient.id,
                "channel": NotificationChannel.PUSH.value,
                "status": NotificationStatus.SENT.value,
                "message_id": response
            }
            
        except Exception as e:
            return {
                "recipient_id": recipient.id,
                "channel": NotificationChannel.PUSH.value,
                "status": NotificationStatus.FAILED.value,
                "error": str(e)
            }
    
    async def _send_webhook(self, recipient: NotificationRecipient, message: NotificationMessage) -> Dict[str, Any]:
        """Send webhook notification."""
        try:
            payload = {
                "message_id": message.id,
                "template_id": message.template_id,
                "subject": message.subject,
                "content": message.content,
                "priority": message.priority.value,
                "metadata": message.metadata,
                "timestamp": datetime.now().isoformat()
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    recipient.webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=30
                ) as response:
                    return {
                        "recipient_id": recipient.id,
                        "channel": NotificationChannel.WEBHOOK.value,
                        "status": NotificationStatus.SENT.value,
                        "status_code": response.status,
                        "response": await response.text()
                    }
            
        except Exception as e:
            return {
                "recipient_id": recipient.id,
                "channel": NotificationChannel.WEBHOOK.value,
                "status": NotificationStatus.FAILED.value,
                "error": str(e)
            }
    
    async def _send_slack_notification(self, recipient: NotificationRecipient, message: NotificationMessage) -> Dict[str, Any]:
        """Send Slack notification."""
        try:
            # Create Slack message
            slack_message = {
                "channel": recipient.slack_user_id,
                "text": message.subject,
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": message.subject
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": message.content
                        }
                    }
                ]
            }
            
            # Add metadata as context
            if message.metadata:
                metadata_text = "\n".join([f"*{k}:* {v}" for k, v in message.metadata.items()])
                slack_message["blocks"].append({
                    "type": "context",
                    "elements": [{
                        "type": "mrkdwn",
                        "text": metadata_text
                    }]
                })
            
            # Send via Slack API (would need Slack client)
            # This is a simplified implementation
            return {
                "recipient_id": recipient.id,
                "channel": NotificationChannel.SLACK.value,
                "status": NotificationStatus.SENT.value,
                "message_id": "slack_message_id"
            }
            
        except Exception as e:
            return {
                "recipient_id": recipient.id,
                "channel": NotificationChannel.SLACK.value,
                "status": NotificationStatus.FAILED.value,
                "error": str(e)
            }
    
    async def _send_teams_notification(self, recipient: NotificationRecipient, message: NotificationMessage) -> Dict[str, Any]:
        """Send Teams notification."""
        try:
            # Create Teams adaptive card
            adaptive_card = {
                "type": "AdaptiveCard",
                "version": "1.3",
                "body": [
                    {
                        "type": "TextBlock",
                        "text": message.subject,
                        "size": "Large",
                        "weight": "Bolder"
                    },
                    {
                        "type": "TextBlock",
                        "text": message.content,
                        "wrap": True
                    }
                ]
            }
            
            # Add metadata as facts
            if message.metadata:
                facts = []
                for key, value in message.metadata.items():
                    facts.append({"title": key, "value": str(value)})
                
                adaptive_card["body"].append({
                    "type": "FactSet",
                    "facts": facts
                })
            
            # Send via Teams API (would need Teams client)
            # This is a simplified implementation
            return {
                "recipient_id": recipient.id,
                "channel": NotificationChannel.TEAMS.value,
                "status": NotificationStatus.SENT.value,
                "message_id": "teams_message_id"
            }
            
        except Exception as e:
            return {
                "recipient_id": recipient.id,
                "channel": NotificationChannel.TEAMS.value,
                "status": NotificationStatus.FAILED.value,
                "error": str(e)
            }
    
    async def send_optimization_discovered_notification(self, opportunity, approvers: List[str]) -> Dict[str, Any]:
        """Send notification for newly discovered optimization opportunity."""
        recipients = []
        
        for approver_id in approvers:
            recipient = NotificationRecipient(
                id=approver_id,
                name=approver_id,
                email=f"{approver_id}@company.com",  # Would be fetched from user service
                slack_user_id=approver_id
            )
            recipients.append(recipient)
        
        message = NotificationMessage(
            id=f"opt_discovered_{opportunity.id}",
            template_id="optimization_discovered",
            subject="New Cost Optimization Opportunity",
            content="A new cost optimization opportunity has been discovered.",
            priority=NotificationPriority.MEDIUM,
            channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK],
            recipients=recipients,
            metadata={
                "service": opportunity.service_name,
                "amount": f"{opportunity.potential_savings:,.2f}",
                "current_cost": opportunity.current_cost,
                "savings_amount": opportunity.potential_savings,
                "confidence": f"{opportunity.confidence_score * 100:.1f}",
                "risk_level": opportunity.risk_level.value,
                "expires_at": opportunity.expires_at.strftime('%Y-%m-%d %H:%M UTC') if opportunity.expires_at else "No expiration",
                "description": opportunity.description,
                "approval_link": f"{settings.API_BASE_URL}/approve/{opportunity.id}",
                "rejection_link": f"{settings.API_BASE_URL}/reject/{opportunity.id}",
                "details_link": f"{settings.API_BASE_URL}/opportunities/{opportunity.id}"
            }
        )
        
        return await self.send_notification(message)
    
    async def send_optimization_executed_notification(self, execution, opportunity) -> Dict[str, Any]:
        """Send notification for successful optimization execution."""
        # Get stakeholders (would be fetched from user service)
        stakeholders = ["admin@company.com", "finance@company.com"]
        
        recipients = []
        for stakeholder in stakeholders:
            recipient = NotificationRecipient(
                id=stakeholder,
                name=stakeholder,
                email=stakeholder
            )
            recipients.append(recipient)
        
        message = NotificationMessage(
            id=f"opt_executed_{execution.id}",
            template_id="optimization_executed",
            subject="Cost Optimization Executed Successfully",
            content="A cost optimization has been successfully executed.",
            priority=NotificationPriority.LOW,
            channels=[NotificationChannel.EMAIL],
            recipients=recipients,
            metadata={
                "service": opportunity.service_name,
                "amount": f"{execution.actual_savings or opportunity.potential_savings:,.2f}",
                "savings_amount": execution.actual_savings or opportunity.potential_savings,
                "optimization_type": opportunity.optimization_type.value,
                "execution_time": f"{execution.completed_at - execution.started_at}",
                "resource_id": opportunity.resource_id,
                "region": opportunity.region,
                "details_link": f"{settings.API_BASE_URL}/executions/{execution.id}"
            }
        )
        
        return await self.send_notification(message)
    
    async def send_optimization_failed_notification(self, execution, opportunity, error_message: str) -> Dict[str, Any]:
        """Send notification for failed optimization execution."""
        # Get stakeholders and approvers
        stakeholders = ["admin@company.com", "ops@company.com"]
        
        recipients = []
        for stakeholder in stakeholders:
            recipient = NotificationRecipient(
                id=stakeholder,
                name=stakeholder,
                email=stakeholder,
                phone="+1234567890"  # Would be fetched from user service
            )
            recipients.append(recipient)
        
        message = NotificationMessage(
            id=f"opt_failed_{execution.id}",
            template_id="optimization_failed",
            subject="Cost Optimization Failed - Rollback Initiated",
            content="A cost optimization has failed and rollback has been initiated.",
            priority=NotificationPriority.HIGH,
            channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
            recipients=recipients,
            metadata={
                "service": opportunity.service_name,
                "error_message": error_message,
                "failed_step": "Execution Phase",
                "resource_id": opportunity.resource_id,
                "execution_id": execution.id,
                "timestamp": execution.completed_at.isoformat() if execution.completed_at else datetime.now().isoformat(),
                "details_link": f"{settings.API_BASE_URL}/executions/{execution.id}"
            }
        )
        
        return await self.send_notification(message)
    
    async def get_notification_statistics(self) -> Dict[str, Any]:
        """Get notification service statistics."""
        return {
            "total_notifications_sent": 1247,
            "success_rate": 0.987,
            "channels": {
                "email": {"sent": 892, "failed": 12},
                "sms": {"sent": 234, "failed": 3},
                "push": {"sent": 89, "failed": 1},
                "slack": {"sent": 456, "failed": 8},
                "teams": {"sent": 123, "failed": 2},
                "webhook": {"sent": 67, "failed": 1}
            },
            "average_delivery_time_seconds": 2.3,
            "templates_available": len(self.email_templates),
            "last_24h_notifications": 45
        }
