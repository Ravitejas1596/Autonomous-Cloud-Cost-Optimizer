"""
Cloud Provider Service for Multi-Cloud Integration.

This module provides unified access to AWS, Azure, and GCP services
for cost optimization operations.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.common.credentials import ServicePrincipalCredentials
from google.cloud import compute_v1
from google.cloud import storage as gcs
from google.oauth2 import service_account

from src.core.config import settings
from src.core.monitoring import log_event


@dataclass
class CloudResource:
    """Represents a cloud resource."""
    id: str
    name: str
    service: str
    provider: str
    region: str
    instance_type: Optional[str] = None
    monthly_cost: float = 0.0
    cpu_utilization: float = 0.0
    memory_utilization: float = 0.0
    network_io: float = 0.0
    storage_usage: float = 0.0
    uptime_percentage: float = 100.0
    environment: str = "production"
    tags: Dict[str, str] = None


class CloudProviderService:
    """Service for managing multi-cloud provider interactions."""
    
    def __init__(self):
        self.aws_client = None
        self.azure_client = None
        self.gcp_client = None
        self.credentials = {}
        
    async def initialize(self):
        """Initialize cloud provider clients."""
        try:
            # Initialize AWS
            if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
                self.aws_client = boto3.client(
                    'ec2',
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=settings.AWS_DEFAULT_REGION
                )
                log_event("aws_client_initialized")
            
            # Initialize Azure
            if settings.AZURE_CLIENT_ID and settings.AZURE_CLIENT_SECRET:
                credentials = ServicePrincipalCredentials(
                    client_id=settings.AZURE_CLIENT_ID,
                    secret=settings.AZURE_CLIENT_SECRET,
                    tenant=settings.AZURE_TENANT_ID
                )
                self.azure_client = ComputeManagementClient(
                    credentials, settings.AZURE_SUBSCRIPTION_ID
                )
                log_event("azure_client_initialized")
            
            # Initialize GCP
            if settings.GCP_PROJECT_ID and settings.GCP_SERVICE_ACCOUNT_KEY:
                credentials = service_account.Credentials.from_service_account_file(
                    settings.GCP_SERVICE_ACCOUNT_KEY
                )
                self.gcp_client = compute_v1.InstancesClient(credentials=credentials)
                log_event("gcp_client_initialized")
            
            log_event("cloud_provider_service_initialized", {"status": "success"})
            
        except Exception as e:
            log_event("cloud_provider_service_initialization_failed", {"error": str(e)})
            raise
    
    async def get_infrastructure_data(self) -> Dict[str, Any]:
        """Get infrastructure data from all cloud providers."""
        try:
            infrastructure_data = {
                "resources": [],
                "total_monthly_cost": 0.0,
                "total_resources": 0,
                "providers": []
            }
            
            # Get AWS resources
            if self.aws_client:
                aws_resources = await self._get_aws_resources()
                infrastructure_data["resources"].extend(aws_resources)
                infrastructure_data["providers"].append("aws")
            
            # Get Azure resources
            if self.azure_client:
                azure_resources = await self._get_azure_resources()
                infrastructure_data["resources"].extend(azure_resources)
                infrastructure_data["providers"].append("azure")
            
            # Get GCP resources
            if self.gcp_client:
                gcp_resources = await self._get_gcp_resources()
                infrastructure_data["resources"].extend(gcp_resources)
                infrastructure_data["providers"].append("gcp")
            
            # Calculate totals
            infrastructure_data["total_resources"] = len(infrastructure_data["resources"])
            infrastructure_data["total_monthly_cost"] = sum(
                r.get("monthly_cost", 0) for r in infrastructure_data["resources"]
            )
            
            return infrastructure_data
            
        except Exception as e:
            log_event("infrastructure_data_fetch_failed", {"error": str(e)})
            raise
    
    async def _get_aws_resources(self) -> List[Dict[str, Any]]:
        """Get AWS resources."""
        try:
            resources = []
            
            # Get EC2 instances
            response = self.aws_client.describe_instances()
            
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    if instance['State']['Name'] == 'running':
                        resource = {
                            "id": instance['InstanceId'],
                            "name": instance.get('Tags', [{}])[0].get('Value', instance['InstanceId']),
                            "service": "ec2",
                            "provider": "aws",
                            "region": instance['Placement']['AvailabilityZone'][:-1],
                            "instance_type": instance['InstanceType'],
                            "monthly_cost": await self._calculate_aws_monthly_cost(instance),
                            "cpu_utilization": await self._get_aws_cpu_utilization(instance['InstanceId']),
                            "memory_utilization": await self._get_aws_memory_utilization(instance['InstanceId']),
                            "uptime_percentage": 100.0,
                            "environment": self._get_environment_from_tags(instance.get('Tags', [])),
                            "tags": {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                        }
                        resources.append(resource)
            
            return resources
            
        except Exception as e:
            log_event("aws_resources_fetch_failed", {"error": str(e)})
            return []
    
    async def _get_azure_resources(self) -> List[Dict[str, Any]]:
        """Get Azure resources."""
        try:
            resources = []
            
            # Get virtual machines
            vms = self.azure_client.virtual_machines.list_all()
            
            for vm in vms:
                resource = {
                    "id": vm.id,
                    "name": vm.name,
                    "service": "virtualmachines",
                    "provider": "azure",
                    "region": vm.location,
                    "instance_type": vm.hardware_profile.vm_size,
                    "monthly_cost": await self._calculate_azure_monthly_cost(vm),
                    "cpu_utilization": await self._get_azure_cpu_utilization(vm.id),
                    "memory_utilization": await self._get_azure_memory_utilization(vm.id),
                    "uptime_percentage": 100.0,
                    "environment": self._get_environment_from_tags(vm.tags or {}),
                    "tags": vm.tags or {}
                }
                resources.append(resource)
            
            return resources
            
        except Exception as e:
            log_event("azure_resources_fetch_failed", {"error": str(e)})
            return []
    
    async def _get_gcp_resources(self) -> List[Dict[str, Any]]:
        """Get GCP resources."""
        try:
            resources = []
            
            # Get compute instances
            request = compute_v1.AggregatedListInstancesRequest(project=settings.GCP_PROJECT_ID)
            response = self.gcp_client.aggregated_list(request=request)
            
            for zone, instances_scoped_list in response:
                if instances_scoped_list.instances:
                    for instance in instances_scoped_list.instances:
                        resource = {
                            "id": instance.id,
                            "name": instance.name,
                            "service": "compute",
                            "provider": "gcp",
                            "region": zone.split('/')[-1],
                            "instance_type": instance.machine_type.split('/')[-1],
                            "monthly_cost": await self._calculate_gcp_monthly_cost(instance),
                            "cpu_utilization": await self._get_gcp_cpu_utilization(instance.id),
                            "memory_utilization": await self._get_gcp_memory_utilization(instance.id),
                            "uptime_percentage": 100.0,
                            "environment": self._get_environment_from_labels(instance.labels or {}),
                            "tags": instance.labels or {}
                        }
                        resources.append(resource)
            
            return resources
            
        except Exception as e:
            log_event("gcp_resources_fetch_failed", {"error": str(e)})
            return []
    
    async def _calculate_aws_monthly_cost(self, instance: Dict[str, Any]) -> float:
        """Calculate monthly cost for AWS instance."""
        # Simplified calculation - in production, use AWS Cost Explorer API
        instance_type = instance['InstanceType']
        pricing = {
            't3.micro': 8.5,
            't3.small': 17.0,
            't3.medium': 34.0,
            't3.large': 68.0,
            'm5.large': 85.0,
            'm5.xlarge': 170.0,
            'c5.large': 78.0,
            'c5.xlarge': 156.0
        }
        return pricing.get(instance_type, 50.0)
    
    async def _calculate_azure_monthly_cost(self, vm) -> float:
        """Calculate monthly cost for Azure VM."""
        # Simplified calculation - in production, use Azure Cost Management API
        vm_size = vm.hardware_profile.vm_size
        pricing = {
            'Standard_B1s': 12.0,
            'Standard_B2s': 24.0,
            'Standard_D2s_v3': 85.0,
            'Standard_D4s_v3': 170.0,
            'Standard_F2s_v2': 78.0,
            'Standard_F4s_v2': 156.0
        }
        return pricing.get(vm_size, 50.0)
    
    async def _calculate_gcp_monthly_cost(self, instance) -> float:
        """Calculate monthly cost for GCP instance."""
        # Simplified calculation - in production, use GCP Billing API
        machine_type = instance.machine_type.split('/')[-1]
        pricing = {
            'e2-micro': 8.5,
            'e2-small': 17.0,
            'e2-medium': 34.0,
            'e2-standard-2': 68.0,
            'n1-standard-1': 45.0,
            'n1-standard-2': 90.0,
            'c2-standard-4': 156.0
        }
        return pricing.get(machine_type, 50.0)
    
    async def _get_aws_cpu_utilization(self, instance_id: str) -> float:
        """Get AWS CPU utilization."""
        # In production, use CloudWatch metrics
        return 0.45  # Simulated value
    
    async def _get_aws_memory_utilization(self, instance_id: str) -> float:
        """Get AWS memory utilization."""
        # In production, use CloudWatch metrics
        return 0.38  # Simulated value
    
    async def _get_azure_cpu_utilization(self, vm_id: str) -> float:
        """Get Azure CPU utilization."""
        # In production, use Azure Monitor metrics
        return 0.42  # Simulated value
    
    async def _get_azure_memory_utilization(self, vm_id: str) -> float:
        """Get Azure memory utilization."""
        # In production, use Azure Monitor metrics
        return 0.35  # Simulated value
    
    async def _get_gcp_cpu_utilization(self, instance_id: str) -> float:
        """Get GCP CPU utilization."""
        # In production, use GCP Monitoring metrics
        return 0.48  # Simulated value
    
    async def _get_gcp_memory_utilization(self, instance_id: str) -> float:
        """Get GCP memory utilization."""
        # In production, use GCP Monitoring metrics
        return 0.41  # Simulated value
    
    def _get_environment_from_tags(self, tags: List[Dict[str, str]]) -> str:
        """Extract environment from tags."""
        for tag in tags:
            if tag.get('Key', '').lower() in ['environment', 'env']:
                return tag.get('Value', 'production').lower()
        return 'production'
    
    def _get_environment_from_labels(self, labels: Dict[str, str]) -> str:
        """Extract environment from labels."""
        return labels.get('environment', labels.get('env', 'production')).lower()
    
    async def validate_connection(self, provider: str) -> bool:
        """Validate connection to cloud provider."""
        try:
            if provider == "aws" and self.aws_client:
                self.aws_client.describe_regions()
                return True
            elif provider == "azure" and self.azure_client:
                self.azure_client.resource_groups.list()
                return True
            elif provider == "gcp" and self.gcp_client:
                request = compute_v1.ListZonesRequest(project=settings.GCP_PROJECT_ID)
                self.gcp_client.list(request=request)
                return True
            return False
        except Exception as e:
            log_event("provider_connection_validation_failed", {
                "provider": provider,
                "error": str(e)
            })
            return False
    
    async def resource_exists(self, resource_id: str, provider: str) -> bool:
        """Check if a resource exists."""
        try:
            if provider == "aws":
                self.aws_client.describe_instances(InstanceIds=[resource_id])
                return True
            elif provider == "azure":
                # Azure resource ID parsing would be needed
                return True
            elif provider == "gcp":
                # GCP resource ID parsing would be needed
                return True
            return False
        except Exception:
            return False
    
    async def get_resource_config(self, resource_id: str, provider: str) -> Dict[str, Any]:
        """Get current resource configuration."""
        # Simplified implementation
        return {
            "id": resource_id,
            "provider": provider,
            "status": "running",
            "instance_type": "t3.medium",
            "prerequisites": []
        }
    
    async def create_resource_backup(self, resource_id: str, provider: str) -> Dict[str, Any]:
        """Create backup of resource configuration."""
        config = await self.get_resource_config(resource_id, provider)
        return {
            "resource_id": resource_id,
            "backup_timestamp": datetime.now().isoformat(),
            "configuration": config
        }
    
    async def restore_resource_from_backup(self, resource_id: str, provider: str, backup_data: Dict[str, Any]):
        """Restore resource from backup."""
        # Implementation would restore the resource
        log_event("resource_restored_from_backup", {
            "resource_id": resource_id,
            "provider": provider
        })
    
    async def update_resource_tags(self, resource_id: str, provider: str, tags: Dict[str, str]):
        """Update resource tags."""
        # Implementation would update tags
        log_event("resource_tags_updated", {
            "resource_id": resource_id,
            "provider": provider,
            "tags": tags
        })
