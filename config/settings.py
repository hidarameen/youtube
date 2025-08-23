"""
Configuration settings for the video downloader bot
All settings loaded from environment variables with secure defaults
"""

import os
import logging
from typing import List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class Settings:
    """Bot configuration settings"""
    
    # Telegram Bot Configuration
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    API_ID: int = int(os.getenv("API_ID", "0"))
    API_HASH: str = os.getenv("API_HASH", "")
    
    # Telethon Session Configuration  
    SESSION_STRING: str = os.getenv("SESSION_STRING", "")
    PHONE_NUMBER: str = os.getenv("PHONE_NUMBER", "")
    
    # Group/Chat Configuration
    ALLOWED_CHAT_IDS: List[int] = field(default_factory=lambda: [
        int(x.strip()) for x in os.getenv("ALLOWED_CHAT_IDS", "").split(",") 
        if x.strip().lstrip('-').isdigit()
    ])
    UPLOAD_CHAT_ID: int = int(os.getenv("UPLOAD_CHAT_ID", "0"))
    
    # Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/video_bot")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Performance Settings
    MAX_CONCURRENT_DOWNLOADS: int = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "5"))
    MAX_CONCURRENT_UPLOADS: int = int(os.getenv("MAX_CONCURRENT_UPLOADS", "3"))
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "262144"))  # 256KB
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "2147483648"))  # 2GB
    
    # File Management
    TEMP_DIR: str = os.getenv("TEMP_DIR", "./temp")
    MAX_TEMP_AGE: int = int(os.getenv("MAX_TEMP_AGE", "3600"))  # 1 hour
    AUTO_CLEANUP: bool = os.getenv("AUTO_CLEANUP", "true").lower() == "true"
    
    # Speed Optimization
    USE_FAST_TELETHON: bool = os.getenv("USE_FAST_TELETHON", "true").lower() == "true"
    BANDWIDTH_LIMIT: int = int(os.getenv("BANDWIDTH_LIMIT", "25000000"))  # 25MB/s
    CONNECTION_RETRIES: int = int(os.getenv("CONNECTION_RETRIES", "5"))
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "300"))  # 5 minutes
    
    # Feature Flags
    ENABLE_ANALYTICS: bool = os.getenv("ENABLE_ANALYTICS", "true").lower() == "true"
    ENABLE_RATE_LIMITING: bool = os.getenv("ENABLE_RATE_LIMITING", "true").lower() == "true"
    ENABLE_USER_STATISTICS: bool = os.getenv("ENABLE_USER_STATISTICS", "true").lower() == "true"
    
    # Security Settings
    MAX_USERS_PER_MINUTE: int = int(os.getenv("MAX_USERS_PER_MINUTE", "100"))
    MAX_DOWNLOADS_PER_USER: int = int(os.getenv("MAX_DOWNLOADS_PER_USER", "10"))
    ADMIN_USER_IDS: List[int] = field(default_factory=lambda: [
        int(x.strip()) for x in os.getenv("ADMIN_USER_IDS", "").split(",") 
        if x.strip().lstrip('-').isdigit()
    ])
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "./logs/bot.log")
    
    # YT-DLP Configuration
    YTDL_FORMAT: str = os.getenv("YTDL_FORMAT", "best")
    YTDL_EXTRACTORS: List[str] = field(default_factory=lambda: [
        "youtube", "facebook", "instagram", "tiktok", "twitter", 
        "generic", "dailymotion", "vimeo", "twitch"
    ])
    
    def validate(self) -> bool:
        """Validate critical configuration settings"""
        errors = []
        
        if not self.BOT_TOKEN:
            errors.append("BOT_TOKEN is required")
        
        if not self.API_ID or self.API_ID == 0:
            errors.append("API_ID is required")
            
        if not self.API_HASH:
            errors.append("API_HASH is required")
            
        if not self.ALLOWED_CHAT_IDS:
            errors.append("ALLOWED_CHAT_IDS is required")
            
        if not self.UPLOAD_CHAT_ID:
            errors.append("UPLOAD_CHAT_ID is required")
        
        if errors:
            for error in errors:
                logger.error(f"Configuration error: {error}")
            return False
        
        logger.info("✅ Configuration validation passed")
        return True
    
    def get_ytdl_opts(self) -> dict:
        """Get optimized yt-dlp options"""
        return {
            'format': 'best[height<=1080]/best',
            'noplaylist': True,
            'extract_flat': False,
            'writethumbnail': True,
            'writeinfojson': True,
            'ignoreerrors': True,
            'no_warnings': False,
            'retries': 3,
            'fragment_retries': 3,
            'socket_timeout': 30,
            'prefer_free_formats': True,
            'merge_output_format': 'mp4',
            'concurrent_fragments': 5,
            'http_chunk_size': self.CHUNK_SIZE,
            'outtmpl': f"{self.TEMP_DIR}/%(title)s.%(ext)s",
            'restrictfilenames': True,
            'windowsfilenames': True,
        }
    
    def __post_init__(self):
        """Post-initialization setup"""
        # Create temp directory if it doesn't exist
        os.makedirs(self.TEMP_DIR, exist_ok=True)
        os.makedirs(os.path.dirname(self.LOG_FILE), exist_ok=True)

# Global settings instance
settings = Settings()
