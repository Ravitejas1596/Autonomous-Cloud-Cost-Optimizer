#!/usr/bin/env python3
"""
Seed data script for Autonomous Cloud Cost Optimizer.

This script populates the database with realistic test data
for development and demonstration purposes.
"""

import asyncio
import sys
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

# Add src to Python path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from src.models.optimization import (
    Base, OptimizationOpportunity, OptimizationExecution, 
    OptimizationNotification, CostAnalysis, ResourceMetrics, ApprovalWorkflow
)
from src.core.config import settings


async def seed_data():
    """Populate database with realistic seed data."""
    try:
        print("🌱 Seeding Autonomous Cloud Cost Optimizer Database...")
        
        # Create database engine
        engine = create_engine(
            settings.DATABASE_URL.replace("+asyncpg", ""),
            echo=False
        )
        
        # Create session
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        
        try:
            # Generate and insert seed data
            await generate_optimization_opportunities(session)
            await generate_execution_history(session)
            await generate_cost_analyses(session)
            await generate_resource_metrics(session)
            await generate_notifications(session)
            await generate_approval_workflows(session)
            
            # Commit all changes
            session.commit()
            print("✅ Database seeding completed successfully!")
            
        except Exception as e:
            session.rollback()
            print(f"❌ Error during database seeding: {e}")
            raise
        finally:
            session.close()
            
    except Exception as e:
        print(f"❌ Failed to seed database: {e}")
        sys.exit(1)


async def generate_optimization_opportunities(session):
    """Generate realistic optimization opportunities."""
    print("  💡 Generating optimization opportunities...")
    
    services = [
        ("EC2 Instance - Web Server", "i-web-001", "aws"),
        ("EC2 Instance - API Server", "i-api-002", "aws"),
        ("EC2 Instance - Database", "i-db-003", "aws"),
        ("Azure VM - Development", "vm-dev-001", "azure"),
        ("Azure VM - Staging", "vm-staging-002", "azure"),
        ("GCP Compute - Analytics", "analytics-001", "gcp"),
        ("GCP Compute - ML Training", "ml-train-002", "gcp"),
        ("RDS Instance - PostgreSQL", "rds-pg-001", "aws"),
        ("Azure SQL Database", "sql-azure-001", "azure"),
        ("GCP Cloud SQL", "sql-gcp-001", "gcp"),
        ("S3 Bucket - Logs", "s3-logs-001", "aws"),
        ("Azure Storage - Backups", "storage-backup-001", "azure"),
        ("GCP Storage - Archives", "storage-archive-001", "gcp"),
    ]
    
    optimization_types = [
        ("rightsizing", "Adjust instance sizes based on utilization"),
        ("scheduling", "Schedule non-production resources"),
        ("storage_optimization", "Optimize storage classes and policies"),
        ("unused_resources", "Remove unused or idle resources"),
        ("reserved_instances", "Purchase reserved instances"),
        ("spot_instances", "Use spot instances for fault-tolerant workloads")
    ]
    
    regions = {
        "aws": ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"],
        "azure": ["eastus", "westus2", "westeurope", "southeastasia"],
        "gcp": ["us-central1", "us-east1", "europe-west1", "asia-southeast1"]
    }
    
    opportunities = []
    
    for service_name, resource_id, provider in services:
        opt_type, description = random.choice(optimization_types)
        region = random.choice(regions[provider])
        
        # Generate realistic costs and savings
        base_cost = random.uniform(50, 500)
        savings_percentage = random.uniform(0.15, 0.45)
        potential_savings = base_cost * savings_percentage
        confidence_score = random.uniform(0.75, 0.98)
        
        # Generate implementation steps based on optimization type
        if opt_type == "rightsizing":
            implementation_steps = [
                "Create snapshot of current instance",
                "Stop the instance",
                f"Change instance type to recommended size",
                "Start the instance",
                "Verify application functionality"
            ]
            rollback_steps = [
                "Stop the instance",
                "Change back to original instance type",
                "Start the instance"
            ]
            prerequisites = [
                "Application can handle brief downtime",
                "Backup/snapshot capability available"
            ]
            exec_time = random.randint(10, 25)
            
        elif opt_type == "scheduling":
            implementation_steps = [
                "Create automation runbook for start/stop",
                "Configure schedule (8 AM - 6 PM weekdays)",
                "Test scheduling functionality",
                "Update monitoring alerts"
            ]
            rollback_steps = [
                "Disable automation schedule",
                "Start server manually"
            ]
            prerequisites = [
                "Server supports automated start/stop",
                "No critical processes during off-hours"
            ]
            exec_time = random.randint(20, 40)
            
        elif opt_type == "storage_optimization":
            implementation_steps = [
                "Analyze data access patterns",
                "Configure lifecycle policies",
                "Migrate data to optimal storage class",
                "Monitor cost changes"
            ]
            rollback_steps = [
                "Migrate data back to original storage class",
                "Remove lifecycle policies"
            ]
            prerequisites = [
                "Data access patterns are well understood",
                "Migration tools are available"
            ]
            exec_time = random.randint(45, 90)
            
        else:  # unused_resources, reserved_instances, spot_instances
            implementation_steps = [
                "Verify resource is truly unused",
                "Create backup if needed",
                "Remove the resource",
                "Update documentation"
            ]
            rollback_steps = [
                "Restore from backup",
                "Recreate resource configuration"
            ]
            prerequisites = [
                "Resource has been unused for 30+ days",
                "No dependencies from other resources"
            ]
            exec_time = random.randint(5, 15)
        
        opportunity = OptimizationOpportunity(
            service_name=service_name,
            resource_id=resource_id,
            optimization_type=opt_type,
            cloud_provider=provider,
            region=region,
            current_cost=base_cost,
            potential_savings=potential_savings,
            confidence_score=confidence_score,
            risk_level=random.choice(["low", "medium", "high"]),
            description=description,
            implementation_steps=implementation_steps,
            rollback_steps=rollback_steps,
            prerequisites=prerequisites,
            estimated_execution_time=exec_time,
            status=random.choice(["discovered", "pending_approval", "approved", "completed"]),
            created_at=datetime.now() - timedelta(days=random.randint(1, 30))
        )
        
        opportunities.append(opportunity)
        session.add(opportunity)
    
    print(f"    ✓ Generated {len(opportunities)} optimization opportunities")


async def generate_execution_history(session):
    """Generate execution history for some opportunities."""
    print("  ⚡ Generating execution history...")
    
    # Get some opportunities that were completed
    opportunities = session.query(OptimizationOpportunity).filter(
        OptimizationOpportunity.status == "completed"
    ).limit(5).all()
    
    executions = []
    
    for opportunity in opportunities:
        start_time = opportunity.created_at + timedelta(hours=random.randint(1, 24))
        execution_time = timedelta(minutes=opportunity.estimated_execution_time + random.randint(-5, 10))
        end_time = start_time + execution_time
        
        execution = OptimizationExecution(
            opportunity_id=opportunity.id,
            status="completed",
            started_at=start_time,
            completed_at=end_time,
            actual_savings=opportunity.potential_savings * random.uniform(0.9, 1.1),
            execution_log=[
                {"step": "preparation", "status": "completed", "duration": 2},
                {"step": "validation", "status": "completed", "duration": 3},
                {"step": "backup", "status": "completed", "duration": 5},
                {"step": "execution", "status": "completed", "duration": opportunity.estimated_execution_time},
                {"step": "verification", "status": "completed", "duration": 3}
            ],
            executed_by=f"user{random.randint(100, 999)}"
        )
        
        executions.append(execution)
        session.add(execution)
    
    print(f"    ✓ Generated {len(executions)} execution records")


async def generate_cost_analyses(session):
    """Generate historical cost analysis data."""
    print("  💰 Generating cost analyses...")
    
    providers = ["aws", "azure", "gcp"]
    regions = {
        "aws": ["us-east-1", "us-west-2", "eu-west-1"],
        "azure": ["eastus", "westus2", "westeurope"],
        "gcp": ["us-central1", "us-east1", "europe-west1"]
    }
    
    analyses = []
    
    # Generate analyses for the last 30 days
    for day in range(30):
        analysis_date = datetime.now() - timedelta(days=day)
        
        for provider in providers:
            for region in regions[provider]:
                total_cost = random.uniform(5000, 50000)
                total_resources = random.randint(20, 100)
                
                cost_breakdown = {
                    "compute": total_cost * random.uniform(0.6, 0.8),
                    "storage": total_cost * random.uniform(0.1, 0.2),
                    "network": total_cost * random.uniform(0.05, 0.15),
                    "other": total_cost * random.uniform(0.05, 0.1)
                }
                
                optimization_potential = total_cost * random.uniform(0.15, 0.35)
                high_impact = random.randint(3, 12)
                low_risk = random.randint(8, 20)
                recommendations = high_impact + low_risk + random.randint(0, 10)
                estimated_savings = optimization_potential * random.uniform(0.7, 0.9)
                
                analysis = CostAnalysis(
                    analysis_date=analysis_date,
                    cloud_provider=provider,
                    region=region,
                    total_monthly_cost=total_cost,
                    total_resources=total_resources,
                    cost_breakdown=cost_breakdown,
                    total_optimization_potential=optimization_potential,
                    high_impact_opportunities=high_impact,
                    low_risk_opportunities=low_risk,
                    recommendations_count=recommendations,
                    estimated_monthly_savings=estimated_savings
                )
                
                analyses.append(analysis)
                session.add(analysis)
    
    print(f"    ✓ Generated {len(analyses)} cost analyses")


async def generate_resource_metrics(session):
    """Generate resource utilization metrics."""
    print("  📊 Generating resource metrics...")
    
    # Get resource IDs from opportunities
    opportunities = session.query(OptimizationOpportunity).all()
    
    metrics = []
    
    # Generate metrics for the last 7 days, every 4 hours
    for day in range(7):
        for hour in range(0, 24, 4):
            timestamp = datetime.now() - timedelta(days=day, hours=hour)
            
            for opportunity in opportunities[:10]:  # Limit to first 10 resources
                metric = ResourceMetrics(
                    resource_id=opportunity.resource_id,
                    service_name=opportunity.service_name,
                    cloud_provider=opportunity.cloud_provider,
                    region=opportunity.region,
                    timestamp=timestamp,
                    cpu_utilization=random.uniform(0.1, 0.9),
                    memory_utilization=random.uniform(0.1, 0.8),
                    network_io=random.uniform(10, 1000),
                    storage_usage=random.uniform(50, 500),
                    hourly_cost=opportunity.current_cost / (24 * 30),
                    monthly_cost_projection=opportunity.current_cost,
                    response_time=random.uniform(50, 300),
                    error_rate=random.uniform(0.0001, 0.01)
                )
                
                metrics.append(metric)
                session.add(metric)
    
    print(f"    ✓ Generated {len(metrics)} resource metrics")


async def generate_notifications(session):
    """Generate notification history."""
    print("  📧 Generating notifications...")
    
    opportunities = session.query(OptimizationOpportunity).limit(10).all()
    
    notifications = []
    notification_types = ["optimization_discovered", "optimization_executed", "optimization_failed"]
    channels = ["email", "slack", "teams", "sms", "push"]
    
    for opportunity in opportunities:
        for _ in range(random.randint(1, 3)):
            notification = OptimizationNotification(
                opportunity_id=opportunity.id,
                notification_type=random.choice(channels),
                recipient=f"user{random.randint(100, 999)}@company.com",
                subject=f"Notification for {opportunity.service_name}",
                message=f"Cost optimization notification for {opportunity.service_name}",
                delivery_status=random.choice(["sent", "delivered", "failed"]),
                sent_at=datetime.now() - timedelta(hours=random.randint(1, 48))
            )
            
            notifications.append(notification)
            session.add(notification)
    
    print(f"    ✓ Generated {len(notifications)} notifications")


async def generate_approval_workflows(session):
    """Generate approval workflow history."""
    print("  ✅ Generating approval workflows...")
    
    opportunities = session.query(OptimizationOpportunity).filter(
        OptimizationOpportunity.status.in_(["pending_approval", "approved", "rejected"])
    ).limit(8).all()
    
    workflows = []
    workflow_types = ["slack", "teams", "email"]
    statuses = ["pending", "approved", "rejected", "expired"]
    
    for opportunity in opportunities:
        workflow = ApprovalWorkflow(
            opportunity_id=opportunity.id,
            workflow_type=random.choice(workflow_types),
            approver_id=f"user{random.randint(100, 999)}",
            approver_name=f"User {random.randint(100, 999)}",
            status=random.choice(statuses),
            requested_at=opportunity.created_at + timedelta(minutes=random.randint(5, 60)),
            responded_at=datetime.now() - timedelta(hours=random.randint(1, 24)) if random.choice([True, False]) else None,
            response_message=random.choice([
                "Approved - looks good to proceed",
                "Rejected - too risky for production",
                "Approved with conditions",
                "Need more information before approval"
            ]) if random.choice([True, False]) else None,
            escalation_level=random.randint(0, 2)
        )
        
        workflows.append(workflow)
        session.add(workflow)
    
    print(f"    ✓ Generated {len(workflows)} approval workflows")


def main():
    """Main function to run data seeding."""
    print("🌱 Autonomous Cloud Cost Optimizer - Data Seeding")
    print("=" * 50)
    
    # Check if database URL is configured
    if not settings.DATABASE_URL:
        print("❌ Error: DATABASE_URL not configured")
        print("Please set the DATABASE_URL environment variable")
        sys.exit(1)
    
    # Run seeding
    asyncio.run(seed_data())
    
    print("\n🎉 Database seeding completed!")
    print("\nThe database now contains:")
    print("  • Realistic optimization opportunities")
    print("  • Historical execution data")
    print("  • Cost analysis reports")
    print("  • Resource utilization metrics")
    print("  • Notification history")
    print("  • Approval workflow records")
    print("\n🚀 You can now start the application and explore the data!")


if __name__ == "__main__":
    main()
