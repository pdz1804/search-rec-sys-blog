"""
Centralized logging system for the Elasticsearch data loading project.

This module provides a single logger instance that is used throughout the entire
project. The logger writes to a timestamped file in the logs/ directory.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


class ProjectLogger:
    """
    Singleton logger for the entire project.
    
    This class ensures only one logger instance exists and provides
    consistent logging configuration across all modules.
    """
    
    _instance: Optional['ProjectLogger'] = None
    _logger: Optional[logging.Logger] = None
    
    def __new__(cls) -> 'ProjectLogger':
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super(ProjectLogger, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize logger if not already done."""
        if self._logger is None:
            self._setup_logger()
    
    def _setup_logger(self) -> None:
        """Set up the project logger with file and console handlers."""
        # Create logs directory
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        # Create timestamped log filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"elasticsearch_loader_{timestamp}.log"
        log_path = logs_dir / log_filename
        
        # Create logger
        self._logger = logging.getLogger("elasticsearch_data_loader")
        self._logger.setLevel(logging.INFO)
        
        # Clear any existing handlers
        self._logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self._logger.addHandler(console_handler)
        
        # File handler
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self._logger.addHandler(file_handler)
        
        # Log the initialization
        self._logger.info(f"Logger initialized. Log file: {log_path}")
        
        # Set log level from environment variable if provided
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        if hasattr(logging, log_level):
            self._logger.setLevel(getattr(logging, log_level))
            console_handler.setLevel(getattr(logging, log_level))
    
    @property
    def logger(self) -> logging.Logger:
        """Get the logger instance."""
        return self._logger
    
    def set_level(self, level: str) -> None:
        """Set the logging level."""
        if hasattr(logging, level.upper()):
            log_level = getattr(logging, level.upper())
            self._logger.setLevel(log_level)
            # Update all handlers to the new level
            for handler in self._logger.handlers:
                handler.setLevel(log_level)


# Global logger instance
_project_logger = ProjectLogger()
logger = _project_logger.logger


def get_logger() -> logging.Logger:
    """
    Get the global project logger.
    
    Returns:
        logging.Logger: The configured logger instance
    """
    return logger


def set_log_level(level: str) -> None:
    """
    Set the global logging level.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    _project_logger.set_level(level)
