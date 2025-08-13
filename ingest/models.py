"""
Simplified data models for the blog application using Pydantic.

This module defines clean, simple data models for Users and Articles
with minimal validation requirements.

---

Assuming BlogData is a Pydantic model (it is imported from .models):

Pydantic inspects the model field definitions (types like List[User], List[Article], etc.).
It walks the raw dict and:
- Matches keys to fields.
- For each item in (say) Users, it builds a User model (also Pydantic) applying type coercion (e.g. strings to ints/datetimes) and field validators.
- Collects all validation errors; if any, raises ValidationError.
- Nested models are recursively validated (so an invalid field inside a single Article will surface as a structured error).
- After success, you get a fully typed object graph: BlogData → list of User objects, list of Article objects, each with Python-native types.

Immediate benefits

- Centralized schema: structure enforced in one place (models.py).
- Automatic type conversion & validation (missing required fields, wrong types, bad formats).
- Clear error reporting (Pydantic's aggregated ValidationError).
- Safe attribute access later (you don't keep indexing raw dicts).

"""



from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class User(BaseModel):
    """
    User model representing a blog user.
    
    All fields are optional to match the updated schema requirements.
    """
    
    id: Optional[int] = Field(None, description="User ID")
    full_name: Optional[str] = Field(None, description="User's full name")
    email: Optional[str] = Field(None, description="User's email address")
    password: Optional[str] = Field(None, description="Password hash")
    avatar_url: Optional[str] = Field(None, description="URL to user's avatar image")
    role: Optional[str] = Field(None, description="User's role in the system")
    created_at: Optional[str] = Field(None, description="Account creation timestamp")
    
    # User interaction arrays - can contain 0 values
    likes: List[int] = Field(default_factory=list, description="Article IDs the user likes")
    dislikes: List[int] = Field(default_factory=list, description="Article IDs the user dislikes")
    bookmarks: List[int] = Field(default_factory=list, description="Bookmarked article IDs")
    
    # Social relationship arrays - can contain 0 values
    following: List[int] = Field(default_factory=list, description="User IDs this user follows")
    followers: List[int] = Field(default_factory=list, description="User IDs who follow this user")
    
    def to_elasticsearch_doc(self) -> Dict[str, Any]:
        """
        Convert the user model to an Elasticsearch document format.
        
        Returns:
            Dict[str, Any]: Document ready for Elasticsearch indexing
        """
        doc = self.model_dump()
        # Add computed fields for Elasticsearch
        doc['total_likes'] = len(self.likes)
        doc['total_dislikes'] = len(self.dislikes)
        doc['total_bookmarks'] = len(self.bookmarks)
        doc['total_following'] = len(self.following)
        doc['total_followers'] = len(self.followers)
        doc['engagement_score'] = len(self.likes) + len(self.bookmarks) - len(self.dislikes)
        
        # Calculate user_activity_level (consistent with pipeline)
        activity_total = doc['total_likes'] + doc['total_bookmarks']
        if activity_total > 10:
            doc['user_activity_level'] = 'high'
        elif activity_total > 5:
            doc['user_activity_level'] = 'medium'
        else:
            doc['user_activity_level'] = 'low'
        
        # Calculate social_influence (consistent with pipeline)
        doc['social_influence'] = doc['total_followers'] * 2 + doc['total_following']
        
        return doc


class Article(BaseModel):
    """
    Article model representing a blog article.
    
    All fields are optional to match the updated schema requirements.
    Tags are now simple strings without enum restrictions.
    """
    
    id: Optional[int] = Field(None, description="Article ID")
    title: Optional[str] = Field(None, description="Article title")
    content: Optional[str] = Field(None, description="Article content")
    summary: Optional[str] = Field(None, description="Article summary")
    status: Optional[str] = Field(None, description="Publication status")
    
    # Tags are now simple strings without enum restrictions
    tags: List[str] = Field(default_factory=list, description="Article tags")
    
    image: Optional[str] = Field(None, description="URL to article's featured image")
    
    # Author information
    author_id: Optional[int] = Field(None, description="ID of the article author")
    author_name: Optional[str] = Field(None, description="Display name of the author")
    
    # Engagement metrics
    likes: Optional[int] = Field(None, description="Number of likes")
    dislikes: Optional[int] = Field(None, description="Number of dislikes")
    views: Optional[int] = Field(None, description="Number of views")
    
    # Timestamps
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")
    
    # Optional timestamp for compatibility with existing data
    createdTs: Optional[int] = Field(None, alias="_createdTs", description="Unix timestamp (optional)")
    
    def to_elasticsearch_doc(self) -> Dict[str, Any]:
        """
        Convert the article model to an Elasticsearch document format.
        
        Returns:
            Dict[str, Any]: Document ready for Elasticsearch indexing
        """
        doc = self.model_dump()
        
        # Add computed fields for Elasticsearch (with safe defaults)
        likes_count = self.likes or 0
        dislikes_count = self.dislikes or 0
        views = self.views or 0
        content = self.content or ""
        summary = self.summary or ""
        title = self.title or ""
        
        doc['engagement_ratio'] = likes_count / max(likes_count + dislikes_count, 1)
        doc['content_length'] = len(content)
        doc['summary_length'] = len(summary)
        doc['tag_count'] = len(self.tags)
        doc['is_published'] = self.status == "published"
        
        # Calculate reading_time_minutes (consistent with pipeline)
        doc['reading_time_minutes'] = max(1, round(doc['content_length'] / 200.0))
        
        # Calculate popularity_score (consistent with pipeline)
        doc['popularity_score'] = views * 0.1 + likes_count * 2 - dislikes_count * 0.5
        
        # Add search-friendly fields
        searchable_parts = [title, summary, content] + self.tags
        doc['searchable_content'] = " ".join(filter(None, searchable_parts))
        
        return doc


class BlogData(BaseModel):
    """
    Container model for the entire blog dataset.
    
    This model represents the complete structure of the generated.json file
    with simplified validation.
    """
    
    Users: List[User] = Field(default_factory=list, description="List of all users")
    Articles: List[Article] = Field(default_factory=list, description="List of all articles")
    
    
    