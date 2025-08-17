"""
Configuration Module - إدارة الإعدادات المتقدمة
"""

import os
import json
from pathlib import Path
from typing import Dict, Any
from dataclasses import dataclass, field
from dotenv import load_dotenv

# تحميل متغيرات البيئة
load_dotenv()


@dataclass
class DatabaseConfig:
    """إعدادات قاعدة البيانات"""
    url: str = "postgresql://user:password@localhost:5432/youtube_bot"
    pool_size: int = 20
    max_overflow: int = 30
    pool_timeout: int = 30
    pool_recycle: int = 3600


@dataclass
class RedisConfig:
    """إعدادات Redis"""
    url: str = "redis://localhost:6379"
    max_connections: int = 50
    decode_responses: bool = True
    socket_timeout: int = 5


@dataclass
class TelegramConfig:
    """إعدادات تلجرام"""
    api_id: int = 0
    api_hash: str = ""
    bot_token: str = ""
    session_name: str = "userbot"
    max_file_size_gb: float = 2.0

    @property
    def max_file_size_bytes(self) -> int:
        """تحويل الحجم إلى بايت"""
        return int(self.max_file_size_gb * 1024 * 1024 * 1024)


@dataclass
class DownloadConfig:
    """إعدادات التحميل"""
    download_dir: Path = Path("downloads")
    temp_dir: Path = Path("temp")
    max_concurrent_downloads: int = 5
    chunk_size: int = 1024 * 1024  # 1MB
    retry_attempts: int = 3
    timeout: int = 300
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


@dataclass
class UploadConfig:
    """إعدادات الرفع"""
    max_concurrent_uploads: int = 3
    chunk_size: int = 512 * 1024  # 512KB
    retry_attempts: int = 5
    timeout: int = 600
    compression_enabled: bool = True
    encryption_enabled: bool = True


@dataclass
class WebConfig:
    """إعدادات الويب"""
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    secret_key: str = "your-secret-key-here"
    cors_origins: list = field(default_factory=lambda: ["*"])
    rate_limit: int = 100  # requests per minute


@dataclass
class LoggingConfig:
    """إعدادات السجلات"""
    level: str = "INFO"
    format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    file: Path = Path("logs/app.log")
    max_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5


@dataclass
class CacheConfig:
    """إعدادات التخزين المؤقت"""
    enabled: bool = True
    ttl: int = 3600  # 1 hour
    max_size: int = 1000
    cache_dir: Path = Path("cache")


@dataclass
class SecurityConfig:
    """إعدادات الأمان"""
    encryption_key: str = ""
    jwt_secret: str = ""
    bcrypt_rounds: int = 12
    session_timeout: int = 3600  # 1 hour
    max_login_attempts: int = 5


@dataclass
class Config:
    """الإعدادات الرئيسية (dataclass)"""

    # إعدادات التطبيق
    app_name: str = "YouTube Telegram Bot"
    app_version: str = "2.0.0"
    environment: str = "development"

    # إعدادات قاعدة البيانات
    database: DatabaseConfig = field(default_factory=DatabaseConfig)

    # إعدادات Redis
    redis: RedisConfig = field(default_factory=RedisConfig)

    # إعدادات تلجرام
    telegram: TelegramConfig = field(default_factory=TelegramConfig)

    # إعدادات التحميل
    download: DownloadConfig = field(default_factory=DownloadConfig)

    # إعدادات الرفع
    upload: UploadConfig = field(default_factory=UploadConfig)

    # إعدادات الويب
    web: WebConfig = field(default_factory=WebConfig)

    # إعدادات السجلات
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    # إعدادات التخزين المؤقت
    cache: CacheConfig = field(default_factory=CacheConfig)

    # إعدادات الأمان
    security: SecurityConfig = field(default_factory=SecurityConfig)

    def load_from_env(self) -> None:
        """تحميل الإعدادات من متغيرات البيئة"""
        self.telegram.api_id = int(os.getenv("API_ID", str(self.telegram.api_id) or "0") or 0)
        self.telegram.api_hash = os.getenv("API_HASH", self.telegram.api_hash)
        self.telegram.bot_token = os.getenv("BOT_TOKEN", self.telegram.bot_token)
        self.telegram.session_name = os.getenv("SESSION_NAME", self.telegram.session_name)
        try:
            self.telegram.max_file_size_gb = float(os.getenv("MAX_FILE_SIZE_GB", str(self.telegram.max_file_size_gb)))
        except Exception:
            pass

        self.database.url = os.getenv("DATABASE_URL", self.database.url)
        self.redis.url = os.getenv("REDIS_URL", self.redis.url)

        self.web.host = os.getenv("WEB_HOST", self.web.host)
        try:
            self.web.port = int(os.getenv("WEB_PORT", str(self.web.port)))
        except Exception:
            pass
        self.web.secret_key = os.getenv("SECRET_KEY", self.web.secret_key)

        self.security.encryption_key = os.getenv("ENCRYPTION_KEY", self.security.encryption_key)
        self.security.jwt_secret = os.getenv("JWT_SECRET", self.security.jwt_secret)

    def create_directories(self) -> None:
        """إنشاء المجلدات المطلوبة"""
        directories = [
            self.download.download_dir,
            self.download.temp_dir,
            self.logging.file.parent,
            self.cache.cache_dir,
            Path("logs"),
            Path("temp"),
            Path("cache"),
            Path("downloads"),
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> Dict[str, Any]:
        """تحويل الإعدادات إلى قاموس"""
        return {
            "app_name": self.app_name,
            "app_version": self.app_version,
            "environment": self.environment,
            "telegram": {
                "api_id": self.telegram.api_id,
                "api_hash": self.telegram.api_hash,
                "session_name": self.telegram.session_name,
                "max_file_size_gb": self.telegram.max_file_size_gb,
            },
            "database": {
                "url": self.database.url,
                "pool_size": self.database.pool_size,
            },
            "redis": {
                "url": self.redis.url,
                "max_connections": self.redis.max_connections,
            },
            "web": {
                "host": self.web.host,
                "port": self.web.port,
                "debug": self.web.debug,
            },
        }

    def save_to_file(self, file_path: Path) -> None:
        """حفظ الإعدادات إلى ملف"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


# إنشاء نسخة عامة من الإعدادات
config = Config()
config.load_from_env()
config.create_directories()