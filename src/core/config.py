"""
Configuration management for the Autonomous Cloud Cost Optimizer.

This module handles all configuration settings, environment variables,
and application constants.
"""

import os
from typing import List, Optional
from pydantic import BaseSettings, validator
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Application
    APP_NAME: str = "Autonomous Cloud Cost Optimizer"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    
    # Security
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1", "*.yourdomain.com"]
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/cost_optimizer"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Cloud Provider Credentials
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_DEFAULT_REGION: str = "us-east-1"
    
    AZURE_CLIENT_ID: Optional[str] = None
    AZURE_CLIENT_SECRET: Optional[str] = None
    AZURE_TENANT_ID: Optional[str] = None
    AZURE_SUBSCRIPTION_ID: Optional[str] = None
    
    GCP_PROJECT_ID: Optional[str] = None
    GCP_SERVICE_ACCOUNT_KEY: Optional[str] = None
    
    # AI/ML Services
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    
    # Slack Integration
    SLACK_BOT_TOKEN: Optional[str] = None
    SLACK_SIGNING_SECRET: Optional[str] = None
    SLACK_APP_TOKEN: Optional[str] = None
    
    # Microsoft Teams Integration
    TEAMS_APP_ID: Optional[str] = None
    TEAMS_APP_PASSWORD: Optional[str] = None
    TEAMS_TENANT_ID: Optional[str] = None
    
    # Notification Services
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None
    
    SENDGRID_API_KEY: Optional[str] = None
    SENDGRID_FROM_EMAIL: str = "noreply@autonomous-cost-optimizer.com"
    
    # Firebase (Push Notifications)
    FIREBASE_CREDENTIALS_PATH: Optional[str] = None
    
    # Ticketing Systems
    JIRA_URL: Optional[str] = None
    JIRA_USERNAME: Optional[str] = None
    JIRA_API_TOKEN: Optional[str] = None
    
    SERVICENOW_URL: Optional[str] = None
    SERVICENOW_USERNAME: Optional[str] = None
    SERVICENOW_PASSWORD: Optional[str] = None
    
    # Monitoring & Observability
    SENTRY_DSN: Optional[str] = None
    PROMETHEUS_PORT: int = 9090
    
    # Cost Optimization Settings
    OPTIMIZATION_THRESHOLD_PERCENTAGE: float = 10.0
    MAX_OPTIMIZATION_AMOUNT: float = 10000.0
    APPROVAL_TIMEOUT_HOURS: int = 24
    ROLLBACK_TIMEOUT_MINUTES: int = 30
    
    # RAG System
    CHROMA_DB_PATH: str = "./data/chroma_db"
    VECTOR_EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    KNOWLEDGE_BASE_UPDATE_INTERVAL_HOURS: int = 24
    
    # Task Queue
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 100
    RATE_LIMIT_BURST: int = 200
    
    @validator("ENVIRONMENT")
    def validate_environment(cls, v):
        """Validate environment setting."""
        if v not in ["development", "staging", "production"]:
            raise ValueError("Environment must be development, staging, or production")
        return v
    
    @validator("ALLOWED_HOSTS", pre=True)
    def parse_allowed_hosts(cls, v):
        """Parse allowed hosts from string or list."""
        if isinstance(v, str):
            return [host.strip() for host in v.split(",")]
        return v
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()


# Cloud provider specific configurations
CLOUD_PROVIDER_CONFIGS = {
    "aws": {
        "regions": [
            "us-east-1", "us-east-2", "us-west-1", "us-west-2",
            "eu-west-1", "eu-west-2", "eu-central-1", "ap-southeast-1",
            "ap-southeast-2", "ap-northeast-1"
        ],
        "services": [
            "ec2", "rds", "s3", "lambda", "ecs", "eks", "elasticache",
            "redshift", "cloudfront", "route53", "sns", "sqs"
        ]
    },
    "azure": {
        "regions": [
            "eastus", "eastus2", "westus", "westus2", "centralus",
            "northcentralus", "southcentralus", "westcentralus",
            "northeurope", "westeurope", "uksouth", "ukwest"
        ],
        "services": [
            "virtualmachines", "sqldatabase", "storage", "functions",
            "containerservice", "rediscache", "cosmosdb", "cdn",
            "dns", "servicebus", "eventhubs"
        ]
    },
    "gcp": {
        "regions": [
            "us-central1", "us-east1", "us-west1", "us-west2",
            "us-west3", "us-west4", "europe-west1", "europe-west2",
            "europe-west3", "europe-west4", "asia-east1", "asia-southeast1"
        ],
        "services": [
            "compute", "sql", "storage", "cloudfunctions", "gke",
            "memorystore", "bigquery", "cloudcdn", "dns", "pubsub"
        ]
    }
}

# Optimization strategies
OPTIMIZATION_STRATEGIES = {
    "rightsizing": {
        "description": "Adjust instance sizes based on actual usage patterns",
        "impact": "high",
        "risk": "medium",
        "automation_level": "semi"
    },
    "scheduling": {
        "description": "Schedule non-production resources to run only when needed",
        "impact": "high",
        "risk": "low",
        "automation_level": "full"
    },
    "reserved_instances": {
        "description": "Purchase reserved instances for predictable workloads",
        "impact": "high",
        "risk": "low",
        "automation_level": "manual"
    },
    "spot_instances": {
        "description": "Use spot instances for fault-tolerant workloads",
        "impact": "medium",
        "risk": "high",
        "automation_level": "semi"
    },
    "storage_optimization": {
        "description": "Optimize storage classes and lifecycle policies",
        "impact": "medium",
        "risk": "low",
        "automation_level": "full"
    },
    "unused_resources": {
        "description": "Identify and remove unused resources",
        "impact": "high",
        "risk": "low",
        "automation_level": "semi"
    }
}

# Notification templates
NOTIFICATION_TEMPLATES = {
    "optimization_discovered": {
        "subject": "💰 New Cost Optimization Opportunity: {amount} in {service}",
        "body": """
        A new cost optimization opportunity has been identified:
        
        Service: {service}
        Current Cost: ${current_cost}
        Potential Savings: ${savings_amount}
        Optimization Type: {optimization_type}
        
        Click here to approve: {approval_link}
        """,
        "priority": "medium"
    },
    "optimization_executed": {
        "subject": "✅ Cost Optimization Executed Successfully",
        "body": """
        Cost optimization has been successfully executed:
        
        Service: {service}
        Savings Achieved: ${savings_amount}
        Optimization Type: {optimization_type}
        
        View details: {details_link}
        """,
        "priority": "low"
    },
    "optimization_failed": {
        "subject": "❌ Cost Optimization Failed - Rollback Initiated",
        "body": """
        A cost optimization has failed and rollback has been initiated:
        
        Service: {service}
        Failed Optimization: {optimization_type}
        Error: {error_message}
        
        The system has been restored to its previous state.
        """,
        "priority": "high"
    }
}
