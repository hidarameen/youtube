"""
Main Application - التطبيق الرئيسي المتطور
بوت تحميل يوتيوب وتلجرام الضخم
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

from core.config import config
from core.database.manager import db_manager
from core.downloader.manager import download_manager
from core.bot.telegram_bot import TelegramBot
from core.userbot.telethon_userbot import TelethonUserBot
from web.api.main import create_web_app
import uvicorn
import contextlib

logger = logging.getLogger(__name__)


class YouTubeTelegramBot:
	"""التطبيق الرئيسي"""
	
	def __init__(self):
		self.download_manager = download_manager
		self.telegram_bot: Optional[TelegramBot] = None
		self.userbot: Optional[TelethonUserBot] = None
		self.web_app = None
		self._uvicorn_server: Optional[uvicorn.Server] = None
		self._uvicorn_task: Optional[asyncio.Task] = None
		self._running = False
		self._shutdown_event = asyncio.Event()
	
	async def start(self):
		"""بدء التطبيق"""
		try:
			logger.info("🚀 بدء تشغيل بوت تحميل يوتيوب وتلجرام الضخم")
			
			# تهيئة قاعدة البيانات
			logger.info("📊 تهيئة قاعدة البيانات...")
			await db_manager.initialize()
			
			# بدء مدير التحميل
			logger.info("📥 بدء مدير التحميل...")
			await self.download_manager.start()
			
			# بدء بوت تلجرام
			if config.telegram.bot_token:
				logger.info("🤖 بدء بوت تلجرام...")
				self.telegram_bot = TelegramBot()
				# يعمل في الخلفية داخل الكائن نفسه
				await self.telegram_bot.start()
			
			# بدء يوزر بوت
			if config.telegram.api_id and config.telegram.api_hash:
				logger.info("👤 بدء يوزر بوت...")
				self.userbot = TelethonUserBot()
				await self.userbot.start()
			
			# بدء تطبيق الويب
			logger.info("🌐 بدء تطبيق الويب...")
			self.web_app = create_web_app()
			uv_config = uvicorn.Config(
				self.web_app,
				host=config.web.host,
				port=config.web.port,
				log_level=config.logging.level.lower(),
			)
			self._uvicorn_server = uvicorn.Server(uv_config)
			self._uvicorn_task = asyncio.create_task(self._uvicorn_server.serve())
			
			# إعداد إشارات الإيقاف
			self._setup_signal_handlers()
			
			self._running = True
			logger.info("✅ تم بدء التطبيق بنجاح!")
			
			# انتظار إشارة الإيقاف
			await self._shutdown_event.wait()
			
		except Exception as e:
			logger.error(f"❌ فشل في بدء التطبيق: {e}")
			await self.stop()
			sys.exit(1)
	
	async def stop(self):
		"""إيقاف التطبيق"""
		if not self._running:
			return
		
		logger.info("🛑 إيقاف التطبيق...")
		self._running = False
		
		try:
			# إيقاف مدير التحميل
			if self.download_manager:
				await self.download_manager.stop()
			
			# إيقاف بوت تلجرام
			if self.telegram_bot:
				await self.telegram_bot.stop()
			
			# إيقاف يوزر بوت
			if self.userbot:
				await self.userbot.stop()
			
			# إيقاف خادم الويب
			if self._uvicorn_server is not None:
				self._uvicorn_server.should_exit = True
			if self._uvicorn_task is not None:
				with contextlib.suppress(Exception):
					await self._uvicorn_task
			
			# إغلاق قاعدة البيانات
			await db_manager.close()
			
			logger.info("✅ تم إيقاف التطبيق بنجاح!")
			
		except Exception as e:
			logger.error(f"❌ خطأ في إيقاف التطبيق: {e}")
	
	def _setup_signal_handlers(self):
		"""إعداد معالجات الإشارات"""
		def signal_handler(signum, frame):
			logger.info(f"📡 استلام إشارة {signum}")
			asyncio.create_task(self.stop())
			self._shutdown_event.set()
		
		signal.signal(signal.SIGINT, signal_handler)
		signal.signal(signal.SIGTERM, signal_handler)
	
	async def health_check(self) -> dict:
		"""فحص صحة التطبيق"""
		health_status = {
			"status": "healthy" if self._running else "unhealthy",
			"components": {}
		}
		
		try:
			# فحص قاعدة البيانات
			db_health = await db_manager.health_check()
			health_status["components"]["database"] = db_health
			
			# فحص مدير التحميل
			health_status["components"]["download_manager"] = {
				"status": "running" if self.download_manager._running else "stopped",
				"active_downloads": len(self.download_manager.active_downloads),
				"queue_size": self.download_manager.download_queue.qsize()
			}
			
			# فحص بوت تلجرام
			if self.telegram_bot:
				health_status["components"]["telegram_bot"] = {
					"status": "running" if self.telegram_bot._running else "stopped"
				}
			
			# فحص يوزر بوت
			if self.userbot:
				health_status["components"]["userbot"] = {
					"status": "running" if self.userbot._running else "stopped"
				}
			
			# تحديد الحالة العامة
			all_healthy = all(
				comp.get("status") in ["running", True] 
				for comp in health_status["components"].values()
			)
			
			health_status["status"] = "healthy" if all_healthy else "degraded"
			
		except Exception as e:
			logger.error(f"❌ خطأ في فحص الصحة: {e}")
			health_status["status"] = "unhealthy"
			health_status["error"] = str(e)
		
		return health_status
	
	async def get_statistics(self) -> dict:
		"""الحصول على إحصائيات التطبيق"""
		try:
			stats = {
				"app": {
					"name": config.app_name,
					"version": config.app_version,
					"environment": config.environment,
					"uptime": 0  # سيتم تحديثه لاحقاً
				},
				"database": await db_manager.get_statistics(),
				"downloads": {
					"active": len(self.download_manager.active_downloads),
					"queue_size": self.download_manager.download_queue.qsize(),
					"progress": self.download_manager.progress_tracker.get_statistics()
				},
				"system": {
					"cpu_usage": 0,  # سيتم تحديثه لاحقاً
					"memory_usage": 0,  # سيتم تحديثه لاحقاً
					"disk_usage": 0  # سيتم تحديثه لاحقاً
				}
			}
			
			return stats
			
		except Exception as e:
			logger.error(f"❌ خطأ في الحصول على الإحصائيات: {e}")
			return {}


async def main():
	"""الدالة الرئيسية"""
	# إعداد التسجيل
	logging.basicConfig(
		level=getattr(logging, config.logging.level),
		format=config.logging.format,
		handlers=[
			logging.FileHandler(config.logging.file),
			logging.StreamHandler(sys.stdout)
		]
	)
	
	# إنشاء التطبيق
	app = YouTubeTelegramBot()
	
	try:
		# بدء التطبيق
		await app.start()
		
	except KeyboardInterrupt:
		logger.info("📡 استلام إشارة الإيقاف")
	except Exception as e:
		logger.error(f"❌ خطأ غير متوقع: {e}")
	finally:
		# إيقاف التطبيق
		await app.stop()


if __name__ == "__main__":
	# تشغيل التطبيق
	asyncio.run(main())