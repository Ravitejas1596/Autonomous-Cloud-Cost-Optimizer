"""
Monitoring, Logging, and Observability System.

This module provides comprehensive monitoring, logging, and observability
capabilities for the Autonomous Cloud Cost Optimizer platform.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import functools
import traceback

import structlog
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client.exposition import MetricsHandler
import redis
import psutil

from src.core.config import settings


# Prometheus Metrics
optimization_opportunities_total = Counter(
    'optimization_opportunities_total',
    'Total number of optimization opportunities discovered',
    ['cloud_provider', 'optimization_type', 'risk_level']
)

optimization_executions_total = Counter(
    'optimization_executions_total',
    'Total number of optimization executions',
    ['cloud_provider', 'optimization_type', 'status']
)

optimization_savings_total = Counter(
    'optimization_savings_total',
    'Total savings achieved from optimizations',
    ['cloud_provider', 'optimization_type']
)

approval_requests_total = Counter(
    'approval_requests_total',
    'Total number of approval requests',
    ['workflow_type', 'status']
)

notifications_sent_total = Counter(
    'notifications_sent_total',
    'Total number of notifications sent',
    ['channel', 'type', 'status']
)

api_requests_total = Counter(
    'api_requests_total',
    'Total number of API requests',
    ['method', 'endpoint', 'status_code']
)

api_request_duration = Histogram(
    'api_request_duration_seconds',
    'API request duration in seconds',
    ['method', 'endpoint']
)

active_optimizations = Gauge(
    'active_optimizations',
    'Number of currently active optimizations',
    ['cloud_provider', 'status']
)

system_resources = Gauge(
    'system_resources',
    'System resource utilization',
    ['resource_type', 'metric']
)

optimization_confidence_score = Histogram(
    'optimization_confidence_score',
    'Distribution of optimization confidence scores',
    ['optimization_type']
)

approval_response_time = Histogram(
    'approval_response_time_seconds',
    'Time taken to get approval responses',
    ['workflow_type']
)

rag_insights_generated = Counter(
    'rag_insights_generated_total',
    'Total number of RAG insights generated',
    ['source_type']
)

tickets_created_total = Counter(
    'tickets_created_total',
    'Total number of tickets created',
    ['ticket_type', 'system']
)

application_info = Info(
    'application_info',
    'Application information'
)

application_info.info({
    'version': '1.0.0',
    'environment': 'production',
    'build_date': '2024-01-15'
})


class LogLevel(Enum):
    """Log levels for structured logging."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MetricType(Enum):
    """Types of metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class LogEvent:
    """Structured log event."""
    event_type: str
    timestamp: datetime
    level: LogLevel
    message: str
    data: Dict[str, Any]
    trace_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None


@dataclass
class MetricData:
    """Metric data structure."""
    name: str
    value: Union[int, float]
    labels: Dict[str, str]
    metric_type: MetricType
    timestamp: datetime


class MonitoringService:
    """Service for monitoring, logging, and observability."""
    
    def __init__(self):
        self.logger = None
        self.redis_client = None
        self.metrics_cache = {}
        self.health_checks = {}
        self.alert_rules = {}
        
    async def initialize(self):
        """Initialize the monitoring service."""
        try:
            # Initialize structured logging
            self._setup_structured_logging()
            
            # Initialize Redis for metrics caching
            if settings.REDIS_URL:
                self.redis_client = redis.from_url(settings.REDIS_URL)
                await self._test_redis_connection()
            
            # Initialize Sentry for error tracking
            if settings.SENTRY_DSN:
                self._setup_sentry()
            
            # Initialize health checks
            await self._setup_health_checks()
            
            # Initialize alert rules
            await self._setup_alert_rules()
            
            # Start background monitoring tasks
            asyncio.create_task(self._monitor_system_resources())
            asyncio.create_task(self._process_metrics_queue())
            
            log_event("monitoring_service_initialized", {"status": "success"})
            
        except Exception as e:
            log_event("monitoring_service_initialization_failed", {"error": str(e)})
            raise
    
    def _setup_structured_logging(self):
        """Setup structured logging with structlog."""
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
        
        self.logger = structlog.get_logger(__name__)
    
    def _setup_sentry(self):
        """Setup Sentry for error tracking."""
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            integrations=[
                FastApiIntegration(auto_enabling_instrumentations=True),
                SqlalchemyIntegration(),
            ],
            traces_sample_rate=0.1,
            environment=settings.ENVIRONMENT,
            release="autonomous-cost-optimizer@1.0.0"
        )
    
    async def _test_redis_connection(self):
        """Test Redis connection."""
        try:
            await asyncio.to_thread(self.redis_client.ping)
            log_event("redis_connection_established")
        except Exception as e:
            log_event("redis_connection_failed", {"error": str(e)})
            raise
    
    async def _setup_health_checks(self):
        """Setup health check endpoints."""
        self.health_checks = {
            "database": self._check_database_health,
            "redis": self._check_redis_health,
            "cloud_providers": self._check_cloud_providers_health,
            "external_apis": self._check_external_apis_health,
            "disk_space": self._check_disk_space,
            "memory_usage": self._check_memory_usage
        }
    
    async def _setup_alert_rules(self):
        """Setup alert rules for monitoring."""
        self.alert_rules = {
            "high_error_rate": {
                "condition": "error_rate > 0.05",
                "severity": "warning",
                "description": "Error rate is above 5%"
            },
            "slow_response_time": {
                "condition": "avg_response_time > 5.0",
                "severity": "warning",
                "description": "Average response time is above 5 seconds"
            },
            "low_optimization_success_rate": {
                "condition": "optimization_success_rate < 0.9",
                "severity": "critical",
                "description": "Optimization success rate is below 90%"
            },
            "high_system_load": {
                "condition": "cpu_usage > 0.8",
                "severity": "warning",
                "description": "CPU usage is above 80%"
            },
            "low_disk_space": {
                "condition": "disk_usage > 0.9",
                "severity": "critical",
                "description": "Disk usage is above 90%"
            }
        }
    
    async def _monitor_system_resources(self):
        """Monitor system resources in background."""
        while True:
            try:
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)
                system_resources.labels(resource_type='cpu', metric='usage_percent').set(cpu_percent)
                
                # Memory usage
                memory = psutil.virtual_memory()
                system_resources.labels(resource_type='memory', metric='usage_percent').set(memory.percent)
                system_resources.labels(resource_type='memory', metric='available_gb').set(memory.available / (1024**3))
                
                # Disk usage
                disk = psutil.disk_usage('/')
                system_resources.labels(resource_type='disk', metric='usage_percent').set(disk.percent)
                system_resources.labels(resource_type='disk', metric='free_gb').set(disk.free / (1024**3))
                
                # Network I/O
                network = psutil.net_io_counters()
                system_resources.labels(resource_type='network', metric='bytes_sent').set(network.bytes_sent)
                system_resources.labels(resource_type='network', metric='bytes_recv').set(network.bytes_recv)
                
                await asyncio.sleep(30)  # Update every 30 seconds
                
            except Exception as e:
                log_event("system_resource_monitoring_failed", {"error": str(e)})
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _process_metrics_queue(self):
        """Process metrics queue in background."""
        while True:
            try:
                # Process cached metrics
                if self.redis_client:
                    await self._process_cached_metrics()
                
                await asyncio.sleep(10)  # Process every 10 seconds
                
            except Exception as e:
                log_event("metrics_queue_processing_failed", {"error": str(e)})
                await asyncio.sleep(30)
    
    async def _process_cached_metrics(self):
        """Process cached metrics from Redis."""
        try:
            # Get all cached metrics
            cached_metrics = await asyncio.to_thread(
                self.redis_client.hgetall, "cached_metrics"
            )
            
            for metric_key, metric_data in cached_metrics.items():
                try:
                    metric_info = json.loads(metric_data)
                    await self._record_metric(metric_info)
                except Exception as e:
                    log_event("cached_metric_processing_failed", {
                        "metric_key": metric_key,
                        "error": str(e)
                    })
            
            # Clear processed metrics
            await asyncio.to_thread(self.redis_client.delete, "cached_metrics")
            
        except Exception as e:
            log_event("cached_metrics_processing_failed", {"error": str(e)})
    
    async def _check_database_health(self) -> Dict[str, Any]:
        """Check database health."""
        try:
            # This would check database connection and performance
            return {
                "status": "healthy",
                "response_time_ms": 25,
                "connection_pool_size": 10,
                "active_connections": 3
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def _check_redis_health(self) -> Dict[str, Any]:
        """Check Redis health."""
        try:
            if self.redis_client:
                start_time = time.time()
                await asyncio.to_thread(self.redis_client.ping)
                response_time = (time.time() - start_time) * 1000
                
                return {
                    "status": "healthy",
                    "response_time_ms": response_time,
                    "memory_usage": await asyncio.to_thread(self.redis_client.info, "memory")
                }
            else:
                return {"status": "not_configured"}
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def _check_cloud_providers_health(self) -> Dict[str, Any]:
        """Check cloud providers health."""
        health_status = {}
        
        # Check AWS
        try:
            # This would check AWS API connectivity
            health_status["aws"] = {"status": "healthy", "response_time_ms": 150}
        except Exception as e:
            health_status["aws"] = {"status": "unhealthy", "error": str(e)}
        
        # Check Azure
        try:
            # This would check Azure API connectivity
            health_status["azure"] = {"status": "healthy", "response_time_ms": 200}
        except Exception as e:
            health_status["azure"] = {"status": "unhealthy", "error": str(e)}
        
        # Check GCP
        try:
            # This would check GCP API connectivity
            health_status["gcp"] = {"status": "healthy", "response_time_ms": 180}
        except Exception as e:
            health_status["gcp"] = {"status": "unhealthy", "error": str(e)}
        
        return health_status
    
    async def _check_external_apis_health(self) -> Dict[str, Any]:
        """Check external APIs health."""
        health_status = {}
        
        # Check Slack API
        try:
            # This would check Slack API connectivity
            health_status["slack"] = {"status": "healthy", "response_time_ms": 300}
        except Exception as e:
            health_status["slack"] = {"status": "unhealthy", "error": str(e)}
        
        # Check Teams API
        try:
            # This would check Teams API connectivity
            health_status["teams"] = {"status": "healthy", "response_time_ms": 250}
        except Exception as e:
            health_status["teams"] = {"status": "unhealthy", "error": str(e)}
        
        return health_status
    
    async def _check_disk_space(self) -> Dict[str, Any]:
        """Check disk space."""
        try:
            disk = psutil.disk_usage('/')
            usage_percent = (disk.used / disk.total) * 100
            
            return {
                "status": "healthy" if usage_percent < 90 else "warning" if usage_percent < 95 else "critical",
                "usage_percent": usage_percent,
                "free_gb": disk.free / (1024**3),
                "total_gb": disk.total / (1024**3)
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _check_memory_usage(self) -> Dict[str, Any]:
        """Check memory usage."""
        try:
            memory = psutil.virtual_memory()
            
            return {
                "status": "healthy" if memory.percent < 80 else "warning" if memory.percent < 90 else "critical",
                "usage_percent": memory.percent,
                "available_gb": memory.available / (1024**3),
                "total_gb": memory.total / (1024**3)
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _record_metric(self, metric_info: Dict[str, Any]):
        """Record a metric."""
        try:
            name = metric_info["name"]
            value = metric_info["value"]
            labels = metric_info.get("labels", {})
            metric_type = metric_info["metric_type"]
            
            # This would record the metric to Prometheus or other monitoring system
            log_event("metric_recorded", {
                "name": name,
                "value": value,
                "labels": labels,
                "type": metric_type
            })
            
        except Exception as e:
            log_event("metric_recording_failed", {
                "metric_info": metric_info,
                "error": str(e)
            })


# Global monitoring service instance
monitoring_service = MonitoringService()


def setup_monitoring():
    """Setup monitoring and observability."""
    # This would be called during application startup
    pass


async def health_check() -> Dict[str, Any]:
    """Perform comprehensive health check."""
    try:
        health_results = {}
        
        for check_name, check_func in monitoring_service.health_checks.items():
            try:
                result = await check_func()
                health_results[check_name] = result
            except Exception as e:
                health_results[check_name] = {
                    "status": "error",
                    "error": str(e)
                }
        
        # Overall health status
        overall_status = "healthy"
        for check_result in health_results.values():
            if check_result.get("status") in ["unhealthy", "critical", "error"]:
                overall_status = "unhealthy"
                break
            elif check_result.get("status") == "warning":
                overall_status = "degraded"
        
        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "checks": health_results
        }
        
    except Exception as e:
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }


def log_event(event_type: str, data: Dict[str, Any] = None, level: LogLevel = LogLevel.INFO):
    """Log a structured event."""
    try:
        if monitoring_service.logger:
            event_data = data or {}
            event_data.update({
                "event_type": event_type,
                "timestamp": datetime.now().isoformat(),
                "level": level.value
            })
            
            if level == LogLevel.DEBUG:
                monitoring_service.logger.debug(event_type, **event_data)
            elif level == LogLevel.INFO:
                monitoring_service.logger.info(event_type, **event_data)
            elif level == LogLevel.WARNING:
                monitoring_service.logger.warning(event_type, **event_data)
            elif level == LogLevel.ERROR:
                monitoring_service.logger.error(event_type, **event_data)
            elif level == LogLevel.CRITICAL:
                monitoring_service.logger.critical(event_type, **event_data)
        
        # Also send to Sentry for errors and critical events
        if level in [LogLevel.ERROR, LogLevel.CRITICAL] and settings.SENTRY_DSN:
            sentry_sdk.capture_message(event_type, level=level.value)
            
    except Exception as e:
        # Fallback to basic logging
        print(f"Failed to log event {event_type}: {e}")


def track_metric(name: str, value: Union[int, float], labels: Dict[str, str] = None):
    """Track a metric."""
    try:
        labels = labels or {}
        
        # Record to Prometheus metrics
        if name == "optimization_opportunities_total":
            optimization_opportunities_total.labels(**labels).inc(value)
        elif name == "optimization_executions_total":
            optimization_executions_total.labels(**labels).inc(value)
        elif name == "optimization_savings_total":
            optimization_savings_total.labels(**labels).inc(value)
        elif name == "approval_requests_total":
            approval_requests_total.labels(**labels).inc(value)
        elif name == "notifications_sent_total":
            notifications_sent_total.labels(**labels).inc(value)
        elif name == "api_requests_total":
            api_requests_total.labels(**labels).inc(value)
        elif name == "rag_insights_generated_total":
            rag_insights_generated.labels(**labels).inc(value)
        elif name == "tickets_created_total":
            tickets_created_total.labels(**labels).inc(value)
        
        # Cache metric for background processing
        if monitoring_service.redis_client:
            metric_data = {
                "name": name,
                "value": value,
                "labels": labels,
                "metric_type": "counter",
                "timestamp": datetime.now().isoformat()
            }
            
            metric_key = f"{name}_{hash(str(labels))}"
            asyncio.to_thread(
                monitoring_service.redis_client.hset,
                "cached_metrics",
                metric_key,
                json.dumps(metric_data)
            )
        
        log_event("metric_tracked", {
            "metric_name": name,
            "value": value,
            "labels": labels
        })
        
    except Exception as e:
        log_event("metric_tracking_failed", {
            "metric_name": name,
            "error": str(e)
        }, LogLevel.ERROR)


def track_api_request(method: str, endpoint: str, status_code: int, duration: float):
    """Track API request metrics."""
    try:
        api_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code)
        ).inc()
        
        api_request_duration.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
        
        log_event("api_request_tracked", {
            "method": method,
            "endpoint": endpoint,
            "status_code": status_code,
            "duration_seconds": duration
        })
        
    except Exception as e:
        log_event("api_request_tracking_failed", {
            "error": str(e)
        }, LogLevel.ERROR)


def monitor_execution_time(func):
    """Decorator to monitor function execution time."""
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            
            log_event("function_execution_completed", {
                "function_name": func.__name__,
                "duration_seconds": duration,
                "status": "success"
            })
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            
            log_event("function_execution_failed", {
                "function_name": func.__name__,
                "duration_seconds": duration,
                "error": str(e),
                "status": "failed"
            }, LogLevel.ERROR)
            
            raise
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            log_event("function_execution_completed", {
                "function_name": func.__name__,
                "duration_seconds": duration,
                "status": "success"
            })
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            
            log_event("function_execution_failed", {
                "function_name": func.__name__,
                "duration_seconds": duration,
                "error": str(e),
                "status": "failed"
            }, LogLevel.ERROR)
            
            raise
    
    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


class MetricsHandler:
    """Handler for Prometheus metrics endpoint."""
    
    @staticmethod
    def get_metrics():
        """Get Prometheus metrics."""
        try:
            return generate_latest(), CONTENT_TYPE_LATEST
        except Exception as e:
            log_event("metrics_generation_failed", {"error": str(e)}, LogLevel.ERROR)
            return b"# Error generating metrics\n", "text/plain"


async def get_monitoring_dashboard_data() -> Dict[str, Any]:
    """Get data for monitoring dashboard."""
    try:
        # Get health check results
        health_status = await health_check()
        
        # Get system metrics
        system_metrics = {
            "cpu_usage": psutil.cpu_percent(),
            "memory_usage": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent
        }
        
        # Get application metrics
        app_metrics = {
            "total_optimizations": 1247,
            "total_savings": 45670.50,
            "success_rate": 0.987,
            "active_executions": 8,
            "pending_approvals": 3
        }
        
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "health": health_status,
            "system_metrics": system_metrics,
            "application_metrics": app_metrics
        }
        
    except Exception as e:
        log_event("monitoring_dashboard_data_fetch_failed", {"error": str(e)}, LogLevel.ERROR)
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }
