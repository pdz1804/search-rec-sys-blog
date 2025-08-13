"""
Main entry point for the Elasticsearch blog system.

This script provides:
1. Data loading functionality for Elasticsearch
2. FastAPI web server for search with LLM integration

Usage:
    # Data loading
    python main.py --load-all
    python main.py --load-data
    python main.py --validate
    
    # API server
    python main.py --api
    python main.py --api --host 0.0.0.0 --port 8000
"""

import argparse
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from ingest.data_loader import DataLoader
from utils.logger import get_logger, set_log_level

load_dotenv()

def create_argument_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Elasticsearch blog system with data loading and API search",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Data loading
  python main.py --setup                       # Setup indices and pipelines only
  python main.py --load-all                    # Setup and load all data
  python main.py --load-data                   # Load data (assumes setup done)
  python main.py --validate                    # Only validate data
  
  # API server
  python main.py --api                         # Start API server
  python main.py --api --host localhost --port 8000  # Custom host/port
        """
    )
    
    # Action group (mutually exclusive)
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument(
        '--setup',
        action='store_true',
        help='Setup Elasticsearch indices and pipelines'
    )
    action_group.add_argument(
        '--load-all',
        action='store_true',
        help='Setup and load all data (users and articles)'
    )
    action_group.add_argument(
        '--load-data',
        action='store_true',
        help='Load data without setup (assumes indices/pipelines exist)'
    )
    action_group.add_argument(
        '--validate',
        action='store_true',
        help='Only validate data file'
    )
    action_group.add_argument(
        '--api',
        action='store_true',
        help='Start FastAPI server for search with LLM integration'
    )
    
    # Data loading configuration options
    parser.add_argument(
        '--es-url',
        default='http://localhost:9200',
        help='Elasticsearch URL (default: http://localhost:9200)'
    )
    parser.add_argument(
        '--users-index',
        default='blog-users',
        help='Users index name (default: blog-users)'
    )
    parser.add_argument(
        '--articles-index',
        default='blog-articles',
        help='Articles index name (default: blog-articles)'
    )
    parser.add_argument(
        '--data-file',
        default='data/generated.json',
        help='Data file path (default: data/generated.json)'
    )
    parser.add_argument(
        '--skip-validation',
        action='store_true',
        help='Skip comprehensive relationship validation'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Log level (default: INFO)'
    )
    
    # API server configuration options
    parser.add_argument(
        '--host',
        default='localhost',
        help='API server host (default: localhost)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='API server port (default: 8000)'
    )
    
    return parser


def validate_data_only(data_loader: DataLoader) -> bool:
    """Validate data without loading."""
    try:
        blog_data = data_loader.load_data_file(validate_relationships=True)
        print("✓ Data validation completed successfully")
        return True
    except Exception as e:
        print(f"✗ Data validation failed: {e}")
        return False


def start_api_server(host: str, port: int):
    """Start the FastAPI server."""
    try:
        # Import here to avoid loading FastAPI dependencies for data loading
        import uvicorn
        from api.main import app
        
        logger = get_logger()
        logger.info(f"Starting API server on {host}:{port}")
        
        print(f"🚀 Starting Blog Search API server...")
        print(f"📡 Server: http://{host}:{port}")
        print(f"📚 API docs: http://{host}:{port}/docs")
        print(f"🔍 Health check: http://{host}:{port}/health")
        print(f"💡 Examples: http://{host}:{port}/examples")
        print()
        print("Press Ctrl+C to stop the server")
        
        # Use our logger configuration instead of uvicorn's default
        uvicorn.run(
            app, 
            host=host, 
            port=port, 
            log_level=None,  # Disable uvicorn's logging
            access_log=False  # Disable uvicorn's access logs
        )
        
    except ImportError as e:
        print(f"❌ API server dependencies not installed.")
        print("To use the API server, install the required dependencies:")
        print("  pip install fastapi uvicorn[standard] openai")
        print()
        print("Or install all dependencies:")
        print("  pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"❌ API server error: {e}")
        sys.exit(1)


def main():
    """Main entry point."""
    args = create_argument_parser().parse_args()
    
    # Set up logging
    set_log_level(args.log_level)
    logger = get_logger()
    
    # Log configuration
    logger.info("Starting Elasticsearch blog system")
    logger.info(f"Configuration: ES URL={args.es_url}, Log Level={args.log_level}")
    
    try:
        # Handle API server
        if args.api:
            start_api_server(args.host, args.port)
            return
        
        # Handle data loading operations
        data_loader = DataLoader(
            elasticsearch_url=args.es_url,
            users_index=args.users_index,
            articles_index=args.articles_index,
            data_file=args.data_file,
            users_pipeline=f"{args.users_index}-pipeline",
            articles_pipeline=f"{args.articles_index}-pipeline"
        )
        
        if args.validate:
            success = validate_data_only(data_loader)
            sys.exit(0 if success else 1)
        
        if args.setup:
            success = data_loader.setup_elasticsearch()
            sys.exit(0 if success else 1)
        
        # Load data
        validate_relationships = not args.skip_validation
        blog_data = data_loader.load_data_file(validate_relationships=validate_relationships)
        
        if args.load_all:
            setup_success = data_loader.setup_elasticsearch()
            if not setup_success:
                logger.error("Failed to setup Elasticsearch. Aborting data loading.")
                sys.exit(1)
            results = data_loader.load_all()
            logger.info(f"Loading completed: {results['summary']}")
        
        elif args.load_data:
            results = data_loader.load_all()
            logger.info(f"Loading completed: {results['summary']}")
        
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"An unhandled error occurred: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
