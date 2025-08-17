"""
Database Models - نماذج قاعدة البيانات المتطورة
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Float, 
    ForeignKey, Index, UniqueConstraint, CheckConstraint, BigInteger
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Mapped
from sqlalchemy.dialects.postgresql import UUID, JSONB

Base = declarative_base()


class User(Base):
    """نموذج المستخدم"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=True, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    
    # إعدادات المستخدم
    language = Column(String(10), default="ar")
    timezone = Column(String(50), default="Asia/Riyadh")
    max_file_size_gb = Column(Float, default=2.0)
    preferred_quality = Column(String(20), default="720")
    
    # حالة المستخدم
    is_active = Column(Boolean, default=True)
    is_premium = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    
    # إحصائيات
    total_downloads = Column(Integer, default=0)
    total_uploads = Column(Integer, default=0)
    total_size_bytes = Column(BigInteger, default=0)
    
    # التواريخ
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_seen = Column(DateTime(timezone=True), nullable=True)
    
    # العلاقات
    downloads: Mapped[List["Download"]] = relationship("Download", back_populates="user")
    uploads: Mapped[List["Upload"]] = relationship("Upload", back_populates="user")
    
    # الفهارس
    __table_args__ = (
        Index("idx_user_telegram_id", "telegram_id"),
        Index("idx_user_username", "username"),
        Index("idx_user_created_at", "created_at"),
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"


class Download(Base):
    """نموذج التحميل"""
    __tablename__ = "downloads"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # معلومات الفيديو
    video_url = Column(Text, nullable=False)
    video_id = Column(String(50), nullable=True, index=True)
    title = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    duration = Column(Integer, nullable=True)  # بالثواني
    thumbnail_url = Column(Text, nullable=True)
    
    # إعدادات التحميل
    quality = Column(String(20), default="720")
    format = Column(String(20), default="mp4")
    audio_only = Column(Boolean, default=False)
    
    # حالة التحميل
    status = Column(String(20), default="pending")  # pending, downloading, completed, failed
    progress = Column(Float, default=0.0)  # 0.0 إلى 100.0
    file_size = Column(BigInteger, nullable=True)
    downloaded_size = Column(BigInteger, default=0)
    
    # معلومات الملف
    file_path = Column(Text, nullable=True)
    file_name = Column(Text, nullable=True)
    mime_type = Column(String(100), nullable=True)
    
    # الأخطاء
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    
    # التواريخ
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # العلاقات
    user: Mapped["User"] = relationship("User", back_populates="downloads")
    upload: Mapped[Optional["Upload"]] = relationship("Upload", back_populates="download", uselist=False)
    
    # الفهارس
    __table_args__ = (
        Index("idx_download_user_id", "user_id"),
        Index("idx_download_status", "status"),
        Index("idx_download_created_at", "created_at"),
        Index("idx_download_video_id", "video_id"),
    )
    
    def __repr__(self):
        return f"<Download(id={self.id}, video_url={self.video_url}, status={self.status})>"


class Upload(Base):
    """نموذج الرفع"""
    __tablename__ = "uploads"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    download_id = Column(UUID(as_uuid=True), ForeignKey("downloads.id"), nullable=True)
    
    # معلومات الملف
    file_path = Column(Text, nullable=False)
    file_name = Column(Text, nullable=False)
    file_size = Column(BigInteger, nullable=False)
    mime_type = Column(String(100), nullable=True)
    
    # معلومات تلجرام
    telegram_file_id = Column(String(255), nullable=True)
    telegram_message_id = Column(BigInteger, nullable=True)
    telegram_chat_id = Column(BigInteger, nullable=True)
    
    # إعدادات الرفع
    caption = Column(Text, nullable=True)
    thumbnail_path = Column(Text, nullable=True)
    compression_enabled = Column(Boolean, default=True)
    encryption_enabled = Column(Boolean, default=True)
    
    # حالة الرفع
    status = Column(String(20), default="pending")  # pending, uploading, completed, failed
    progress = Column(Float, default=0.0)  # 0.0 إلى 100.0
    uploaded_size = Column(BigInteger, default=0)
    
    # الأخطاء
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    
    # التواريخ
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # العلاقات
    user: Mapped["User"] = relationship("User", back_populates="uploads")
    download: Mapped[Optional["Download"]] = relationship("Download", back_populates="upload")
    
    # الفهارس
    __table_args__ = (
        Index("idx_upload_user_id", "user_id"),
        Index("idx_upload_status", "status"),
        Index("idx_upload_created_at", "created_at"),
        Index("idx_upload_download_id", "download_id"),
    )
    
    def __repr__(self):
        return f"<Upload(id={self.id}, file_name={self.file_name}, status={self.status})>"


class Statistics(Base):
    """نموذج الإحصائيات"""
    __tablename__ = "statistics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # إحصائيات المستخدمين
    total_users = Column(Integer, default=0)
    active_users = Column(Integer, default=0)
    new_users = Column(Integer, default=0)
    
    # إحصائيات التحميل
    total_downloads = Column(Integer, default=0)
    successful_downloads = Column(Integer, default=0)
    failed_downloads = Column(Integer, default=0)
    total_download_size = Column(BigInteger, default=0)
    
    # إحصائيات الرفع
    total_uploads = Column(Integer, default=0)
    successful_uploads = Column(Integer, default=0)
    failed_uploads = Column(Integer, default=0)
    total_upload_size = Column(BigInteger, default=0)
    
    # إحصائيات الأداء
    avg_download_time = Column(Float, default=0.0)  # بالثواني
    avg_upload_time = Column(Float, default=0.0)  # بالثواني
    peak_concurrent_users = Column(Integer, default=0)
    
    # إحصائيات النظام
    cpu_usage = Column(Float, default=0.0)
    memory_usage = Column(Float, default=0.0)
    disk_usage = Column(Float, default=0.0)
    network_usage = Column(Float, default=0.0)
    
    # بيانات إضافية
    extra_data = Column(JSONB, nullable=True)
    
    # التواريخ
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # الفهارس
    __table_args__ = (
        Index("idx_statistics_date", "date"),
        UniqueConstraint("date", name="uq_statistics_date"),
    )
    
    def __repr__(self):
        return f"<Statistics(id={self.id}, date={self.date})>"


class SystemLog(Base):
    """نموذج سجلات النظام"""
    __tablename__ = "system_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # معلومات السجل
    level = Column(String(20), nullable=False, index=True)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    module = Column(String(100), nullable=False, index=True)
    message = Column(Text, nullable=False)
    
    # معلومات السياق
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    download_id = Column(UUID(as_uuid=True), ForeignKey("downloads.id"), nullable=True)
    upload_id = Column(UUID(as_uuid=True), ForeignKey("uploads.id"), nullable=True)
    
    # معلومات إضافية
    exception = Column(Text, nullable=True)
    stack_trace = Column(Text, nullable=True)
    extra_data = Column(JSONB, nullable=True)
    
    # التواريخ
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    
    # الفهارس
    __table_args__ = (
        Index("idx_system_log_level", "level"),
        Index("idx_system_log_module", "module"),
        Index("idx_system_log_created_at", "created_at"),
        Index("idx_system_log_user_id", "user_id"),
    )
    
    def __repr__(self):
        return f"<SystemLog(id={self.id}, level={self.level}, module={self.module})>"


# إضافة الفهارس والقيود
class CacheEntry(Base):
    """نموذج التخزين المؤقت"""
    __tablename__ = "cache_entries"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String(255), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)
    ttl = Column(DateTime(timezone=True), nullable=False, index=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index("idx_cache_key", "key"),
        Index("idx_cache_ttl", "ttl"),
    )
    
    def __repr__(self):
        return f"<CacheEntry(id={self.id}, key={self.key})>"


# إضافة القيود
__all__ = [
    "Base",
    "User", 
    "Download",
    "Upload", 
    "Statistics",
    "SystemLog",
    "CacheEntry"
]