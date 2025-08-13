"""
Data validation module for comprehensive data integrity checks.

This module validates relationships between users and articles,
ensuring data consistency and referential integrity.
"""

from typing import Dict, List, Set, Tuple, Any
from .models import User, Article, BlogData
from utils.logger import get_logger


class DataValidator:
    """
    Comprehensive data validator for blog data.
    
    Validates relationships between users and articles to ensure data integrity.
    """
    
    def __init__(self):
        """Initialize the data validator."""
        self.logger = get_logger()
        self.validation_errors: List[str] = []
        self.warnings: List[str] = []
    
    def validate_blog_data(self, blog_data: BlogData) -> Tuple[bool, List[str], List[str]]:
        """
        Validate complete blog data structure.
        
        Args:
            blog_data: BlogData instance to validate
            
        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        self.logger.info("Starting comprehensive data validation")
        self.validation_errors.clear()
        self.warnings.clear()
        
        # Extract IDs for validation
        user_ids = {user.id for user in blog_data.Users if user.id is not None}
        article_ids = {article.id for article in blog_data.Articles if article.id is not None}
        
        self.logger.info(f"Validating {len(blog_data.Users)} users and {len(blog_data.Articles)} articles")
        self.logger.info(f"Found {len(user_ids)} unique user IDs and {len(article_ids)} unique article IDs")
        
        # Validate users
        self._validate_users(blog_data.Users, user_ids, article_ids)
        
        # Validate articles
        self._validate_articles(blog_data.Articles, user_ids, article_ids)
        
        # Cross-validation
        self._validate_cross_references(blog_data.Users, blog_data.Articles, user_ids, article_ids)
        
        is_valid = len(self.validation_errors) == 0
        
        self.logger.info(f"Validation completed: {len(self.validation_errors)} errors, {len(self.warnings)} warnings")
        
        return is_valid, self.validation_errors.copy(), self.warnings.copy()
    
    def _validate_users(self, users: List[User], user_ids: Set[int], article_ids: Set[int]) -> None:
        """Validate user data and relationships."""
        self.logger.info("Validating user data...")
        
        seen_emails = set()
        
        for user in users:
            user_context = f"User {user.id or 'unknown'}"
            
            # Check for duplicate emails
            if user.email:
                if user.email in seen_emails:
                    self.validation_errors.append(f"{user_context}: Duplicate email '{user.email}'")
                else:
                    seen_emails.add(user.email)
            
            # Validate user likes references
            if user.likes:
                for article_id in user.likes:
                    if article_id not in article_ids and article_id != 0:
                        self.validation_errors.append(
                            f"{user_context}: Likes non-existent article {article_id}"
                        )
            
            # Validate user dislikes references
            if user.dislikes:
                for article_id in user.dislikes:
                    if article_id not in article_ids and article_id != 0:
                        self.validation_errors.append(
                            f"{user_context}: Dislikes non-existent article {article_id}"
                        )
            
            # Validate bookmarks references
            if user.bookmarks:
                for article_id in user.bookmarks:
                    if article_id not in article_ids and article_id != 0:
                        self.validation_errors.append(
                            f"{user_context}: Bookmarks non-existent article {article_id}"
                        )
            
            # Validate following relationships
            if user.following:
                for followed_id in user.following:
                    if followed_id == user.id:
                        self.validation_errors.append(f"{user_context}: User follows themselves")
                    elif followed_id not in user_ids and followed_id != 0:
                        self.validation_errors.append(
                            f"{user_context}: Follows non-existent user {followed_id}"
                        )
            
            # Validate followers relationships
            if user.followers:
                for follower_id in user.followers:
                    if follower_id == user.id:
                        self.validation_errors.append(f"{user_context}: User is their own follower")
                    elif follower_id not in user_ids and follower_id != 0:
                        self.validation_errors.append(
                            f"{user_context}: Has non-existent follower {follower_id}"
                        )
            
            # Check for conflicts between likes and dislikes
            if user.likes and user.dislikes:
                conflicts = set(user.likes) & set(user.dislikes)
                if conflicts:
                    self.warnings.append(
                        f"{user_context}: User both likes and dislikes articles: {list(conflicts)}"
                    )
    
    def _validate_articles(self, articles: List[Article], user_ids: Set[int], article_ids: Set[int]) -> None:
        """Validate article data and relationships."""
        self.logger.info("Validating article data...")
        
        for article in articles:
            article_context = f"Article {article.id or 'unknown'}"
            
            # Validate author exists
            if article.author_id is not None:
                if article.author_id not in user_ids:
                    self.validation_errors.append(
                        f"{article_context}: References non-existent author {article.author_id}"
                    )
            
            # Check for missing author name
            if not article.author_name:
                self.warnings.append(f"{article_context}: Missing author name")
            
            # Validate engagement metrics consistency
            if article.likes is not None and article.likes < 0:
                self.validation_errors.append(f"{article_context}: Negative likes count")
            
            if article.dislikes is not None and article.dislikes < 0:
                self.validation_errors.append(f"{article_context}: Negative dislikes count")
            
            if article.views is not None and article.views < 0:
                self.validation_errors.append(f"{article_context}: Negative views count")
            
            # Check for unrealistic engagement ratios
            if (article.likes is not None and article.views is not None and 
                article.views > 0 and article.likes > article.views):
                self.warnings.append(
                    f"{article_context}: Likes ({article.likes}) exceed views ({article.views})"
                )
    
    def _validate_cross_references(self, users: List[User], articles: List[Article], 
                                 user_ids: Set[int], article_ids: Set[int]) -> None:
        """Validate cross-references between users and articles."""
        self.logger.info("Validating cross-references...")
        
        # 1. Build reverse engagement maps
        # Build article engagement maps
        article_likes_by_users = {}
        article_dislikes_by_users = {}
        article_bookmarks_by_users = {}
        
        for user in users:
            if user.id is not None:
                for article_id in user.likes:
                    if article_id in article_ids:
                        if article_id not in article_likes_by_users:
                            article_likes_by_users[article_id] = []
                        article_likes_by_users[article_id].append(user.id)
                
                for article_id in user.dislikes:
                    if article_id in article_ids:
                        if article_id not in article_dislikes_by_users:
                            article_dislikes_by_users[article_id] = []
                        article_dislikes_by_users[article_id].append(user.id)
                
                for article_id in user.bookmarks:
                    if article_id in article_ids:
                        if article_id not in article_bookmarks_by_users:
                            article_bookmarks_by_users[article_id] = []
                        article_bookmarks_by_users[article_id].append(user.id)
        
        # 2. Build social graph maps
        # Validate follower/following symmetry
        following_map = {}
        followers_map = {}
        
        for user in users:
            if user.id is not None:
                following_map[user.id] = set(user.following)
                followers_map[user.id] = set(user.followers)
        
        # 3. Detect asymmetric follow relationships
        # Check for asymmetric relationships
        # - Check list of following of A for example it's B
        # - Then check if B follows A
        # - If not, add a warning
        # - If so, continue checking other users
        for user_id, following in following_map.items():
            for followed_id in following:
                if followed_id in followers_map:
                    if user_id not in followers_map[followed_id]:
                        self.warnings.append(
                            f"User {user_id} follows User {followed_id}, but relationship is not reciprocal"
                        )
        
        # 4. Article likes consistency check
        # Check article engagement consistency
        for article in articles:
            if article.id in article_likes_by_users:
                user_likes_count = len(article_likes_by_users[article.id])
                if article.likes is not None and abs(article.likes - user_likes_count) > user_likes_count * 0.5:
                    self.warnings.append(
                        f"Article {article.id}: Likes count ({article.likes}) doesn't match user interactions ({user_likes_count})"
                    )
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get a summary of validation results."""
        return {
            'errors_count': len(self.validation_errors),
            'warnings_count': len(self.warnings),
            'errors': self.validation_errors.copy(),
            'warnings': self.warnings.copy()
        }
