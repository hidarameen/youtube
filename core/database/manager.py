"""
Database Manager - إدارة قاعدة البيانات المتقدمة
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from redis import Redis, ConnectionPool
from motor.motor_asyncio import AsyncIOMotorClient

from ..config import config

logger = logging.getLogger(__name__)


class DatabaseManager:
	"""مدير قاعدة البيانات المتطور"""
	
	def __init__(self):
		self.engine = None
		self.async_engine = None
		self.session_factory = None
		self.async_session_factory = None
		self.redis_client = None
		self.mongo_client = None
		self._initialized = False
	
	async def initialize(self):
		"""تهيئة قاعدة البيانات"""
		if self._initialized:
			return
		
		try:
			# تهيئة PostgreSQL
			await self._init_postgresql()
			
			# تهيئة Redis
			await self._init_redis()
			
			# تهيئة MongoDB (اختياري)
			try:
				await self._init_mongodb()
			except Exception as e:
				logger.warning(f"⚠️ فشل في تهيئة MongoDB (اختياري): {e}")
				self.mongo_client = None
			
			# إنشاء الجداول
			await self._create_tables()
			
			self._initialized = True
			logger.info("✅ تم تهيئة قاعدة البيانات بنجاح")
			
		except Exception as e:
			logger.error(f"❌ فشل في تهيئة قاعدة البيانات: {e}")
			raise
	
	async def _init_postgresql(self):
		"""تهيئة PostgreSQL"""
		try:
			# إنشاء محرك قاعدة البيانات
			self.engine = create_engine(
				config.database.url,
				poolclass=QueuePool,
				pool_size=config.database.pool_size,
				max_overflow=config.database.max_overflow,
				pool_timeout=config.database.pool_timeout,
				pool_recycle=config.database.pool_recycle,
				echo=config.web.debug
			)
			
			# إنشاء محرك غير متزامن
			async_url = config.database.url.replace('postgresql://', 'postgresql+asyncpg://')
			self.async_engine = create_async_engine(
				async_url,
				pool_size=config.database.pool_size,
				max_overflow=config.database.max_overflow,
				pool_timeout=config.database.pool_timeout,
				pool_recycle=config.database.pool_recycle,
				echo=config.web.debug
			)
			
			# إنشاء مصانع الجلسات
			self.session_factory = sessionmaker(
				bind=self.engine,
				autocommit=False,
				autoflush=False
			)
			
			self.async_session_factory = async_sessionmaker(
				bind=self.async_engine,
				autocommit=False,
				autoflush=False
			)
			
			logger.info("✅ تم تهيئة PostgreSQL بنجاح")
			
		except Exception as e:
			logger.error(f"❌ فشل في تهيئة PostgreSQL: {e}")
			raise
	
	async def _init_redis(self):
		"""تهيئة Redis"""
		try:
			# إنشاء pool الاتصالات
			pool = ConnectionPool.from_url(
				config.redis.url,
				max_connections=config.redis.max_connections,
				decode_responses=config.redis.decode_responses,
				socket_timeout=config.redis.socket_timeout
			)
			
			# إنشاء عميل Redis
			self.redis_client = Redis(connection_pool=pool)
			
			# اختبار الاتصال
			await asyncio.to_thread(self.redis_client.ping)
			
			logger.info("✅ تم تهيئة Redis بنجاح")
			
		except Exception as e:
			logger.error(f"❌ فشل في تهيئة Redis: {e}")
			raise
	
	async def _init_mongodb(self):
		"""تهيئة MongoDB"""
		# قد يفشل الاتصال إذا لم تكن الخدمة متوفرة، وهذا مقبول
		self.mongo_client = AsyncIOMotorClient(
			"mongodb://localhost:27017",
			maxPoolSize=50,
			serverSelectionTimeoutMS=5000
		)
		# اختبار الاتصال بشكل اختياري
		await self.mongo_client.admin.command('ping')
		logger.info("✅ تم تهيئة MongoDB بنجاح")
	
	async def _create_tables(self):
		"""إنشاء الجداول"""
		try:
			from .models import Base
			
			async with self.async_engine.begin() as conn:
				await conn.run_sync(Base.metadata.create_all)
			
			logger.info("✅ تم إنشاء الجداول بنجاح")
			
		except Exception as e:
			logger.error(f"❌ فشل في إنشاء الجداول: {e}")
			raise
	
	@asynccontextmanager
	async def get_session(self) -> AsyncSession:
		"""الحصول على جلسة قاعدة البيانات"""
		if not self._initialized:
			await self.initialize()
		
		async with self.async_session_factory() as session:
			try:
				yield session
				await session.commit()
			except Exception:
				await session.rollback()
				raise
			finally:
				await session.close()
	
	def get_sync_session(self) -> Session:
		"""الحصول على جلسة متزامنة"""
		if not self._initialized:
			raise RuntimeError("يجب تهيئة قاعدة البيانات أولاً")
		
		return self.session_factory()
	
	async def health_check(self) -> Dict[str, bool]:
		"""فحص صحة قاعدة البيانات"""
		health_status = {
			"postgresql": False,
			"redis": False,
			"mongodb": False
		}
		
		try:
			# فحص PostgreSQL
			async with self.get_session() as session:
				await session.execute(text("SELECT 1"))
				health_status["postgresql"] = True
		except Exception as e:
			logger.error(f"فشل فحص PostgreSQL: {e}")
		
		try:
			# فحص Redis
			await asyncio.to_thread(self.redis_client.ping)
			health_status["redis"] = True
		except Exception as e:
			logger.error(f"فشل فحص Redis: {e}")
		
		try:
			# فحص MongoDB (إن وجد)
			if self.mongo_client is not None:
				await self.mongo_client.admin.command('ping')
				health_status["mongodb"] = True
		except Exception as e:
			logger.error(f"فشل فحص MongoDB: {e}")
		
		return health_status
	
	async def get_statistics(self) -> Dict[str, Any]:
		"""الحصول على إحصائيات قاعدة البيانات"""
		stats = {
			"total_users": 0,
			"total_downloads": 0,
			"total_uploads": 0,
			"total_size": 0,
			"active_sessions": 0
		}
		
		try:
			async with self.get_session() as session:
				# إحصائيات المستخدمين
				result = await session.execute(text("SELECT COUNT(*) FROM users"))
				stats["total_users"] = result.scalar() or 0
				
				# إحصائيات التحميلات
				result = await session.execute(text("SELECT COUNT(*) FROM downloads"))
				stats["total_downloads"] = result.scalar() or 0
				
				# إحصائيات الرفع
				result = await session.execute(text("SELECT COUNT(*) FROM uploads"))
				stats["total_uploads"] = result.scalar() or 0
				
				# إجمالي الحجم
				result = await session.execute(text("SELECT SUM(file_size) FROM uploads"))
				stats["total_size"] = result.scalar() or 0
				
		except Exception as e:
			logger.error(f"فشل في الحصول على الإحصائيات: {e}")
		
		return stats
	
	async def cleanup_old_data(self, days: int = 30):
		"""تنظيف البيانات القديمة"""
		try:
			async with self.get_session() as session:
				# حذف التحميلات القديمة
				await session.execute(
					text("DELETE FROM downloads WHERE created_at < NOW() - INTERVAL :days DAY"),
					{"days": days}
				)
				
				# حذف الرفع القديم
				await session.execute(
					text("DELETE FROM uploads WHERE created_at < NOW() - INTERVAL :days DAY"),
					{"days": days}
				)
				
				await session.commit()
				
			logger.info(f"✅ تم تنظيف البيانات الأقدم من {days} يوم")
			
		except Exception as e:
			logger.error(f"❌ فشل في تنظيف البيانات: {e}")
	
	async def backup_database(self, backup_path: str):
		"""إنشاء نسخة احتياطية من قاعدة البيانات"""
		try:
			import subprocess
			
			# إنشاء نسخة احتياطية من PostgreSQL
			cmd = [
				"pg_dump",
				"-h", "localhost",
				"-U", "user",
				"-d", "youtube_bot",
				"-f", f"{backup_path}/postgresql_backup.sql"
			]
			
			subprocess.run(cmd, check=True)
			
			logger.info(f"✅ تم إنشاء نسخة احتياطية في {backup_path}")
			
		except Exception as e:
			logger.error(f"❌ فشل في إنشاء النسخة الاحتياطية: {e}")
	
	async def close(self):
		"""إغلاق اتصالات قاعدة البيانات"""
		try:
			if self.async_engine:
				await self.async_engine.dispose()
			
			if self.engine:
				self.engine.dispose()
			
			if self.redis_client:
				self.redis_client.close()
			
			if self.mongo_client:
				self.mongo_client.close()
			
			logger.info("✅ تم إغلاق اتصالات قاعدة البيانات")
			
		except Exception as e:
			logger.error(f"❌ فشل في إغلاق قاعدة البيانات: {e}")


# إنشاء نسخة عامة من مدير قاعدة البيانات
db_manager = DatabaseManager()