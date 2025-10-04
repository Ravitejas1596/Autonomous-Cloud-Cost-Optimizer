"""
RAG (Retrieval-Augmented Generation) System for Cost Optimization Insights.

This module implements a sophisticated RAG system that continuously learns from
external sources of cost optimization knowledge and provides contextual insights
for optimization recommendations.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import hashlib
import aiohttp
import asyncio

import chromadb
from chromadb.config import Settings
import openai
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.document_loaders import WebBaseLoader
from sentence_transformers import SentenceTransformer
import feedparser
import requests
from bs4 import BeautifulSoup

from src.core.config import settings
from src.core.monitoring import track_metric, log_event


@dataclass
class KnowledgeSource:
    """Represents a source of cost optimization knowledge."""
    id: str
    name: str
    url: str
    source_type: str  # blog, documentation, paper, news
    last_updated: datetime
    content_hash: str
    priority: int  # 1-10, higher is more important


@dataclass
class OptimizationInsight:
    """Represents an insight extracted from external knowledge."""
    id: str
    title: str
    content: str
    source: str
    confidence_score: float
    tags: List[str]
    applicable_services: List[str]
    potential_savings_percentage: float
    implementation_difficulty: str  # easy, medium, hard
    risk_level: str  # low, medium, high
    created_at: datetime


class RAGSystem:
    """RAG system for continuous learning from external cost optimization sources."""
    
    def __init__(self):
        self.chroma_client = None
        self.vector_store = None
        self.embeddings = None
        self.text_splitter = None
        self.knowledge_sources = []
        self.insights_cache = {}
        
    async def initialize(self):
        """Initialize the RAG system."""
        try:
            # Initialize ChromaDB
            self.chroma_client = chromadb.PersistentClient(
                path=settings.CHROMA_DB_PATH,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Initialize embeddings
            self.embeddings = OpenAIEmbeddings(
                openai_api_key=settings.OPENAI_API_KEY,
                model=settings.VECTOR_EMBEDDING_MODEL
            )
            
            # Initialize text splitter
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
                separators=["\n\n", "\n", " ", ""]
            )
            
            # Initialize vector store
            self.vector_store = Chroma(
                client=self.chroma_client,
                embedding_function=self.embeddings,
                collection_name="cost_optimization_knowledge"
            )
            
            # Load knowledge sources
            await self._load_knowledge_sources()
            
            # Perform initial knowledge base update if needed
            await self._check_and_update_knowledge_base()
            
            log_event("rag_system_initialized", {"status": "success"})
            
        except Exception as e:
            log_event("rag_system_initialization_failed", {"error": str(e)})
            raise
    
    async def _load_knowledge_sources(self):
        """Load predefined knowledge sources for cost optimization."""
        self.knowledge_sources = [
            KnowledgeSource(
                id="aws_cost_optimization_best_practices",
                name="AWS Cost Optimization Best Practices",
                url="https://aws.amazon.com/well-architected-tool/",
                source_type="documentation",
                last_updated=datetime.now(),
                content_hash="",
                priority=10
            ),
            KnowledgeSource(
                id="azure_cost_management",
                name="Azure Cost Management Documentation",
                url="https://docs.microsoft.com/en-us/azure/cost-management-billing/",
                source_type="documentation",
                last_updated=datetime.now(),
                content_hash="",
                priority=9
            ),
            KnowledgeSource(
                id="gcp_cost_optimization",
                name="Google Cloud Cost Optimization Guide",
                url="https://cloud.google.com/cost-optimization",
                source_type="documentation",
                last_updated=datetime.now(),
                content_hash="",
                priority=9
            ),
            KnowledgeSource(
                id="aws_blog_cost_optimization",
                name="AWS Blog - Cost Optimization",
                url="https://aws.amazon.com/blogs/aws/category/cloud-financial-management/",
                source_type="blog",
                last_updated=datetime.now(),
                content_hash="",
                priority=8
            ),
            KnowledgeSource(
                id="azure_blog_cost_optimization",
                name="Azure Blog - Cost Management",
                url="https://azure.microsoft.com/en-us/blog/tag/cost-management/",
                source_type="blog",
                last_updated=datetime.now(),
                content_hash="",
                priority=8
            ),
            KnowledgeSource(
                id="finops_foundation",
                name="FinOps Foundation Resources",
                url="https://www.finops.org/resources/",
                source_type="documentation",
                last_updated=datetime.now(),
                content_hash="",
                priority=7
            ),
            KnowledgeSource(
                id="cloud_cost_optimization_papers",
                name="Academic Papers on Cloud Cost Optimization",
                url="https://scholar.google.com/scholar?q=cloud+cost+optimization",
                source_type="papers",
                last_updated=datetime.now(),
                content_hash="",
                priority=6
            ),
            KnowledgeSource(
                id="kubecost_blog",
                name="Kubecost Blog - Kubernetes Cost Optimization",
                url="https://blog.kubecost.com/",
                source_type="blog",
                last_updated=datetime.now(),
                content_hash="",
                priority=7
            ),
            KnowledgeSource(
                id="cloudability_resources",
                name="Cloudability Cost Optimization Resources",
                url="https://www.cloudability.com/resources/",
                source_type="blog",
                last_updated=datetime.now(),
                content_hash="",
                priority=6
            ),
            KnowledgeSource(
                id="spot_instances_guide",
                name="Spot Instances Optimization Guide",
                url="https://aws.amazon.com/ec2/spot/",
                source_type="documentation",
                last_updated=datetime.now(),
                content_hash="",
                priority=8
            )
        ]
        
        log_event("knowledge_sources_loaded", {
            "count": len(self.knowledge_sources),
            "sources": [s.name for s in self.knowledge_sources]
        })
    
    async def _check_and_update_knowledge_base(self):
        """Check if knowledge base needs updating and update if necessary."""
        try:
            last_update = await self._get_last_knowledge_update()
            now = datetime.now()
            
            if (now - last_update).total_seconds() > settings.KNOWLEDGE_BASE_UPDATE_INTERVAL_HOURS * 3600:
                await self._update_knowledge_base()
                await self._set_last_knowledge_update(now)
                
        except Exception as e:
            log_event("knowledge_base_update_check_failed", {"error": str(e)})
    
    async def _get_last_knowledge_update(self) -> datetime:
        """Get the timestamp of the last knowledge base update."""
        # In a real implementation, this would come from a database
        return datetime.now() - timedelta(hours=25)  # Simulate old update
    
    async def _set_last_knowledge_update(self, timestamp: datetime):
        """Set the timestamp of the last knowledge base update."""
        # In a real implementation, this would be saved to a database
        pass
    
    async def _update_knowledge_base(self):
        """Update the knowledge base with fresh content from sources."""
        try:
            log_event("knowledge_base_update_started")
            
            new_content_count = 0
            
            for source in self.knowledge_sources:
                try:
                    content = await self._fetch_content_from_source(source)
                    if content:
                        # Calculate content hash to check for changes
                        content_hash = hashlib.md5(content.encode()).hexdigest()
                        
                        if content_hash != source.content_hash:
                            # Content has changed, process and store it
                            await self._process_and_store_content(source, content)
                            source.content_hash = content_hash
                            source.last_updated = datetime.now()
                            new_content_count += 1
                            
                except Exception as e:
                    log_event("source_update_failed", {
                        "source": source.name,
                        "error": str(e)
                    })
            
            log_event("knowledge_base_update_completed", {
                "new_content_sources": new_content_count
            })
            
        except Exception as e:
            log_event("knowledge_base_update_failed", {"error": str(e)})
            raise
    
    async def _fetch_content_from_source(self, source: KnowledgeSource) -> Optional[str]:
        """Fetch content from a knowledge source."""
        try:
            if source.source_type == "blog":
                return await self._fetch_blog_content(source.url)
            elif source.source_type == "documentation":
                return await self._fetch_documentation_content(source.url)
            elif source.source_type == "papers":
                return await self._fetch_academic_papers(source.url)
            else:
                return await self._fetch_generic_content(source.url)
                
        except Exception as e:
            log_event("content_fetch_failed", {
                "source": source.name,
                "error": str(e)
            })
            return None
    
    async def _fetch_blog_content(self, url: str) -> Optional[str]:
        """Fetch content from a blog RSS feed."""
        try:
            # Parse RSS feed
            feed = feedparser.parse(url)
            content_pieces = []
            
            for entry in feed.entries[:10]:  # Limit to 10 recent posts
                if 'summary' in entry:
                    content_pieces.append(entry.summary)
                if 'content' in entry:
                    for content_item in entry.content:
                        content_pieces.append(content_item.value)
            
            return "\n\n".join(content_pieces)
            
        except Exception as e:
            log_event("blog_content_fetch_failed", {"url": url, "error": str(e)})
            return None
    
    async def _fetch_documentation_content(self, url: str) -> Optional[str]:
        """Fetch content from documentation pages."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Extract main content
                        content_elements = soup.find_all(['p', 'h1', 'h2', 'h3', 'li'])
                        content_text = []
                        
                        for element in content_elements:
                            text = element.get_text().strip()
                            if text and len(text) > 20:  # Filter out short text
                                content_text.append(text)
                        
                        return "\n".join(content_text)
            
        except Exception as e:
            log_event("documentation_content_fetch_failed", {"url": url, "error": str(e)})
            return None
    
    async def _fetch_academic_papers(self, url: str) -> Optional[str]:
        """Fetch content from academic paper sources."""
        # This is a simplified implementation
        # In production, you'd integrate with academic APIs like arXiv, Google Scholar, etc.
        return "Academic papers content would be fetched here in production implementation."
    
    async def _fetch_generic_content(self, url: str) -> Optional[str]:
        """Fetch generic web content."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Remove script and style elements
                        for script in soup(["script", "style"]):
                            script.decompose()
                        
                        text = soup.get_text()
                        lines = (line.strip() for line in text.splitlines())
                        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                        text = '\n'.join(chunk for chunk in chunks if chunk)
                        
                        return text[:50000]  # Limit content size
            
        except Exception as e:
            log_event("generic_content_fetch_failed", {"url": url, "error": str(e)})
            return None
    
    async def _process_and_store_content(self, source: KnowledgeSource, content: str):
        """Process and store content in the vector database."""
        try:
            # Split content into chunks
            chunks = self.text_splitter.split_text(content)
            
            # Create documents with metadata
            documents = []
            metadatas = []
            ids = []
            
            for i, chunk in enumerate(chunks):
                doc_id = f"{source.id}_{i}_{datetime.now().timestamp()}"
                
                documents.append(chunk)
                metadatas.append({
                    "source": source.name,
                    "source_type": source.source_type,
                    "source_url": source.url,
                    "priority": source.priority,
                    "timestamp": datetime.now().isoformat()
                })
                ids.append(doc_id)
            
            # Add to vector store
            self.vector_store.add_texts(
                texts=documents,
                metadatas=metadatas,
                ids=ids
            )
            
            log_event("content_stored", {
                "source": source.name,
                "chunks": len(chunks)
            })
            
        except Exception as e:
            log_event("content_storage_failed", {
                "source": source.name,
                "error": str(e)
            })
            raise
    
    async def get_optimization_insights(self, infrastructure_data: Dict[str, Any]) -> List[OptimizationInsight]:
        """Get optimization insights based on current infrastructure."""
        try:
            # Create a query based on infrastructure data
            query = await self._create_infrastructure_query(infrastructure_data)
            
            # Search for relevant knowledge
            relevant_docs = self.vector_store.similarity_search_with_score(
                query=query,
                k=10
            )
            
            # Extract insights from relevant documents
            insights = []
            for doc, score in relevant_docs:
                insight = await self._extract_insight_from_document(doc, infrastructure_data, score)
                if insight:
                    insights.append(insight)
            
            # Filter and rank insights
            filtered_insights = await self._filter_insights(insights, infrastructure_data)
            ranked_insights = await self._rank_insights(filtered_insights)
            
            track_metric("rag_insights_generated", len(ranked_insights))
            
            return ranked_insights[:5]  # Return top 5 insights
            
        except Exception as e:
            log_event("insights_generation_failed", {"error": str(e)})
            return []
    
    async def _create_infrastructure_query(self, infrastructure_data: Dict[str, Any]) -> str:
        """Create a query string based on infrastructure data."""
        services = []
        providers = []
        regions = []
        
        for resource in infrastructure_data.get('resources', []):
            services.append(resource.get('service', ''))
            providers.append(resource.get('provider', ''))
            regions.append(resource.get('region', ''))
        
        unique_services = list(set(filter(None, services)))
        unique_providers = list(set(filter(None, providers)))
        unique_regions = list(set(filter(None, regions)))
        
        query_parts = []
        
        if unique_services:
            query_parts.append(f"optimization for {', '.join(unique_services)}")
        
        if unique_providers:
            query_parts.append(f"{', '.join(unique_providers)} cost optimization")
        
        if unique_regions:
            query_parts.append(f"optimization in {', '.join(unique_regions)}")
        
        query_parts.append("cost reduction best practices")
        query_parts.append("resource optimization techniques")
        
        return " ".join(query_parts)
    
    async def _extract_insight_from_document(self, doc, infrastructure_data: Dict[str, Any], relevance_score: float) -> Optional[OptimizationInsight]:
        """Extract an optimization insight from a document."""
        try:
            content = doc.page_content
            metadata = doc.metadata
            
            # Use OpenAI to extract structured insights
            insight = await self._extract_insight_with_ai(content, infrastructure_data, metadata)
            
            if insight:
                insight.confidence_score = float(relevance_score)
                return insight
            
            return None
            
        except Exception as e:
            log_event("insight_extraction_failed", {"error": str(e)})
            return None
    
    async def _extract_insight_with_ai(self, content: str, infrastructure_data: Dict[str, Any], metadata: Dict) -> Optional[OptimizationInsight]:
        """Use AI to extract structured insights from content."""
        try:
            prompt = f"""
            Extract a cost optimization insight from the following content. 
            Infrastructure context: {json.dumps(infrastructure_data, default=str)}
            
            Content: {content[:2000]}
            
            Return a JSON object with the following structure:
            {{
                "title": "Brief title of the optimization",
                "content": "Detailed description of the optimization",
                "applicable_services": ["list", "of", "services"],
                "potential_savings_percentage": 0.0,
                "implementation_difficulty": "easy|medium|hard",
                "risk_level": "low|medium|high",
                "tags": ["list", "of", "tags"]
            }}
            """
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500
            )
            
            insight_data = json.loads(response.choices[0].message.content)
            
            return OptimizationInsight(
                id=f"insight_{datetime.now().timestamp()}",
                title=insight_data.get("title", ""),
                content=insight_data.get("content", ""),
                source=metadata.get("source", "Unknown"),
                confidence_score=0.0,  # Will be set later
                tags=insight_data.get("tags", []),
                applicable_services=insight_data.get("applicable_services", []),
                potential_savings_percentage=insight_data.get("potential_savings_percentage", 0.0),
                implementation_difficulty=insight_data.get("implementation_difficulty", "medium"),
                risk_level=insight_data.get("risk_level", "medium"),
                created_at=datetime.now()
            )
            
        except Exception as e:
            log_event("ai_insight_extraction_failed", {"error": str(e)})
            return None
    
    async def _filter_insights(self, insights: List[OptimizationInsight], infrastructure_data: Dict[str, Any]) -> List[OptimizationInsight]:
        """Filter insights based on relevance to current infrastructure."""
        filtered = []
        
        current_services = [r.get('service') for r in infrastructure_data.get('resources', [])]
        
        for insight in insights:
            # Check if insight is applicable to current services
            if any(service in insight.applicable_services for service in current_services):
                filtered.append(insight)
            elif not insight.applicable_services:  # General insights
                filtered.append(insight)
        
        return filtered
    
    async def _rank_insights(self, insights: List[OptimizationInsight]) -> List[OptimizationInsight]:
        """Rank insights by relevance and potential impact."""
        def ranking_score(insight: OptimizationInsight) -> float:
            savings_score = insight.potential_savings_percentage / 100
            confidence_score = insight.confidence_score
            difficulty_penalty = {"easy": 0, "medium": 0.1, "hard": 0.3}[insight.implementation_difficulty]
            risk_penalty = {"low": 0, "medium": 0.1, "high": 0.2}[insight.risk_level]
            
            return savings_score + confidence_score - difficulty_penalty - risk_penalty
        
        return sorted(insights, key=ranking_score, reverse=True)
    
    async def get_similar_optimizations(self, optimization_type: str, context: str) -> List[Dict[str, Any]]:
        """Find similar optimizations from the knowledge base."""
        try:
            query = f"{optimization_type} optimization {context}"
            
            relevant_docs = self.vector_store.similarity_search_with_score(
                query=query,
                k=5
            )
            
            similar_optimizations = []
            for doc, score in relevant_docs:
                similar_optimizations.append({
                    "content": doc.page_content[:500],
                    "source": doc.metadata.get("source", "Unknown"),
                    "relevance_score": float(score),
                    "url": doc.metadata.get("source_url", "")
                })
            
            return similar_optimizations
            
        except Exception as e:
            log_event("similar_optimizations_search_failed", {"error": str(e)})
            return []
    
    async def update_knowledge_base_manually(self):
        """Manually trigger a knowledge base update."""
        await self._update_knowledge_base()
        log_event("manual_knowledge_base_update_completed")
    
    async def get_knowledge_base_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge base."""
        try:
            # Get collection info from ChromaDB
            collection = self.chroma_client.get_collection("cost_optimization_knowledge")
            count = collection.count()
            
            return {
                "total_documents": count,
                "knowledge_sources": len(self.knowledge_sources),
                "last_update": datetime.now().isoformat(),
                "vector_store_type": "ChromaDB",
                "embedding_model": settings.VECTOR_EMBEDDING_MODEL
            }
            
        except Exception as e:
            log_event("knowledge_base_stats_failed", {"error": str(e)})
            return {"error": str(e)}
