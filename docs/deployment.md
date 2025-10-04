# Deployment Guide

## Overview

This guide covers deploying the Autonomous Cloud Cost Optimizer platform in various environments, from development to production.

## Prerequisites

### System Requirements

- **CPU**: 4+ cores (8+ recommended for production)
- **Memory**: 8GB RAM minimum (16GB+ recommended for production)
- **Storage**: 50GB+ SSD storage
- **Network**: Stable internet connection for cloud provider APIs

### Software Requirements

- **Python**: 3.11+
- **Node.js**: 18+
- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **PostgreSQL**: 13+
- **Redis**: 6.0+

### Cloud Provider Access

- AWS Account with appropriate IAM permissions
- Azure Subscription with Contributor access
- Google Cloud Project with Compute Admin permissions

## Environment Setup

### 1. Clone Repository

```bash
git clone https://github.com/your-org/autonomous-cloud-cost-optimizer.git
cd autonomous-cloud-cost-optimizer
```

### 2. Environment Configuration

Copy the example environment file and configure:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```bash
# Application
APP_NAME="Autonomous Cloud Cost Optimizer"
VERSION="1.0.0"
ENVIRONMENT="production"
DEBUG=false

# Security
SECRET_KEY="your-super-secret-key-change-in-production"
ALLOWED_HOSTS="yourdomain.com,api.yourdomain.com"

# Database
DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/cost_optimizer"
REDIS_URL="redis://localhost:6379/0"

# Cloud Providers
AWS_ACCESS_KEY_ID="your-aws-access-key"
AWS_SECRET_ACCESS_KEY="your-aws-secret-key"
AWS_DEFAULT_REGION="us-east-1"

AZURE_CLIENT_ID="your-azure-client-id"
AZURE_CLIENT_SECRET="your-azure-client-secret"
AZURE_TENANT_ID="your-azure-tenant-id"
AZURE_SUBSCRIPTION_ID="your-azure-subscription-id"

GCP_PROJECT_ID="your-gcp-project-id"
GCP_SERVICE_ACCOUNT_KEY="path/to/service-account-key.json"

# AI/ML Services
OPENAI_API_KEY="your-openai-api-key"

# Slack Integration
SLACK_BOT_TOKEN="xoxb-your-slack-bot-token"
SLACK_SIGNING_SECRET="your-slack-signing-secret"

# Microsoft Teams Integration
TEAMS_APP_ID="your-teams-app-id"
TEAMS_APP_PASSWORD="your-teams-app-password"

# Notification Services
TWILIO_ACCOUNT_SID="your-twilio-account-sid"
TWILIO_AUTH_TOKEN="your-twilio-auth-token"
SENDGRID_API_KEY="your-sendgrid-api-key"

# Monitoring
SENTRY_DSN="your-sentry-dsn"
```

## Deployment Methods

### Method 1: Docker Compose (Recommended)

#### 1. Build and Start Services

```bash
# Build all services
docker-compose build

# Start all services
docker-compose up -d

# Check service status
docker-compose ps
```

#### 2. Initialize Database

```bash
# Run database migrations
docker-compose exec web python -m alembic upgrade head

# Initialize database with seed data
docker-compose exec web python scripts/init_database.py
```

#### 3. Verify Deployment

```bash
# Check application health
curl http://localhost:8000/health

# Check logs
docker-compose logs -f web
```

### Method 2: Kubernetes

#### 1. Create Namespace

```bash
kubectl create namespace cost-optimizer
```

#### 2. Deploy ConfigMap and Secrets

```bash
# Create configmap
kubectl create configmap cost-optimizer-config \
  --from-env-file=.env \
  --namespace=cost-optimizer

# Create secrets for sensitive data
kubectl create secret generic cost-optimizer-secrets \
  --from-literal=database-url="postgresql://user:pass@db:5432/cost_optimizer" \
  --from-literal=redis-url="redis://redis:6379/0" \
  --from-literal=secret-key="your-secret-key" \
  --namespace=cost-optimizer
```

#### 3. Deploy Services

```bash
# Deploy PostgreSQL
kubectl apply -f k8s/postgresql.yaml

# Deploy Redis
kubectl apply -f k8s/redis.yaml

# Deploy Application
kubectl apply -f k8s/application.yaml

# Deploy Ingress
kubectl apply -f k8s/ingress.yaml
```

#### 4. Check Deployment Status

```bash
kubectl get pods -n cost-optimizer
kubectl get services -n cost-optimizer
kubectl get ingress -n cost-optimizer
```

### Method 3: Manual Deployment

#### 1. Install Dependencies

```bash
# Python dependencies
pip install -r requirements.txt

# Node.js dependencies
npm install
```

#### 2. Setup Database

```bash
# Create database
createdb cost_optimizer

# Run migrations
alembic upgrade head

# Initialize with seed data
python scripts/init_database.py
```

#### 3. Start Services

```bash
# Start Redis
redis-server

# Start Application
uvicorn src.main:app --host 0.0.0.0 --port 8000

# Start Background Workers
celery -A src.tasks.celery worker --loglevel=info
```

## Production Deployment

### High Availability Setup

#### 1. Load Balancer Configuration

```yaml
# nginx.conf
upstream cost_optimizer {
    server app1:8000;
    server app2:8000;
    server app3:8000;
}

server {
    listen 80;
    server_name api.yourdomain.com;
    
    location / {
        proxy_pass http://cost_optimizer;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### 2. Database Clustering

```yaml
# PostgreSQL primary-replica setup
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: postgres-cluster
spec:
  instances: 3
  postgresql:
    parameters:
      max_connections: "200"
      shared_buffers: "256MB"
      effective_cache_size: "1GB"
```

#### 3. Redis Clustering

```yaml
# Redis cluster configuration
apiVersion: v1
kind: ConfigMap
metadata:
  name: redis-cluster-config
data:
  redis.conf: |
    cluster-enabled yes
    cluster-config-file nodes.conf
    cluster-node-timeout 5000
    appendonly yes
```

### SSL/TLS Configuration

#### 1. Obtain SSL Certificate

```bash
# Using Let's Encrypt
certbot certonly --nginx -d api.yourdomain.com
```

#### 2. Configure HTTPS

```yaml
# Kubernetes ingress with TLS
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: cost-optimizer-ingress
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - api.yourdomain.com
    secretName: cost-optimizer-tls
  rules:
  - host: api.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: cost-optimizer-service
            port:
              number: 8000
```

### Monitoring and Logging

#### 1. Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'cost-optimizer'
    static_configs:
      - targets: ['app1:9090', 'app2:9090', 'app3:9090']
```

#### 2. Grafana Dashboards

```bash
# Import dashboards
grafana-cli admin reset-admin-password admin
```

#### 3. Log Aggregation

```yaml
# Fluentd configuration
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluentd-config
data:
  fluent.conf: |
    <source>
      @type tail
      path /var/log/cost-optimizer/*.log
      pos_file /var/log/fluentd/cost-optimizer.log.pos
      tag cost-optimizer.*
      format json
    </source>
    
    <match cost-optimizer.**>
      @type elasticsearch
      host elasticsearch.logging.svc.cluster.local
      port 9200
      index_name cost-optimizer
    </match>
```

## Scaling Configuration

### Horizontal Scaling

#### 1. Auto-scaling Configuration

```yaml
# Kubernetes HPA
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: cost-optimizer-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: cost-optimizer
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

#### 2. Database Scaling

```bash
# Read replicas for PostgreSQL
kubectl apply -f k8s/postgresql-replica.yaml

# Redis cluster scaling
kubectl scale statefulset redis-cluster --replicas=6
```

### Performance Optimization

#### 1. Application Configuration

```python
# production.py
import multiprocessing

# Gunicorn configuration
bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 30
keepalive = 5
```

#### 2. Database Optimization

```sql
-- PostgreSQL optimization
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
```

## Security Configuration

### 1. Network Security

```yaml
# Network policies
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: cost-optimizer-netpol
spec:
  podSelector:
    matchLabels:
      app: cost-optimizer
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8000
```

### 2. RBAC Configuration

```yaml
# Service account and RBAC
apiVersion: v1
kind: ServiceAccount
metadata:
  name: cost-optimizer-sa
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: cost-optimizer-role
rules:
- apiGroups: [""]
  resources: ["pods", "services"]
  verbs: ["get", "list", "watch"]
```

### 3. Secret Management

```bash
# Using external secret operator
helm install external-secrets external-secrets/external-secrets \
  --set installCRDs=true \
  --namespace external-secrets-system
```

## Backup and Recovery

### 1. Database Backup

```bash
#!/bin/bash
# backup.sh
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump -h localhost -U postgres cost_optimizer > backup_${DATE}.sql
aws s3 cp backup_${DATE}.sql s3://your-backup-bucket/
```

### 2. Application Backup

```bash
#!/bin/bash
# app_backup.sh
kubectl get all -n cost-optimizer -o yaml > app_backup_${DATE}.yaml
kubectl get configmaps -n cost-optimizer -o yaml >> app_backup_${DATE}.yaml
kubectl get secrets -n cost-optimizer -o yaml >> app_backup_${DATE}.yaml
```

### 3. Disaster Recovery

```bash
# Restore from backup
psql -h localhost -U postgres cost_optimizer < backup_20240115_103000.sql
kubectl apply -f app_backup_20240115_103000.yaml
```

## Maintenance

### 1. Regular Updates

```bash
# Update application
git pull origin main
docker-compose build
docker-compose up -d

# Update dependencies
pip install -r requirements.txt --upgrade
npm update
```

### 2. Health Checks

```bash
# Automated health checks
curl -f http://localhost:8000/health || exit 1
```

### 3. Log Rotation

```yaml
# Logrotate configuration
/var/log/cost-optimizer/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 app app
    postrotate
        docker-compose restart web
    endscript
}
```

## Troubleshooting

### Common Issues

#### 1. Database Connection Issues

```bash
# Check database connectivity
psql -h localhost -U postgres -d cost_optimizer -c "SELECT 1;"

# Check connection pool
docker-compose logs web | grep "database"
```

#### 2. Redis Connection Issues

```bash
# Test Redis connection
redis-cli ping

# Check Redis memory usage
redis-cli info memory
```

#### 3. Cloud Provider API Issues

```bash
# Test AWS connectivity
aws sts get-caller-identity

# Test Azure connectivity
az account show

# Test GCP connectivity
gcloud auth list
```

### Performance Issues

#### 1. High CPU Usage

```bash
# Check application metrics
curl http://localhost:9090/metrics | grep cpu

# Check system resources
top -p $(pgrep -f "uvicorn")
```

#### 2. Memory Issues

```bash
# Check memory usage
free -h
docker stats

# Check for memory leaks
curl http://localhost:9090/metrics | grep memory
```

#### 3. Database Performance

```sql
-- Check slow queries
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;

-- Check database size
SELECT pg_size_pretty(pg_database_size('cost_optimizer'));
```

## Support

For deployment support:

- **Documentation**: [docs.autonomous-cost-optimizer.com](https://docs.autonomous-cost-optimizer.com)
- **Support Email**: support@autonomous-cost-optimizer.com
- **GitHub Issues**: [github.com/your-org/autonomous-cloud-cost-optimizer/issues](https://github.com/your-org/autonomous-cloud-cost-optimizer/issues)
- **Community Slack**: [autonomous-cost-optimizer.slack.com](https://autonomous-cost-optimizer.slack.com)
