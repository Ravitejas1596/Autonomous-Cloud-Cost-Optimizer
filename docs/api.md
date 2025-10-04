# API Documentation

## Overview

The Autonomous Cloud Cost Optimizer provides a comprehensive REST API for managing cost optimization operations, approvals, executions, and monitoring.

## Base URL

```
https://api.autonomous-cost-optimizer.com/api/v1
```

## Authentication

All API requests require authentication using Bearer tokens:

```bash
Authorization: Bearer <your-token>
```

## Rate Limiting

- **Rate Limit**: 100 requests per minute
- **Burst Limit**: 200 requests per minute
- **Headers**: Rate limit information is included in response headers

## Endpoints

### Optimizations

#### Get Optimization Opportunities

```http
GET /optimizations/opportunities
```

**Query Parameters:**
- `limit` (integer, optional): Number of results per page (1-100, default: 10)
- `offset` (integer, optional): Number of results to skip (default: 0)
- `provider` (string, optional): Filter by cloud provider (aws, azure, gcp)
- `optimization_type` (string, optional): Filter by optimization type

**Response:**
```json
{
  "opportunities": [
    {
      "id": "opt_1234567890",
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
      "created_at": "2024-01-15T10:30:00Z",
      "expires_at": "2024-01-22T10:30:00Z"
    }
  ],
  "pagination": {
    "total": 47,
    "limit": 10,
    "offset": 0,
    "has_more": true
  }
}
```

#### Get Optimization Opportunity Details

```http
GET /optimizations/opportunities/{opportunity_id}
```

**Response:**
```json
{
  "id": "opt_1234567890",
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
  "created_at": "2024-01-15T10:30:00Z",
  "expires_at": "2024-01-22T10:30:00Z"
}
```

#### Approve Optimization Opportunity

```http
POST /optimizations/opportunities/{opportunity_id}/approve?approver_id={approver_id}
```

**Response:**
```json
{
  "status": "approved",
  "opportunity_id": "opt_1234567890",
  "approver_id": "user123",
  "approved_at": "2024-01-15T10:35:00Z",
  "message": "Optimization opportunity approved successfully"
}
```

#### Reject Optimization Opportunity

```http
POST /optimizations/opportunities/{opportunity_id}/reject?approver_id={approver_id}&reason={reason}
```

**Response:**
```json
{
  "status": "rejected",
  "opportunity_id": "opt_1234567890",
  "approver_id": "user123",
  "rejected_at": "2024-01-15T10:35:00Z",
  "reason": "Not suitable for production environment",
  "message": "Optimization opportunity rejected"
}
```

#### Get Optimization Metrics

```http
GET /optimizations/metrics
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "total_recommendations": 47,
    "total_potential_savings": 15420.50,
    "optimizations_executed": 23,
    "total_savings_achieved": 8930.25,
    "success_rate": 0.987,
    "average_approval_time_minutes": 45,
    "active_optimizations": 8,
    "pending_approvals": 3,
    "last_analysis_time": "2024-01-15T10:30:00Z",
    "next_scheduled_analysis": "2024-01-15T14:30:00Z"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### Trigger Optimization Analysis

```http
POST /optimizations/analyze
```

**Response:**
```json
{
  "status": "started",
  "message": "Optimization analysis started in background",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Approvals

#### Get Pending Approvals

```http
GET /approvals/pending?approver_id={approver_id}
```

**Response:**
```json
{
  "approvals": [
    {
      "id": "approval_1234567890",
      "opportunity_id": "opt_1234567890",
      "workflow_type": "slack",
      "approver_id": "user123",
      "title": "Cost Optimization Request: EC2 Instance",
      "description": "Right-size t3.large instance to t3.medium",
      "current_cost": 85.50,
      "potential_savings": 34.20,
      "risk_level": "low",
      "expires_at": "2024-01-16T10:30:00Z",
      "requested_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

#### Get Approval Statistics

```http
GET /approvals/statistics
```

**Response:**
```json
{
  "active_requests": 3,
  "expired_requests": 1,
  "workflow_types": {
    "slack": 2,
    "teams": 1,
    "email": 0
  },
  "average_approval_time_minutes": 45,
  "approval_rate": 0.85
}
```

### Executions

#### Get Execution Status

```http
GET /executions/{execution_id}
```

**Response:**
```json
{
  "execution_id": "exec_1234567890",
  "opportunity_id": "opt_1234567890",
  "status": "running",
  "started_at": "2024-01-15T10:35:00Z",
  "progress": {
    "current_step": "Execution",
    "steps_completed": 3,
    "total_steps": 6,
    "estimated_completion": "2024-01-15T10:50:00Z"
  },
  "context": {
    "resource_id": "i-1234567890abcdef0",
    "cloud_provider": "aws",
    "optimization_type": "rightsizing"
  },
  "is_active": true
}
```

#### Cancel Execution

```http
POST /executions/{execution_id}/cancel?reason={reason}
```

**Response:**
```json
{
  "status": "cancelled",
  "execution_id": "exec_1234567890",
  "reason": "Manual cancellation requested",
  "cancelled_at": "2024-01-15T10:40:00Z",
  "rollback_status": "completed"
}
```

### Notifications

#### Get Notification Statistics

```http
GET /notifications/statistics
```

**Response:**
```json
{
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
  "templates_available": 3,
  "last_24h_notifications": 45
}
```

### Analytics

#### Get Cost Analytics

```http
GET /analytics/cost?period={period}&provider={provider}
```

**Query Parameters:**
- `period` (string, optional): Time period (7d, 30d, 90d, 1y, default: 30d)
- `provider` (string, optional): Cloud provider filter

**Response:**
```json
{
  "period": "30d",
  "total_cost": 45670.50,
  "total_savings": 8930.25,
  "savings_percentage": 19.6,
  "breakdown": {
    "aws": {
      "cost": 23450.25,
      "savings": 4567.50,
      "optimizations": 12
    },
    "azure": {
      "cost": 15670.75,
      "savings": 2345.25,
      "optimizations": 8
    },
    "gcp": {
      "cost": 6549.50,
      "savings": 2017.50,
      "optimizations": 3
    }
  },
  "trends": [
    {
      "date": "2024-01-01",
      "cost": 1500.00,
      "savings": 300.00
    }
  ]
}
```

#### Get Performance Metrics

```http
GET /analytics/performance
```

**Response:**
```json
{
  "optimization_success_rate": 0.987,
  "average_execution_time_minutes": 18.5,
  "average_approval_time_minutes": 45.2,
  "rollback_rate": 0.013,
  "customer_satisfaction_score": 4.8,
  "uptime_percentage": 99.95,
  "response_time_ms": 125
}
```

### Health

#### Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0",
  "environment": "production",
  "checks": {
    "database": {
      "status": "healthy",
      "response_time_ms": 25
    },
    "redis": {
      "status": "healthy",
      "response_time_ms": 12
    },
    "cloud_providers": {
      "aws": {"status": "healthy", "response_time_ms": 150},
      "azure": {"status": "healthy", "response_time_ms": 200},
      "gcp": {"status": "healthy", "response_time_ms": 180}
    },
    "external_apis": {
      "slack": {"status": "healthy", "response_time_ms": 300},
      "teams": {"status": "healthy", "response_time_ms": 250}
    }
  }
}
```

## Error Responses

### Standard Error Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": {
      "field": "limit",
      "reason": "Value must be between 1 and 100"
    }
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_1234567890"
}
```

### HTTP Status Codes

- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `429` - Too Many Requests
- `500` - Internal Server Error
- `503` - Service Unavailable

## Webhooks

### Webhook Events

The API supports webhooks for real-time notifications:

- `optimization.discovered` - New optimization opportunity found
- `optimization.approved` - Optimization opportunity approved
- `optimization.rejected` - Optimization opportunity rejected
- `optimization.executed` - Optimization execution completed
- `optimization.failed` - Optimization execution failed

### Webhook Payload Example

```json
{
  "event": "optimization.executed",
  "timestamp": "2024-01-15T10:35:00Z",
  "data": {
    "execution_id": "exec_1234567890",
    "opportunity_id": "opt_1234567890",
    "service_name": "EC2 Instance",
    "actual_savings": 34.20,
    "execution_time": "15 minutes",
    "status": "completed"
  }
}
```

## SDK Examples

### Python SDK

```python
from autonomous_cost_optimizer import CostOptimizerClient

client = CostOptimizerClient(api_key="your-api-key")

# Get optimization opportunities
opportunities = client.optimizations.list_opportunities(
    limit=10,
    provider="aws"
)

# Approve an optimization
client.optimizations.approve(
    opportunity_id="opt_1234567890",
    approver_id="user123"
)

# Get metrics
metrics = client.analytics.get_cost_metrics(period="30d")
```

### JavaScript SDK

```javascript
import { CostOptimizerClient } from 'autonomous-cost-optimizer-js';

const client = new CostOptimizerClient({
  apiKey: 'your-api-key'
});

// Get optimization opportunities
const opportunities = await client.optimizations.listOpportunities({
  limit: 10,
  provider: 'aws'
});

// Approve an optimization
await client.optimizations.approve('opt_1234567890', 'user123');

// Get metrics
const metrics = await client.analytics.getCostMetrics({ period: '30d' });
```

## Rate Limiting

The API implements rate limiting to ensure fair usage:

- **Standard Plan**: 100 requests/minute
- **Professional Plan**: 500 requests/minute
- **Enterprise Plan**: 2000 requests/minute

Rate limit headers are included in all responses:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1642248600
```

## Pagination

List endpoints support cursor-based pagination:

```json
{
  "data": [...],
  "pagination": {
    "cursor": "eyJpZCI6IjEyMzQ1Njc4OTAifQ==",
    "has_more": true,
    "limit": 10
  }
}
```

## Filtering and Sorting

Most list endpoints support filtering and sorting:

```http
GET /optimizations/opportunities?filter[provider]=aws&sort=-created_at&limit=20
```

Available filters and sort options are documented for each endpoint.
