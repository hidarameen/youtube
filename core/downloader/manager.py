"""
Download Manager - مدير التحميل المتطور
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any, List, Callable
from pathlib import Path
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from datetime import datetime, timezone

import yt_dlp
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import config
from ..database.manager import db_manager
from ..database.models import Download, User
from .yt_dlp_wrapper import YTDlpWrapper
from .progress import ProgressTracker

logger = logging.getLogger(__name__)


@dataclass
class DownloadRequest:
    """طلب التحميل"""
    user_id: str
    video_url: str
    quality: str = "720"
    format: str = "mp4"
    audio_only: bool = False
    callback: Optional[Callable] = None


@dataclass
class DownloadResult:
    """نتيجة التحميل"""
    success: bool
    file_path: Optional[Path] = None
    file_size: Optional[int] = None
    duration: Optional[int] = None
    title: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class DownloadManager:
    """مدير التحميل المتطور"""
    
    def __init__(self):
        self.yt_dlp_wrapper = YTDlpWrapper()
        self.progress_tracker = ProgressTracker()
        self.executor = ThreadPoolExecutor(
            max_workers=config.download.max_concurrent_downloads,
            thread_name_prefix="DownloadWorker"
        )
        self.active_downloads: Dict[str, asyncio.Task] = {}
        self.download_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
    
    async def start(self):
        """بدء مدير التحميل"""
        if self._running:
            return
        
        self._running = True
        logger.info("🚀 بدء مدير التحميل")
        
        # بدء معالج الطوابير
        asyncio.create_task(self._queue_processor())
        
        # بدء مراقب التقدم
        asyncio.create_task(self._progress_monitor())
    
    async def stop(self):
        """إيقاف مدير التحميل"""
        if not self._running:
            return
        
        self._running = False
        logger.info("🛑 إيقاف مدير التحميل")
        
        # إيقاف جميع التحميلات النشطة
        for task in self.active_downloads.values():
            task.cancel()
        
        # انتظار انتهاء المهام
        if self.active_downloads:
            await asyncio.gather(*self.active_downloads.values(), return_exceptions=True)
        
        # إغلاق المعالج
        self.executor.shutdown(wait=True)
    
    async def download_video(self, request: DownloadRequest) -> str:
        """تحميل فيديو"""
        try:
            # إنشاء سجل التحميل في قاعدة البيانات
            download_id = await self._create_download_record(request)
            
            # إضافة الطلب إلى الطابور
            await self.download_queue.put((download_id, request))
            
            logger.info(f"📥 تم إضافة طلب التحميل: {download_id}")
            return download_id
            
        except Exception as e:
            logger.error(f"❌ فشل في إنشاء طلب التحميل: {e}")
            raise
    
    async def _create_download_record(self, request: DownloadRequest) -> str:
        """إنشاء سجل التحميل في قاعدة البيانات"""
        async with db_manager.get_session() as session:
            # الحصول على المستخدم
            user = await session.get(User, request.user_id)
            if not user:
                raise ValueError("المستخدم غير موجود")
            
            # إنشاء سجل التحميل
            download = Download(
                user_id=request.user_id,
                video_url=request.video_url,
                quality=request.quality,
                format=request.format,
                audio_only=request.audio_only,
                status="pending"
            )
            
            session.add(download)
            await session.commit()
            await session.refresh(download)
            
            return str(download.id)
    
    async def _queue_processor(self):
        """معالج طابور التحميل"""
        while self._running:
            try:
                # انتظار طلب جديد
                download_id, request = await asyncio.wait_for(
                    self.download_queue.get(), 
                    timeout=1.0
                )
                
                # بدء التحميل
                task = asyncio.create_task(
                    self._process_download(download_id, request)
                )
                self.active_downloads[download_id] = task
                
                # تنظيف المهام المكتملة
                await self._cleanup_completed_tasks()
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"❌ خطأ في معالج الطابور: {e}")
    
    async def _process_download(self, download_id: str, request: DownloadRequest):
        """معالجة التحميل"""
        try:
            logger.info(f"⏬ بدء تحميل: {download_id}")
            
            # تحديث حالة التحميل
            await self._update_download_status(download_id, "downloading")
            
            # تحميل الفيديو
            result = await self._download_with_yt_dlp(request)
            
            if result.success:
                # تحديث قاعدة البيانات
                await self._update_download_success(download_id, result)
                
                # استدعاء callback إذا كان موجوداً
                if request.callback:
                    await request.callback(download_id, result)
                
                logger.info(f"✅ تم تحميل الفيديو بنجاح: {download_id}")
            else:
                # تحديث الخطأ
                await self._update_download_error(download_id, result.error_message)
                logger.error(f"❌ فشل في تحميل الفيديو: {download_id} - {result.error_message}")
            
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة التحميل {download_id}: {e}")
            await self._update_download_error(download_id, str(e))
    
    async def _download_with_yt_dlp(self, request: DownloadRequest) -> DownloadResult:
        """تحميل باستخدام yt-dlp"""
        try:
            # إعداد خيارات التحميل
            ydl_opts = self._prepare_ydl_opts(request)
            
            # تحميل الفيديو
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                self.executor,
                self.yt_dlp_wrapper.download_video,
                request.video_url,
                ydl_opts
            )
            
            return result
            
        except Exception as e:
            logger.error(f"❌ خطأ في تحميل yt-dlp: {e}")
            return DownloadResult(
                success=False,
                error_message=str(e)
            )
    
    def _prepare_ydl_opts(self, request: DownloadRequest) -> Dict[str, Any]:
        """إعداد خيارات yt-dlp"""
        # تحديد مسار الإخراج
        output_template = str(config.download.download_dir / "%(title).200B [%(id)s].%(ext)s")
        
        # تحديد التنسيق
        if request.audio_only:
            format_selector = "bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio"
        else:
            format_selector = f"bestvideo[height<={request.quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={request.quality}][ext=mp4]/best[height<={request.quality}]"
        
        return {
            "outtmpl": output_template,
            "format": format_selector,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "merge_output_format": request.format,
            "concurrent_fragment_downloads": 5,
            "retries": config.download.retry_attempts,
            "fragment_retries": 10,
            "trim_file_name": 200,
            "ignoreerrors": False,
            "progress_hooks": [self.progress_tracker.update_progress],
            "user_agent": config.download.user_agent,
            "socket_timeout": config.download.timeout,
        }
    
    async def _update_download_status(self, download_id: str, status: str):
        """تحديث حالة التحميل"""
        async with db_manager.get_session() as session:
            download = await session.get(Download, download_id)
            if download:
                download.status = status
                if status == "downloading":
                    download.started_at = datetime.now(timezone.utc)
                await session.commit()
    
    async def _update_download_success(self, download_id: str, result: DownloadResult):
        """تحديث نجاح التحميل"""
        async with db_manager.get_session() as session:
            download = await session.get(Download, download_id)
            if download:
                download.status = "completed"
                download.progress = 100.0
                download.file_path = str(result.file_path) if result.file_path else None
                download.file_name = result.file_path.name if result.file_path else None
                download.file_size = result.file_size
                download.duration = result.duration
                download.title = result.title
                download.completed_at = datetime.now(timezone.utc)
                
                # تحديث إحصائيات المستخدم
                user = await session.get(User, download.user_id)
                if user:
                    user.total_downloads += 1
                    if result.file_size:
                        user.total_size_bytes += result.file_size
                
                await session.commit()
    
    async def _update_download_error(self, download_id: str, error_message: str):
        """تحديث خطأ التحميل"""
        async with db_manager.get_session() as session:
            download = await session.get(Download, download_id)
            if download:
                download.status = "failed"
                download.error_message = error_message
                download.retry_count += 1
                await session.commit()
    
    async def _cleanup_completed_tasks(self):
        """تنظيف المهام المكتملة"""
        completed_tasks = []
        
        for download_id, task in self.active_downloads.items():
            if task.done():
                completed_tasks.append(download_id)
        
        for download_id in completed_tasks:
            del self.active_downloads[download_id]
    
    async def _progress_monitor(self):
        """مراقب التقدم"""
        while self._running:
            try:
                # تحديث التقدم كل ثانية
                await asyncio.sleep(1)
                
                # تحديث التقدم في قاعدة البيانات
                await self._update_progress_in_db()
                
            except Exception as e:
                logger.error(f"❌ خطأ في مراقب التقدم: {e}")
    
    async def _update_progress_in_db(self):
        """تحديث التقدم في قاعدة البيانات"""
        try:
            progress_data = self.progress_tracker.get_progress()
            
            for download_id, progress in progress_data.items():
                async with db_manager.get_session() as session:
                    download = await session.get(Download, download_id)
                    if download and download.status == "downloading":
                        download.progress = progress
                        download.downloaded_size = int(progress * (download.file_size or 0) / 100)
                        await session.commit()
                        
        except Exception as e:
            logger.error(f"❌ خطأ في تحديث التقدم: {e}")
    
    async def get_download_status(self, download_id: str) -> Optional[Dict[str, Any]]:
        """الحصول على حالة التحميل"""
        try:
            async with db_manager.get_session() as session:
                download = await session.get(Download, download_id)
                if download:
                    return {
                        "id": str(download.id),
                        "status": download.status,
                        "progress": download.progress,
                        "file_size": download.file_size,
                        "downloaded_size": download.downloaded_size,
                        "title": download.title,
                        "error_message": download.error_message,
                        "created_at": download.created_at.isoformat(),
                        "started_at": download.started_at.isoformat() if download.started_at else None,
                        "completed_at": download.completed_at.isoformat() if download.completed_at else None,
                    }
            return None
            
        except Exception as e:
            logger.error(f"❌ خطأ في الحصول على حالة التحميل: {e}")
            return None
    
    async def cancel_download(self, download_id: str) -> bool:
        """إلغاء التحميل"""
        try:
            # إلغاء المهمة إذا كانت نشطة
            if download_id in self.active_downloads:
                task = self.active_downloads[download_id]
                task.cancel()
                del self.active_downloads[download_id]
            
            # تحديث حالة التحميل
            await self._update_download_status(download_id, "cancelled")
            
            logger.info(f"❌ تم إلغاء التحميل: {download_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ خطأ في إلغاء التحميل: {e}")
            return False
    
    async def get_active_downloads(self) -> List[Dict[str, Any]]:
        """الحصول على التحميلات النشطة"""
        try:
            async with db_manager.get_session() as session:
                downloads = await session.execute(
                    "SELECT * FROM downloads WHERE status = 'downloading'"
                )
                
                return [
                    {
                        "id": str(download.id),
                        "user_id": str(download.user_id),
                        "video_url": download.video_url,
                        "progress": download.progress,
                        "file_size": download.file_size,
                        "title": download.title,
                        "created_at": download.created_at.isoformat(),
                    }
                    for download in downloads
                ]
                
        except Exception as e:
            logger.error(f"❌ خطأ في الحصول على التحميلات النشطة: {e}")
            return []


# إنشاء نسخة عامة من مدير التحميل
download_manager = DownloadManager()