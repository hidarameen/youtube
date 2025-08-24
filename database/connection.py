"""
Database connection manager for PostgreSQL
Handles connection pooling, migrations, and database operations
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.sql import text
from sqlalchemy import func

from config.settings import settings
from database.models import Base, User, Download, UserAnalytics, SystemStats, Platform, ErrorLog

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Ultra high-performance database manager with connection pooling"""
    
    def __init__(self):
        self.engine: Optional[any] = None
        self.session_factory: Optional[async_sessionmaker] = None
        self.connection_pool: Optional[asyncpg.Pool] = None
        self.is_initialized = False
        
        # Connection pool settings
        self.min_connections = 5
        self.max_connections = 20
        self.pool_timeout = 30
        
    async def initialize(self):
        """Initialize database connections and create tables"""
        try:
            logger.info("🔧 Initializing database connections...")
            
            # Create async engine with optimized settings
            # Remove any SSL parameters that might conflict
            db_url = settings.DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://')
            if '?sslmode=' in db_url:
                db_url = db_url.split('?sslmode=')[0]
            
            self.engine = create_async_engine(
                db_url,
                pool_size=self.min_connections,
                max_overflow=self.max_connections - self.min_connections,
                pool_timeout=self.pool_timeout,
                pool_pre_ping=True,
                pool_recycle=3600,  # Recycle connections every hour
                echo=False,  # Set to True for SQL debugging
            )
            
            # Create session factory
            self.session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Create raw connection pool for direct queries
            await self._create_connection_pool()
            
            # Create tables if they don't exist
            await self._create_tables()
            
            # Mark as initialized before calling methods that use get_session()
            self.is_initialized = True
            
            # Initialize default data
            await self._initialize_default_data()
            
            logger.info("✅ Database initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}", exc_info=True)
            raise
    
    async def _create_connection_pool(self):
        """Create asyncpg connection pool for raw queries"""
        try:
            # Use direct database URL with asyncpg (it handles SSL automatically)
            # Remove sslmode parameter if present to avoid conflicts
            db_url = settings.DATABASE_URL
            if '?sslmode=' in db_url:
                db_url = db_url.split('?sslmode=')[0]
            
            self.connection_pool = await asyncpg.create_pool(
                dsn=db_url,
                min_size=self.min_connections,
                max_size=self.max_connections,
                command_timeout=60,
                server_settings={
                    'jit': 'off',  # Disable JIT for better performance on small queries
                }
            )
            
            logger.info("✅ AsyncPG connection pool created")
            
        except Exception as e:
            logger.error(f"❌ Failed to create connection pool: {e}")
            raise
    
    async def _create_tables(self):
        """Create database tables if they don't exist"""
        try:
            if self.engine is None:
                raise RuntimeError("Database engine not initialized")
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            logger.info("✅ Database tables created/verified")
            
        except Exception as e:
            logger.error(f"❌ Failed to create tables: {e}")
            raise
    
    async def _initialize_default_data(self):
        """Initialize default platform data"""
        try:
            async with self.get_session() as session:
                # Check if platforms already exist
                result = await session.execute(text("SELECT COUNT(*) FROM platforms"))
                count = result.scalar()
                
                if count == 0:
                    # Insert default platforms
                    default_platforms = [
                        {
                            'name': 'youtube',
                            'display_name': 'YouTube',
                            'base_url': 'https://www.youtube.com',
                            'supports_video': True,
                            'supports_audio': True,
                            'supports_playlists': True,
                            'max_quality': '4K'
                        },
                        {
                            'name': 'tiktok',
                            'display_name': 'TikTok',
                            'base_url': 'https://www.tiktok.com',
                            'supports_video': True,
                            'supports_audio': True,
                            'supports_playlists': False,
                            'max_quality': '1080p'
                        },
                        {
                            'name': 'instagram',
                            'display_name': 'Instagram',
                            'base_url': 'https://www.instagram.com',
                            'supports_video': True,
                            'supports_audio': True,
                            'supports_playlists': False,
                            'max_quality': '1080p'
                        },
                        {
                            'name': 'facebook',
                            'display_name': 'Facebook',
                            'base_url': 'https://www.facebook.com',
                            'supports_video': True,
                            'supports_audio': True,
                            'supports_playlists': False,
                            'max_quality': '1080p'
                        },
                        {
                            'name': 'twitter',
                            'display_name': 'Twitter/X',
                            'base_url': 'https://twitter.com',
                            'supports_video': True,
                            'supports_audio': True,
                            'supports_playlists': False,
                            'max_quality': '1080p'
                        }
                    ]
                    
                    for platform_data in default_platforms:
                        platform = Platform(**platform_data)
                        session.add(platform)
                    
                    await session.commit()
                    logger.info("✅ Default platforms initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize default data: {e}")
    
    @asynccontextmanager
    async def get_session(self):
        """Get database session with automatic cleanup"""
        if not self.is_initialized or self.session_factory is None:
            raise RuntimeError("Database not initialized")
        
        async with self.session_factory() as session:
            try:
                yield session
            except Exception as e:
                await session.rollback()
                logger.error(f"Database session error: {e}")
                raise
            finally:
                await session.close()
    
    async def create_or_update_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        chat_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create or update user in database"""
        try:
            async with self.get_session() as session:
                # Try to get existing user
                result = await session.execute(
                    text("SELECT * FROM users WHERE user_id = :user_id"),
                    {"user_id": user_id}
                )
                user_data = result.fetchone()
                
                if user_data:
                    # Update existing user
                    await session.execute(
                        text("""
                            UPDATE users 
                            SET username = :username, first_name = :first_name, 
                                last_name = :last_name, chat_id = :chat_id, 
                                last_active = :now, updated_at = :now
                            WHERE user_id = :user_id
                        """),
                        {
                            "user_id": user_id,
                            "username": username,
                            "first_name": first_name,
                            "last_name": last_name,
                            "chat_id": chat_id,
                            "now": datetime.utcnow()
                        }
                    )
                    
                    # Fetch updated user
                    result = await session.execute(
                        text("SELECT * FROM users WHERE user_id = :user_id"),
                        {"user_id": user_id}
                    )
                    user_data = result.fetchone()
                else:
                    # Create new user
                    await session.execute(
                        text("""
                            INSERT INTO users (user_id, username, first_name, last_name, chat_id, created_at, last_active)
                            VALUES (:user_id, :username, :first_name, :last_name, :chat_id, :now, :now)
                        """),
                        {
                            "user_id": user_id,
                            "username": username,
                            "first_name": first_name,
                            "last_name": last_name,
                            "chat_id": chat_id,
                            "now": datetime.utcnow()
                        }
                    )
                    
                    # Fetch created user
                    result = await session.execute(
                        text("SELECT * FROM users WHERE user_id = :user_id"),
                        {"user_id": user_id}
                    )
                    user_data = result.fetchone()
                
                await session.commit()
                
                # Convert asyncpg Row to dict properly
                if user_data:
                    return {
                        'id': user_data[0] if len(user_data) > 0 else None,
                        'user_id': user_data[1] if len(user_data) > 1 else None,
                        'username': user_data[2] if len(user_data) > 2 else None,
                        'first_name': user_data[3] if len(user_data) > 3 else None,
                        'last_name': user_data[4] if len(user_data) > 4 else None,
                        'chat_id': user_data[5] if len(user_data) > 5 else None,
                        'settings': user_data[6] if len(user_data) > 6 else {},
                        'total_downloads': user_data[7] if len(user_data) > 7 else 0,
                        'successful_downloads': user_data[8] if len(user_data) > 8 else 0,
                        'failed_downloads': user_data[9] if len(user_data) > 9 else 0,
                        'total_bytes_downloaded': user_data[10] if len(user_data) > 10 else 0,
                        'total_bytes_uploaded': user_data[11] if len(user_data) > 11 else 0,
                        'created_at': user_data[12] if len(user_data) > 12 else None,
                        'updated_at': user_data[13] if len(user_data) > 13 else None,
                        'last_active': user_data[14] if len(user_data) > 14 else None,
                        'is_premium': user_data[15] if len(user_data) > 15 else False,
                        'premium_expires': user_data[16] if len(user_data) > 16 else None
                    }
                else:
                    return {}
                
        except Exception as e:
            logger.error(f"❌ Failed to create/update user {user_id}: {e}")
            raise
    
    async def create_download_record(
        self,
        task_id: str,
        user_id: int,
        original_url: str,
        video_info: Dict[str, Any],
        format_info: Dict[str, Any]
    ) -> int:
        """Create download record in database"""
        try:
            async with self.get_session() as session:
                download_data = {
                    "task_id": task_id,
                    "user_id": user_id,
                    "original_url": original_url,
                    "video_title": video_info.get('title'),
                    "video_id": video_info.get('id'),
                    "platform": video_info.get('platform'),
                    "uploader": video_info.get('uploader'),
                    "duration": video_info.get('duration'),
                    "view_count": video_info.get('view_count'),
                    "upload_date": video_info.get('upload_date'),
                    "format_id": format_info.get('format_id'),
                    "quality": format_info.get('quality'),
                    "file_extension": format_info.get('ext'),
                    "file_size": format_info.get('file_size'),
                    "is_audio_only": format_info.get('ext') == 'mp3',
                    "status": 'pending',
                    "video_metadata": {
                        "video_info": video_info,
                        "format_info": format_info
                    },
                    "created_at": datetime.utcnow()
                }
                
                result = await session.execute(
                    text("""
                        INSERT INTO downloads 
                        (task_id, user_id, original_url, video_title, video_id, platform, uploader, 
                         duration, view_count, upload_date, format_id, quality, file_extension, 
                         file_size, is_audio_only, status, video_metadata, created_at)
                        VALUES 
                        (:task_id, :user_id, :original_url, :video_title, :video_id, :platform, 
                         :uploader, :duration, :view_count, :upload_date, :format_id, :quality, 
                         :file_extension, :file_size, :is_audio_only, :status, :video_metadata, :created_at)
                        RETURNING id
                    """),
                    download_data
                )
                
                download_id = result.scalar()
                await session.commit()
                
                logger.info(f"✅ Created download record {download_id} for task {task_id}")
                return int(download_id) if download_id else 0
                
        except Exception as e:
            logger.error(f"❌ Failed to create download record: {e}")
            raise
    
    async def update_download_progress(
        self,
        task_id: str,
        status: str,
        download_time: Optional[float] = None,
        upload_time: Optional[float] = None,
        download_speed: Optional[float] = None,
        upload_speed: Optional[float] = None,
        error_message: Optional[str] = None,
        telegram_message_id: Optional[int] = None,
        telegram_chat_id: Optional[int] = None
    ):
        """Update download progress in database"""
        try:
            async with self.get_session() as session:
                update_data = {
                    "task_id": task_id,
                    "status": status,
                    "updated_at": datetime.utcnow()
                }
                
                # Add optional fields if provided
                if download_time is not None:
                    update_data["download_time"] = download_time
                if upload_time is not None:
                    update_data["upload_time"] = upload_time
                if download_speed is not None:
                    update_data["download_speed"] = download_speed
                if upload_speed is not None:
                    update_data["upload_speed"] = upload_speed
                if error_message is not None:
                    update_data["error_message"] = error_message
                if telegram_message_id is not None:
                    update_data["telegram_message_id"] = telegram_message_id
                if telegram_chat_id is not None:
                    update_data["telegram_chat_id"] = telegram_chat_id
                
                # Set completion timestamp for final statuses
                if status in ['completed', 'failed', 'cancelled']:
                    update_data["completed_at"] = datetime.utcnow()
                elif status == 'downloading':
                    update_data["started_at"] = datetime.utcnow()
                
                # Build dynamic update query
                set_clauses = []
                for key in update_data.keys():
                    if key != "task_id":
                        set_clauses.append(f"{key} = :{key}")
                
                query = f"""
                    UPDATE downloads 
                    SET {', '.join(set_clauses)}
                    WHERE task_id = :task_id
                """
                
                await session.execute(text(query), update_data)
                await session.commit()
                
        except Exception as e:
            logger.error(f"❌ Failed to update download progress for {task_id}: {e}")
    
    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get comprehensive user statistics"""
        try:
            if self.connection_pool is None:
                raise RuntimeError("Connection pool not initialized")
            async with self.connection_pool.acquire() as conn:
                # Get basic user stats
                user_stats = await conn.fetchrow("""
                    SELECT 
                        total_downloads, successful_downloads, failed_downloads,
                        total_bytes_downloaded, total_bytes_uploaded, created_at, last_active
                    FROM users 
                    WHERE user_id = $1
                """, user_id)
                
                if not user_stats:
                    return {}
                
                # Get advanced statistics
                advanced_stats = await conn.fetchrow("""
                    SELECT 
                        AVG(download_speed) as avg_download_speed,
                        AVG(upload_speed) as avg_upload_speed,
                        MAX(download_speed) as fastest_download_speed,
                        AVG(download_time + upload_time) as avg_processing_time,
                        SUM(download_time) as total_download_time,
                        SUM(upload_time) as total_upload_time,
                        AVG(file_size) as avg_file_size
                    FROM downloads 
                    WHERE user_id = $1 AND status = 'completed'
                """, user_id)
                
                # Calculate success rate (handle null values)
                success_rate = 0
                total_downloads = user_stats['total_downloads'] or 0
                successful_downloads = user_stats['successful_downloads'] or 0
                
                if total_downloads > 0:
                    success_rate = (successful_downloads / total_downloads) * 100
                
                # Combine all stats (handle null values)
                stats = {}
                for key, value in dict(user_stats).items():
                    stats[key] = value if value is not None else 0
                
                # Add advanced stats with null handling
                if advanced_stats:
                    for key, value in dict(advanced_stats).items():
                        stats[key] = value if value is not None else 0
                else:
                    # Set default values for missing advanced stats
                    stats.update({
                        'avg_download_speed': 0,
                        'avg_upload_speed': 0, 
                        'fastest_download_speed': 0,
                        'avg_processing_time': 0,
                        'total_download_time': 0,
                        'total_upload_time': 0,
                        'avg_file_size': 0
                    })
                
                stats['success_rate'] = success_rate
                
                # Format timestamps
                if stats.get('created_at'):
                    stats['created_at'] = stats['created_at'].strftime('%B %d, %Y')
                if stats.get('last_active'):
                    stats['last_active'] = stats['last_active'].strftime('%B %d, %Y at %I:%M %p')
                
                return stats
                
        except Exception as e:
            logger.error(f"❌ Failed to get user stats for {user_id}: {e}")
            return {}
    
    async def get_user_settings(self, user_id: int) -> Dict[str, Any]:
        """Get user settings"""
        try:
            if self.connection_pool is None:
                raise RuntimeError("Connection pool not initialized")
            async with self.connection_pool.acquire() as conn:
                result = await conn.fetchrow(
                    "SELECT settings FROM users WHERE user_id = $1",
                    user_id
                )
                
                if result and result['settings']:
                    return result['settings']
                else:
                    # Return default settings
                    return {
                        'default_quality': 'best',
                        'default_format': 'mp4',
                        'progress_notifications': True,
                        'completion_notifications': True,
                        'error_notifications': True,
                        'auto_cleanup': True,
                        'fast_mode': True,
                        'generate_thumbnails': True
                    }
                    
        except Exception as e:
            logger.error(f"❌ Failed to get user settings for {user_id}: {e}")
            return {}
    
    async def update_user_settings(self, user_id: int, settings_update: Dict[str, Any]):
        """Update user settings"""
        try:
            if self.connection_pool is None:
                raise RuntimeError("Connection pool not initialized")
            async with self.connection_pool.acquire() as conn:
                # Get current settings
                current_settings = await self.get_user_settings(user_id)
                
                # Merge with updates
                current_settings.update(settings_update)
                
                # Update in database
                await conn.execute("""
                    UPDATE users 
                    SET settings = $1, updated_at = $2
                    WHERE user_id = $3
                """, current_settings, datetime.utcnow(), user_id)
                
                logger.info(f"✅ Updated settings for user {user_id}")
                
        except Exception as e:
            logger.error(f"❌ Failed to update user settings for {user_id}: {e}")
    
    async def get_global_stats(self) -> Dict[str, Any]:
        """Get global bot statistics"""
        try:
            if self.connection_pool is None:
                raise RuntimeError("Connection pool not initialized")
            async with self.connection_pool.acquire() as conn:
                # Get user statistics
                user_stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total_users,
                        COUNT(CASE WHEN last_active > NOW() - INTERVAL '1 day' THEN 1 END) as active_today,
                        COUNT(CASE WHEN created_at > NOW() - INTERVAL '1 day' THEN 1 END) as new_users_24h
                    FROM users
                """)
                
                # Get download statistics
                download_stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total_downloads,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_downloads,
                        COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_downloads,
                        SUM(CASE WHEN status = 'completed' THEN file_size ELSE 0 END) as total_data_processed,
                        SUM(CASE WHEN status = 'completed' AND created_at > NOW() - INTERVAL '1 day' THEN file_size ELSE 0 END) as data_today,
                        AVG(CASE WHEN status = 'completed' THEN download_speed END) as avg_speed,
                        MAX(CASE WHEN status = 'completed' THEN download_speed END) as peak_speed
                    FROM downloads
                """)
                
                # Calculate additional metrics
                stats = dict(user_stats)
                stats.update(dict(download_stats))
                
                # Calculate success rate
                if stats['total_downloads'] > 0:
                    stats['global_success_rate'] = (stats['successful_downloads'] / stats['total_downloads']) * 100
                else:
                    stats['global_success_rate'] = 0
                
                # Calculate average per user
                if stats['total_users'] > 0:
                    stats['avg_per_user'] = stats['total_data_processed'] / stats['total_users']
                else:
                    stats['avg_per_user'] = 0
                
                return stats
                
        except Exception as e:
            logger.error(f"❌ Failed to get global stats: {e}")
            return {}
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Get database performance statistics"""
        try:
            if self.connection_pool is None:
                raise RuntimeError("Connection pool not initialized")
            async with self.connection_pool.acquire() as conn:
                # Check connection
                await conn.fetchval("SELECT 1")
                connected = True
                
                # Get database size
                db_size = await conn.fetchval("""
                    SELECT pg_size_pretty(pg_database_size(current_database()))
                """)
                
                # Get table sizes
                table_sizes = await conn.fetch("""
                    SELECT 
                        schemaname as schema,
                        tablename as table,
                        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                        pg_total_relation_size(schemaname||'.'||tablename) as bytes
                    FROM pg_tables 
                    WHERE schemaname = 'public'
                    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                    LIMIT 10
                """)
                
                # Get user and download counts
                total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
                total_downloads = await conn.fetchval("SELECT COUNT(*) FROM downloads")
                
                return {
                    'connected': connected,
                    'database_size': db_size,
                    'database_size_bytes': sum(row['bytes'] for row in table_sizes),
                    'total_users': total_users,
                    'total_downloads': total_downloads,
                    'table_sizes': [dict(row) for row in table_sizes]
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to get database stats: {e}")
            return {'connected': False, 'error': str(e)}
    
    async def cleanup_old_records(self, days: int = 30):
        """Clean up old records to maintain performance"""
        try:
            if self.connection_pool is None:
                raise RuntimeError("Connection pool not initialized")
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            async with self.connection_pool.acquire() as conn:
                # Clean up old completed downloads
                deleted_downloads = await conn.fetchval("""
                    DELETE FROM downloads 
                    WHERE status IN ('completed', 'failed', 'cancelled') 
                    AND completed_at < $1
                    RETURNING COUNT(*)
                """, cutoff_date)
                
                # Clean up old system stats
                deleted_stats = await conn.fetchval("""
                    DELETE FROM system_stats 
                    WHERE timestamp < $1
                    RETURNING COUNT(*)
                """, cutoff_date)
                
                # Clean up old error logs
                deleted_errors = await conn.fetchval("""
                    DELETE FROM error_logs 
                    WHERE created_at < $1 AND resolved = true
                    RETURNING COUNT(*)
                """, cutoff_date)
                
                logger.info(f"🗑️ Cleaned up {deleted_downloads} downloads, {deleted_stats} stats, {deleted_errors} errors")
                
        except Exception as e:
            logger.error(f"❌ Failed to cleanup old records: {e}")
    
    async def log_error(
        self,
        error_type: str,
        error_message: str,
        error_traceback: Optional[str] = None,
        user_id: Optional[int] = None,
        url: Optional[str] = None,
        platform: Optional[str] = None,
        task_id: Optional[str] = None,
        severity: str = 'error',
        request_data: Optional[Dict[str, Any]] = None
    ):
        """Log error to database"""
        try:
            if self.connection_pool is None:
                raise RuntimeError("Connection pool not initialized")
            async with self.connection_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO error_logs 
                    (error_type, error_message, error_traceback, user_id, url, platform, 
                     task_id, severity, request_data, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """, error_type, error_message, error_traceback, user_id, url, platform,
                   task_id, severity, request_data, datetime.utcnow())
                
        except Exception as e:
            logger.error(f"❌ Failed to log error: {e}")
    
    async def close_all_connections(self):
        """Close all database connections"""
        try:
            if self.connection_pool:
                await self.connection_pool.close()
                self.connection_pool = None
            
            if self.engine:
                await self.engine.dispose()
                self.engine = None
            
            self.session_factory = None
            self.is_initialized = False
            
            logger.info("🔌 Database connections closed")
            
        except Exception as e:
            logger.error(f"❌ Error closing database connections: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform database health check"""
        try:
            if not self.connection_pool:
                return {'healthy': False, 'error': 'Connection pool not initialized'}
            
            async with self.connection_pool.acquire() as conn:
                # Test basic query
                result = await conn.fetchval("SELECT 1")
                
                if result == 1:
                    return {'healthy': True, 'connected': True}
                else:
                    return {'healthy': False, 'error': 'Unexpected query result'}
                    
        except Exception as e:
            return {'healthy': False, 'error': str(e), 'connected': False}
