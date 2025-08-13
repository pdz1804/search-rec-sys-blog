"""
Simplified Elasticsearch data loader.

This module provides a clean, simple implementation for loading blog data
into Elasticsearch with minimal complexity and maximum maintainability.
"""

import json
import hashlib
from typing import Dict, Any, List, Optional, Generator
from pathlib import Path

from elasticsearch import Elasticsearch, helpers
from elasticsearch.exceptions import TransportError, ConnectionError, RequestError
from pydantic import ValidationError

from .models import User, Article, BlogData
from .data_validator import DataValidator
from utils.logger import get_logger


class DataLoader:
    """
    Simple data loader for Elasticsearch.
    
    This class handles loading Users and Articles data into Elasticsearch
    with a clean, straightforward approach.
    """
    
    def __init__(self, 
                 elasticsearch_url: str = "http://localhost:9200",
                 users_index: str = "blog-users",
                 articles_index: str = "blog-articles",
                 data_file: str = "data/generated.json",
                 users_pipeline: str = "blog-users-pipeline",
                 articles_pipeline: str = "blog-articles-pipeline"):
        """
        Initialize the data loader.
        
        Args:
            elasticsearch_url: Elasticsearch connection URL
            users_index: Index name for users
            articles_index: Index name for articles
            data_file: Path to the data file
            users_pipeline: Pipeline name for users
            articles_pipeline: Pipeline name for articles
        """
        self.elasticsearch_url = elasticsearch_url
        self.users_index = users_index
        self.articles_index = articles_index
        self.users_pipeline = users_pipeline
        self.articles_pipeline = articles_pipeline
        self.data_file = Path(data_file)
        self.logger = get_logger()
        self._es_client: Optional[Elasticsearch] = None
        self.validator = DataValidator()
        
        # Statistics
        self.stats = {
            'users_loaded': 0,
            'articles_loaded': 0,
            'users_failed': 0,
            'articles_failed': 0,
            'validation_errors': 0,
            'validation_warnings': 0
        }
    
    @property
    def es_client(self) -> Elasticsearch:
        """Get or create Elasticsearch client."""
        if self._es_client is None:
            try:
                self._es_client = Elasticsearch(self.elasticsearch_url, request_timeout=120)
                self._es_client.ping()
                self.logger.info(f"Connected to Elasticsearch at {self.elasticsearch_url}")
            except ConnectionError as e:
                self.logger.error(f"Failed to connect to Elasticsearch: {e}")
                raise
        return self._es_client
    
    def load_data_file(self, validate_relationships: bool = True) -> BlogData:
        """
        Load and validate data from the JSON file.
        
        Args:
            validate_relationships: Whether to perform comprehensive relationship validation
        
        Returns:
            BlogData: Validated blog data
        """
        try:
            self.logger.info(f"Loading data from {self.data_file}")
            with open(self.data_file, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)

            # The ** expands the dict into keyword args 
            # so each top‑level JSON key must match a BlogData field name (e.g. Users, Articles).
            blog_data = BlogData(**raw_data)
            self.logger.info(f"Loaded {len(blog_data.Users)} users and {len(blog_data.Articles)} articles")
            
            # Perform comprehensive validation if requested
            if validate_relationships:
                self.logger.info("Performing comprehensive data validation...")
                is_valid, errors, warnings = self.validator.validate_blog_data(blog_data)
                
                self.stats['validation_errors'] = len(errors)
                self.stats['validation_warnings'] = len(warnings)
                
                if errors:
                    self.logger.error(f"Data validation failed with {len(errors)} errors:")
                    for error in errors[:10]:  # Show first 10 errors
                        self.logger.error(f"  - {error}")
                    if len(errors) > 10:
                        self.logger.error(f"  ... and {len(errors) - 10} more errors")
                    
                    raise ValidationError(f"Data validation failed with {len(errors)} errors")
                
                if warnings:
                    self.logger.warning(f"Data validation completed with {len(warnings)} warnings:")
                    for warning in warnings:  # Show first 5 warnings
                        self.logger.warning(f"  - {warning}")
                    # if len(warnings) > 5:
                    #     self.logger.warning(f"  ... and {len(warnings) - 5} more warnings")
                
                self.logger.info("✓ Data validation passed")
            
            return blog_data
            
        except FileNotFoundError:
            self.logger.error(f"Data file not found: {self.data_file}")
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in data file: {e}")
            raise
        except ValidationError as e:
            self.logger.error(f"Data validation failed: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error loading data file: {e}")
            raise
    
    def generate_user_id(self, user_data: Dict[str, Any]) -> str:
        """Generate a unique ID for a user document."""
        if user_data.get('id'):
            return f"user_{user_data['id']}"
        
        # Fallback to hash-based ID
        key_data = f"{user_data.get('email', '')}{user_data.get('full_name', '')}"
        return hashlib.sha256(key_data.encode('utf-8')).hexdigest()[:16]
    
    def generate_article_id(self, article_data: Dict[str, Any]) -> str:
        """Generate a unique ID for an article document."""
        if article_data.get('id'):
            return f"article_{article_data['id']}"
        
        # Fallback to hash-based ID
        key_data = f"{article_data.get('title', '')}{article_data.get('author_id', '')}"
        return hashlib.sha256(key_data.encode('utf-8')).hexdigest()[:16]
    
    def generate_user_actions(self, users: List[User]) -> Generator[Dict[str, Any], None, None]:
        """Generate Elasticsearch bulk actions for users."""
        for user in users:
            try:
                doc = user.to_elasticsearch_doc()
                action = {
                    '_index': self.users_index,
                    '_id': self.generate_user_id(user.dict()),
                    '_source': doc
                }
                if self.users_pipeline:
                    # Only add pipeline if it exists, otherwise log warning
                    try:
                        self.es_client.ingest.get_pipeline(id=self.users_pipeline)
                        action['pipeline'] = self.users_pipeline
                    except:
                        # Pipeline doesn't exist, continue without it
                        pass
                yield action
            except Exception as e:
                self.logger.error(f"Error processing user {user.id}: {e}")
                self.stats['users_failed'] += 1
    
    def generate_article_actions(self, articles: List[Article]) -> Generator[Dict[str, Any], None, None]:
        """Generate Elasticsearch bulk actions for articles."""
        for article in articles:
            try:
                doc = article.to_elasticsearch_doc()
                action = {
                    '_index': self.articles_index,
                    '_id': self.generate_article_id(article.dict()),
                    '_source': doc
                }
                if self.articles_pipeline:
                    # Only add pipeline if it exists, otherwise log warning
                    try:
                        self.es_client.ingest.get_pipeline(id=self.articles_pipeline)
                        action['pipeline'] = self.articles_pipeline
                    except:
                        # Pipeline doesn't exist, continue without it
                        pass
                yield action
            except Exception as e:
                self.logger.error(f"Error processing article {article.id}: {e}")
                self.stats['articles_failed'] += 1
    
    def create_index(self, index_name: str, mapping_file: str) -> bool:
        """
        Create Elasticsearch index with mapping.
        
        Args:
            index_name: Name of the index to create
            mapping_file: Path to mapping JSON file
            
        Returns:
            bool: True if successful
        """
        try:
            # Check if index already exists first
            if self.es_client.indices.exists(index=index_name):
                self.logger.info(f"✓ Index '{index_name}' already exists")
                return True
            
            mapping_path = Path("es") / mapping_file
            if not mapping_path.exists():
                self.logger.error(f"Mapping file not found: {mapping_path}")
                return False
            
            with open(mapping_path, 'r', encoding='utf-8') as f:
                mapping = json.load(f)
            
            # Create index
            response = self.es_client.indices.create(index=index_name, body=mapping)
            self.logger.info(f"✓ Created index '{index_name}'")
            return True
            
        except RequestError as e:
            # Handle specific error cases
            if "resource_already_exists_exception" in str(e):
                self.logger.info(f"✓ Index '{index_name}' already exists")
                return True
            else:
                self.logger.error(f"Failed to create index '{index_name}': {e}")
                return False
        except Exception as e:
            self.logger.error(f"Unexpected error creating index '{index_name}': {e}")
            return False
    
    def create_pipeline(self, pipeline_name: str, pipeline_file: str) -> bool:
        """
        Create Elasticsearch ingest pipeline.
        
        Args:
            pipeline_name: Name of the pipeline to create
            pipeline_file: Path to pipeline JSON file
            
        Returns:
            bool: True if successful
        """
        try:
            # Check if pipeline already exists
            try:
                existing = self.es_client.ingest.get_pipeline(id=pipeline_name)
                if existing:
                    self.logger.info(f"✓ Pipeline '{pipeline_name}' already exists")
                    return True
            except:
                # Pipeline doesn't exist, continue with creation
                pass
            
            pipeline_path = Path("es") / pipeline_file
            if not pipeline_path.exists():
                self.logger.error(f"Pipeline file not found: {pipeline_path}")
                return False
            
            with open(pipeline_path, 'r', encoding='utf-8') as f:
                pipeline = json.load(f)
            
            # Create pipeline with version compatibility handling
            try:
                response = self.es_client.ingest.put_pipeline(id=pipeline_name, body=pipeline)
                self.logger.info(f"✓ Created pipeline '{pipeline_name}'")
                return True
            except RequestError as e:
                # Handle version compatibility issues
                if "media_type_header_exception" in str(e) or "Accept version" in str(e):
                    self.logger.warning(f"Pipeline creation skipped due to version compatibility: {pipeline_name}")
                    self.logger.info(f"You can create the pipeline manually using Kibana or curl commands")
                    return True  # Don't fail the entire process
                else:
                    raise e
            
        except RequestError as e:
            self.logger.error(f"Failed to create pipeline '{pipeline_name}': {e}")
            # Don't fail completely for pipeline issues
            self.logger.warning(f"Continuing without pipeline '{pipeline_name}' - data will still load")
            return True
        except Exception as e:
            self.logger.error(f"Unexpected error creating pipeline '{pipeline_name}': {e}")
            self.logger.warning(f"Continuing without pipeline '{pipeline_name}' - data will still load")
            return True
    
    def setup_elasticsearch(self) -> bool:
        """
        Setup Elasticsearch indices and pipelines.
        
        Returns:
            bool: True if all setup successful
        """
        self.logger.info("Setting up Elasticsearch indices and pipelines...")
        
        success = True
        
        # Create indices
        success &= self.create_index(self.users_index, "users_mapping.json")
        success &= self.create_index(self.articles_index, "articles_mapping.json")
        
        # Create pipelines
        success &= self.create_pipeline(self.users_pipeline, "users_pipeline.json")
        success &= self.create_pipeline(self.articles_pipeline, "articles_pipeline.json")
        
        if success:
            self.logger.info("✓ Elasticsearch setup completed successfully")
        else:
            self.logger.error("✗ Elasticsearch setup failed")
        
        return success
    
    def load_users(self, users: List[User]) -> Dict[str, int]:
        """
        Load users into Elasticsearch.
        
        Args:
            users: List of user objects
            
        Returns:
            Dict[str, int]: Loading statistics
        """
        if not users:
            self.logger.info("No users to load")
            return {'success': 0, 'failed': 0}
        
        self.logger.info(f"Loading {len(users)} users to index '{self.users_index}'")
        
        success_count = 0
        failed_count = 0
        
        try:
            # Use streaming_bulk with proper error handling
            for success, info in helpers.streaming_bulk(
                self.es_client,
                self.generate_user_actions(users),
                chunk_size=1000,
                request_timeout=120,
                max_retries=3,
                initial_backoff=2,
                max_backoff=600
            ):
                if success:
                    success_count += 1
                else:
                    failed_count += 1
                    # Log detailed error information
                    self.logger.error(f"Failed to index user: {info}")
                    if isinstance(info, dict):
                        if 'index' in info and 'error' in info['index']:
                            error_details = info['index']['error']
                            self.logger.error(f"User indexing error details: {error_details}")
                        elif 'create' in info and 'error' in info['create']:
                            error_details = info['create']['error']
                            self.logger.error(f"User creation error details: {error_details}")
                        elif 'error' in info:
                            self.logger.error(f"User error details: {info['error']}")
                    
                    # Also log the document that failed
                    if hasattr(info, '__dict__'):
                        self.logger.debug(f"Failed document info: {vars(info)}")
            
            self.stats['users_loaded'] = success_count
            self.stats['users_failed'] += failed_count
            
            self.logger.info(f"Users loading completed: {success_count} success, {failed_count} failed")
            return {'success': success_count, 'failed': failed_count}
            
        except helpers.BulkIndexError as e:
            # Handle bulk indexing errors with detailed information
            self.logger.error(f"Bulk indexing error while loading users: {e}")
            
            # Log details of failed documents
            for error in e.errors:
                self.logger.error(f"User indexing error: {error}")
                failed_count += 1
            
            self.stats['users_loaded'] = success_count
            self.stats['users_failed'] += failed_count
            
            self.logger.info(f"Users loading completed with errors: {success_count} success, {failed_count} failed")
            return {'success': success_count, 'failed': failed_count}
            
        except TransportError as e:
            self.logger.error(f"Elasticsearch transport error while loading users: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error while loading users: {e}")
            raise
    
    def load_articles(self, articles: List[Article]) -> Dict[str, int]:
        """
        Load articles into Elasticsearch.
        
        Args:
            articles: List of article objects
            
        Returns:
            Dict[str, int]: Loading statistics
        """
        if not articles:
            self.logger.info("No articles to load")
            return {'success': 0, 'failed': 0}
        
        self.logger.info(f"Loading {len(articles)} articles to index '{self.articles_index}'")
        
        success_count = 0
        failed_count = 0
        
        try:
            # Use streaming_bulk with proper error handling
            for success, info in helpers.streaming_bulk(
                self.es_client,
                self.generate_article_actions(articles),
                chunk_size=1000,
                request_timeout=120,
                max_retries=3,
                initial_backoff=2,
                max_backoff=600
            ):
                if success:
                    success_count += 1
                else:
                    failed_count += 1
                    # Log detailed error information
                    self.logger.error(f"Failed to index article: {info}")
                    if isinstance(info, dict):
                        if 'index' in info and 'error' in info['index']:
                            error_details = info['index']['error']
                            self.logger.error(f"Article indexing error details: {error_details}")
                        elif 'create' in info and 'error' in info['create']:
                            error_details = info['create']['error']
                            self.logger.error(f"Article creation error details: {error_details}")
                        elif 'error' in info:
                            self.logger.error(f"Article error details: {info['error']}")
                    
                    # Also log the document that failed
                    if hasattr(info, '__dict__'):
                        self.logger.debug(f"Failed document info: {vars(info)}")
            
            self.stats['articles_loaded'] = success_count
            self.stats['articles_failed'] += failed_count
            
            self.logger.info(f"Articles loading completed: {success_count} success, {failed_count} failed")
            return {'success': success_count, 'failed': failed_count}
            
        except helpers.BulkIndexError as e:
            # Handle bulk indexing errors with detailed information
            self.logger.error(f"Bulk indexing error while loading articles: {e}")
            
            # Log details of failed documents
            for error in e.errors:
                self.logger.error(f"Article indexing error: {error}")
                failed_count += 1
            
            self.stats['articles_loaded'] = success_count
            self.stats['articles_failed'] += failed_count
            
            self.logger.info(f"Articles loading completed with errors: {success_count} success, {failed_count} failed")
            return {'success': success_count, 'failed': failed_count}
            
        except TransportError as e:
            self.logger.error(f"Elasticsearch transport error while loading articles: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error while loading articles: {e}")
            raise
    
    def load_all(self) -> Dict[str, Dict[str, int]]:
        """
        Load all data (users and articles) into Elasticsearch.
        
        Returns:
            Dict[str, Dict[str, int]]: Complete loading statistics
        """
        self.logger.info("Starting complete data loading process")
        
        # Load and validate data
        blog_data = self.load_data_file()
        
        # Load users first
        user_results = self.load_users(blog_data.Users)
        
        # Then load articles
        article_results = self.load_articles(blog_data.Articles)
        
        # Log summary
        total_success = user_results['success'] + article_results['success']
        total_failed = user_results['failed'] + article_results['failed']
        
        self.logger.info(f"Data loading completed: {total_success} success, {total_failed} failed")
        
        return {
            'users': user_results,
            'articles': article_results,
            'summary': {
                'total_success': total_success,
                'total_failed': total_failed
            }
        }
    
    def get_statistics(self) -> Dict[str, int]:
        """Get current loading statistics."""
        return self.stats.copy()



