"""
Database models for the video downloader bot
Defines all database tables and relationships using SQLAlchemy
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column, Integer, String, BigInteger, DateTime, Boolean, 
    Text, Float, JSON, Index, ForeignKey
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()

class User(Base):
    """User model for storing user information and statistics"""
    __tablename__ = 'users'
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Telegram user information
    user_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    
    # Chat information
    chat_id = Column(BigInteger, nullable=True)
    
    # User settings (stored as JSON)
    settings = Column(JSON, default=lambda: {
        'default_quality': 'best',
        'default_format': 'mp4',
        'progress_notifications': True,
        'completion_notifications': True,
        'error_notifications': True,
        'auto_cleanup': True,
        'fast_mode': True,
        'generate_thumbnails': True
    })
    
    # Statistics
    total_downloads = Column(Integer, default=0)
    successful_downloads = Column(Integer, default=0)
    failed_downloads = Column(Integer, default=0)
    total_bytes_downloaded = Column(BigInteger, default=0)
    total_bytes_uploaded = Column(BigInteger, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    last_active = Column(DateTime(timezone=True), default=func.now())
    
    # Premium features
    is_premium = Column(Boolean, default=False)
    premium_expires = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    downloads = relationship("Download", back_populates="user", cascade="all, delete-orphan")
    user_analytics = relationship("UserAnalytics", back_populates="user", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_users_user_id', 'user_id'),
        Index('idx_users_username', 'username'),
        Index('idx_users_created_at', 'created_at'),
        Index('idx_users_last_active', 'last_active'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'chat_id': self.chat_id,
            'settings': self.settings,
            'total_downloads': self.total_downloads,
            'successful_downloads': self.successful_downloads,
            'failed_downloads': self.failed_downloads,
            'total_bytes_downloaded': self.total_bytes_downloaded,
            'total_bytes_uploaded': self.total_bytes_uploaded,
            'created_at': self.created_at.isoformat() if self.created_at is not None else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at is not None else None,
            'last_active': self.last_active.isoformat() if self.last_active is not None else None,
            'is_premium': self.is_premium,
            'premium_expires': self.premium_expires.isoformat() if self.premium_expires is not None else None
        }
    
    @property
    def success_rate(self) -> float:
        """Calculate user's download success rate"""
        if not self.total_downloads or self.total_downloads == 0:
            return 0.0
        return float((self.successful_downloads / self.total_downloads) * 100)

class Download(Base):
    """Download model for tracking individual downloads"""
    __tablename__ = 'downloads'
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Task tracking
    task_id = Column(String(255), unique=True, nullable=False, index=True)
    
    # User relationship
    user_id = Column(BigInteger, ForeignKey('users.user_id'), nullable=False, index=True)
    
    # Video information
    original_url = Column(Text, nullable=False)
    video_title = Column(Text, nullable=True)
    video_id = Column(String(255), nullable=True)
    platform = Column(String(100), nullable=True, index=True)
    uploader = Column(String(255), nullable=True)
    duration = Column(Integer, nullable=True)  # in seconds
    view_count = Column(BigInteger, nullable=True)
    upload_date = Column(String(20), nullable=True)
    
    # Download details
    format_id = Column(String(100), nullable=True)
    quality = Column(String(50), nullable=True)
    file_extension = Column(String(10), nullable=True)
    file_size = Column(BigInteger, nullable=True)
    is_audio_only = Column(Boolean, default=False)
    
    # Performance metrics
    download_time = Column(Float, nullable=True)  # in seconds
    upload_time = Column(Float, nullable=True)    # in seconds
    download_speed = Column(Float, nullable=True) # bytes per second
    upload_speed = Column(Float, nullable=True)   # bytes per second
    
    # Status and result
    status = Column(String(50), default='pending', index=True)  # pending, downloading, uploading, completed, failed, cancelled
    error_message = Column(Text, nullable=True)
    
    # Telegram upload info
    telegram_message_id = Column(BigInteger, nullable=True)
    telegram_chat_id = Column(BigInteger, nullable=True)
    
    # Additional video metadata (stored as JSON)
    video_metadata = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="downloads")
    
    # Indexes
    __table_args__ = (
        Index('idx_downloads_user_downloads', 'user_id', 'created_at'),
        Index('idx_downloads_platform_status', 'platform', 'status'),
        Index('idx_downloads_created_at', 'created_at'),
        Index('idx_downloads_status', 'status'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert download to dictionary"""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'user_id': self.user_id,
            'original_url': self.original_url,
            'video_title': self.video_title,
            'video_id': self.video_id,
            'platform': self.platform,
            'uploader': self.uploader,
            'duration': self.duration,
            'view_count': self.view_count,
            'upload_date': self.upload_date,
            'format_id': self.format_id,
            'quality': self.quality,
            'file_extension': self.file_extension,
            'file_size': self.file_size,
            'is_audio_only': self.is_audio_only,
            'download_time': self.download_time,
            'upload_time': self.upload_time,
            'download_speed': self.download_speed,
            'upload_speed': self.upload_speed,
            'status': self.status,
            'error_message': self.error_message,
            'telegram_message_id': self.telegram_message_id,
            'telegram_chat_id': self.telegram_chat_id,
            'video_metadata': self.video_metadata,
            'created_at': self.created_at.isoformat() if self.created_at is not None else None,
            'started_at': self.started_at.isoformat() if self.started_at is not None else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at is not None else None
        }

class UserAnalytics(Base):
    """User analytics model for detailed usage tracking"""
    __tablename__ = 'user_analytics'
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # User relationship
    user_id = Column(BigInteger, ForeignKey('users.user_id'), nullable=False, index=True)
    
    # Date for daily analytics
    date = Column(DateTime(timezone=True), default=func.now(), index=True)
    
    # Daily statistics
    downloads_count = Column(Integer, default=0)
    successful_downloads = Column(Integer, default=0)
    failed_downloads = Column(Integer, default=0)
    bytes_downloaded = Column(BigInteger, default=0)
    bytes_uploaded = Column(BigInteger, default=0)
    
    # Platform usage
    platform_stats = Column(JSON, default=dict)  # {"youtube": 5, "tiktok": 2, etc.}
    
    # Quality preferences
    quality_stats = Column(JSON, default=dict)   # {"1080p": 3, "720p": 4, etc.}
    
    # Performance metrics
    avg_download_speed = Column(Float, nullable=True)
    avg_upload_speed = Column(Float, nullable=True)
    avg_processing_time = Column(Float, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="user_analytics")
    
    # Indexes
    __table_args__ = (
        Index('idx_analytics_user_date', 'user_id', 'date'),
        Index('idx_analytics_date', 'date'),
    )

class SystemStats(Base):
    """System statistics model for monitoring bot performance"""
    __tablename__ = 'system_stats'
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Timestamp
    timestamp = Column(DateTime(timezone=True), default=func.now(), index=True)
    
    # System metrics
    cpu_usage = Column(Float, nullable=True)
    memory_usage = Column(Float, nullable=True)
    disk_usage = Column(Float, nullable=True)
    
    # Bot performance metrics
    active_users = Column(Integer, default=0)
    active_downloads = Column(Integer, default=0)
    active_uploads = Column(Integer, default=0)
    queue_size = Column(Integer, default=0)
    
    # Service health
    database_connected = Column(Boolean, default=True)
    redis_connected = Column(Boolean, default=True)
    telethon_connected = Column(Boolean, default=True)
    
    # Performance metrics
    avg_response_time = Column(Float, nullable=True)
    requests_per_minute = Column(Float, nullable=True)
    error_rate = Column(Float, nullable=True)
    
    # Additional metrics (stored as JSON)
    custom_metrics = Column(JSON, nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_system_stats_timestamp', 'timestamp'),
    )

class Platform(Base):
    """Platform model for tracking supported platforms and their statistics"""
    __tablename__ = 'platforms'
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Platform information
    name = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(100), nullable=False)
    base_url = Column(String(255), nullable=True)
    
    # Platform statistics
    total_downloads = Column(BigInteger, default=0)
    successful_downloads = Column(BigInteger, default=0)
    failed_downloads = Column(BigInteger, default=0)
    
    # Platform capabilities
    supports_video = Column(Boolean, default=True)
    supports_audio = Column(Boolean, default=True)
    supports_playlists = Column(Boolean, default=False)
    max_quality = Column(String(50), nullable=True)
    
    # Platform-specific settings (stored as JSON)
    settings = Column(JSON, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    last_successful_download = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_platforms_name', 'name'),
        Index('idx_platforms_active', 'is_active'),
    )
    
    @property
    def success_rate(self) -> float:
        """Calculate platform's success rate"""
        if not self.total_downloads or self.total_downloads == 0:
            return 0.0
        return float((self.successful_downloads / self.total_downloads) * 100)

class ErrorLog(Base):
    """Error log model for tracking and debugging errors"""
    __tablename__ = 'error_logs'
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Error information
    error_type = Column(String(100), nullable=False, index=True)
    error_message = Column(Text, nullable=False)
    error_traceback = Column(Text, nullable=True)
    
    # Context information
    user_id = Column(BigInteger, nullable=True, index=True)
    url = Column(Text, nullable=True)
    platform = Column(String(100), nullable=True)
    task_id = Column(String(255), nullable=True)
    
    # Request context (stored as JSON)
    request_data = Column(JSON, nullable=True)
    
    # Error severity
    severity = Column(String(20), default='error', index=True)  # debug, info, warning, error, critical
    
    # Resolution status
    resolved = Column(Boolean, default=False, index=True)
    resolution_notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now(), index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_errors_type_created', 'error_type', 'created_at'),
        Index('idx_errors_user_errors', 'user_id', 'created_at'),
        Index('idx_errors_severity_resolved', 'severity', 'resolved'),
    )

# Create all indexes and constraints
def create_indexes(engine):
    """Create additional database indexes for performance"""
    # This function can be used to create additional indexes
    # that are not defined in the model classes
    pass
