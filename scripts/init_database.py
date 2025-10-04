#!/usr/bin/env python3
"""
Database initialization script for Autonomous Cloud Cost Optimizer.

This script initializes the database with necessary tables, indexes,
and seed data for the cost optimization platform.
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add src to Python path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from src.models.optimization import Base, OptimizationOpportunity, OptimizationExecution
from src.core.config import settings


async def init_database():
    """Initialize the database with tables and seed data."""
    try:
        print("🚀 Initializing Autonomous Cloud Cost Optimizer Database...")
        
        # Create database engine
        engine = create_engine(
            settings.DATABASE_URL.replace("+asyncpg", ""),  # Use synchronous driver for init
            echo=True
        )
        
        # Create all tables
        print("📋 Creating database tables...")
        Base.metadata.create_all(bind=engine)
        
        # Create session
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        
        try:
            # Create indexes for performance
            print("🔍 Creating database indexes...")
            await create_indexes(session)
            
            # Insert seed data
            print("🌱 Inserting seed data...")
            await insert_seed_data(session)
            
            # Commit all changes
            session.commit()
            print("✅ Database initialization completed successfully!")
            
        except Exception as e:
            session.rollback()
            print(f"❌ Error during database initialization: {e}")
            raise
        finally:
            session.close()
            
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
        sys.exit(1)


async def create_indexes(session):
    """Create database indexes for optimal performance."""
    indexes = [
        # Optimization opportunities indexes
        "CREATE INDEX IF NOT EXISTS idx_opt_opp_cloud_provider ON optimization_opportunities(cloud_provider);",
        "CREATE INDEX IF NOT EXISTS idx_opt_opp_optimization_type ON optimization_opportunities(optimization_type);",
        "CREATE INDEX IF NOT EXISTS idx_opt_opp_status ON optimization_opportunities(status);",
        "CREATE INDEX IF NOT EXISTS idx_opt_opp_created_at ON optimization_opportunities(created_at);",
        "CREATE INDEX IF NOT EXISTS idx_opt_opp_potential_savings ON optimization_opportunities(potential_savings);",
        
        # Optimization executions indexes
        "CREATE INDEX IF NOT EXISTS idx_opt_exec_opportunity_id ON optimization_executions(opportunity_id);",
        "CREATE INDEX IF NOT EXISTS idx_opt_exec_status ON optimization_executions(status);",
        "CREATE INDEX IF NOT EXISTS idx_opt_exec_started_at ON optimization_executions(started_at);",
        "CREATE INDEX IF NOT EXISTS idx_opt_exec_executed_by ON optimization_executions(executed_by);",
        
        # Notifications indexes
        "CREATE INDEX IF NOT EXISTS idx_notifications_opportunity_id ON optimization_notifications(opportunity_id);",
        "CREATE INDEX IF NOT EXISTS idx_notifications_type ON optimization_notifications(notification_type);",
        "CREATE INDEX IF NOT EXISTS idx_notifications_sent_at ON optimization_notifications(sent_at);",
        
        # Cost analyses indexes
        "CREATE INDEX IF NOT EXISTS idx_cost_analyses_date ON cost_analyses(analysis_date);",
        "CREATE INDEX IF NOT EXISTS idx_cost_analyses_provider ON cost_analyses(cloud_provider);",
        
        # Resource metrics indexes
        "CREATE INDEX IF NOT EXISTS idx_resource_metrics_resource_id ON resource_metrics(resource_id);",
        "CREATE INDEX IF NOT EXISTS idx_resource_metrics_timestamp ON resource_metrics(timestamp);",
        "CREATE INDEX IF NOT EXISTS idx_resource_metrics_provider ON resource_metrics(cloud_provider);",
        
        # Approval workflows indexes
        "CREATE INDEX IF NOT EXISTS idx_approval_workflows_opportunity_id ON approval_workflows(opportunity_id);",
        "CREATE INDEX IF NOT EXISTS idx_approval_workflows_status ON approval_workflows(status);",
        "CREATE INDEX IF NOT EXISTS idx_approval_workflows_requested_at ON approval_workflows(requested_at);",
    ]
    
    for index_sql in indexes:
        try:
            session.execute(text(index_sql))
            print(f"  ✓ Created index: {index_sql.split('idx_')[1].split(' ')[0]}")
        except Exception as e:
            print(f"  ⚠️  Warning: Failed to create index: {e}")


async def insert_seed_data(session):
    """Insert seed data for testing and development."""
    
    # Sample optimization opportunities
    sample_opportunities = [
        {
            "service_name": "EC2 Instance - Web Server",
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
            "status": "discovered"
        },
        {
            "service_name": "Azure VM - Development Server",
            "resource_id": "vm-dev-server-001",
            "optimization_type": "scheduling",
            "cloud_provider": "azure",
            "region": "eastus",
            "current_cost": 120.00,
            "potential_savings": 60.00,
            "confidence_score": 0.95,
            "risk_level": "low",
            "description": "Schedule development server to run only during business hours",
            "implementation_steps": [
                "Create automation runbook for start/stop",
                "Configure schedule (8 AM - 6 PM weekdays)",
                "Test scheduling functionality",
                "Update monitoring alerts"
            ],
            "rollback_steps": [
                "Disable automation schedule",
                "Start server manually"
            ],
            "prerequisites": [
                "Server supports automated start/stop",
                "No critical processes during off-hours"
            ],
            "estimated_execution_time": 30,
            "status": "discovered"
        },
        {
            "service_name": "GCP Compute Engine - Analytics",
            "resource_id": "analytics-instance-001",
            "optimization_type": "storage_optimization",
            "cloud_provider": "gcp",
            "region": "us-central1",
            "current_cost": 45.75,
            "potential_savings": 13.73,
            "confidence_score": 0.88,
            "risk_level": "low",
            "description": "Migrate infrequently accessed data to cheaper storage class",
            "implementation_steps": [
                "Analyze data access patterns",
                "Configure lifecycle policies",
                "Migrate data to Nearline storage",
                "Monitor cost changes"
            ],
            "rollback_steps": [
                "Migrate data back to Standard storage",
                "Remove lifecycle policies"
            ],
            "prerequisites": [
                "Data access patterns are well understood",
                "Migration tools are available"
            ],
            "estimated_execution_time": 60,
            "status": "discovered"
        }
    ]
    
    print("  📊 Inserting sample optimization opportunities...")
    for opp_data in sample_opportunities:
        opportunity = OptimizationOpportunity(**opp_data)
        session.add(opportunity)
        print(f"    ✓ Added opportunity: {opp_data['service_name']}")
    
    # Sample cost analysis data
    print("  💰 Inserting sample cost analysis data...")
    cost_analysis_sql = """
    INSERT INTO cost_analyses (
        analysis_date, cloud_provider, region, total_monthly_cost,
        total_resources, cost_breakdown, total_optimization_potential,
        high_impact_opportunities, low_risk_opportunities,
        recommendations_count, estimated_monthly_savings
    ) VALUES (
        NOW() - INTERVAL '1 day', 'aws', 'us-east-1', 12500.50,
        45, '{"ec2": 8500.25, "rds": 2800.75, "s3": 1199.50}',
        2500.10, 8, 12, 15, 1800.75
    );
    """
    session.execute(text(cost_analysis_sql))
    print("    ✓ Added cost analysis data")
    
    # Sample resource metrics
    print("  📈 Inserting sample resource metrics...")
    metrics_sql = """
    INSERT INTO resource_metrics (
        resource_id, service_name, cloud_provider, region, timestamp,
        cpu_utilization, memory_utilization, network_io, storage_usage,
        hourly_cost, monthly_cost_projection, response_time, error_rate
    ) VALUES 
    ('i-1234567890abcdef0', 'ec2', 'aws', 'us-east-1', NOW(),
     0.45, 0.38, 150.5, 250.0, 0.12, 85.50, 120.5, 0.001),
    ('vm-dev-server-001', 'virtualmachines', 'azure', 'eastus', NOW(),
     0.25, 0.42, 89.3, 180.0, 0.16, 120.00, 95.2, 0.0005),
    ('analytics-instance-001', 'compute', 'gcp', 'us-central1', NOW(),
     0.62, 0.55, 210.8, 320.0, 0.06, 45.75, 88.1, 0.002);
    """
    session.execute(text(metrics_sql))
    print("    ✓ Added resource metrics data")
    
    # Sample approval workflows
    print("  ✅ Inserting sample approval workflows...")
    approval_sql = """
    INSERT INTO approval_workflows (
        opportunity_id, workflow_type, approver_id, approver_name,
        status, requested_at, escalation_level
    ) SELECT 
        id, 'slack', 'user123', 'John Doe', 'pending', NOW(), 0
    FROM optimization_opportunities 
    WHERE service_name = 'EC2 Instance - Web Server';
    """
    session.execute(text(approval_sql))
    print("    ✓ Added approval workflow data")


def main():
    """Main function to run database initialization."""
    print("🔧 Autonomous Cloud Cost Optimizer - Database Initialization")
    print("=" * 60)
    
    # Check if database URL is configured
    if not settings.DATABASE_URL:
        print("❌ Error: DATABASE_URL not configured")
        print("Please set the DATABASE_URL environment variable")
        sys.exit(1)
    
    # Run initialization
    asyncio.run(init_database())
    
    print("\n🎉 Database initialization completed!")
    print("\nNext steps:")
    print("1. Configure your cloud provider credentials")
    print("2. Set up Slack/Teams integration")
    print("3. Configure notification services")
    print("4. Start the application: uvicorn src.main:app --reload")
    print("\n📚 Documentation: docs.autonomous-cost-optimizer.com")
    print("🆘 Support: support@autonomous-cost-optimizer.com")


if __name__ == "__main__":
    main()
