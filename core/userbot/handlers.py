"""
UserBot Handlers - معالجات يوزر البوت
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from ..config import config
from ..database.manager import db_manager
from ..database.models import User, Download, Upload

logger = logging.getLogger(__name__)


class UserBotHandlers:
    """معالجات يوزر البوت"""
    
    def __init__(self):
        self.active_uploads = {}  # تتبع الرفع النشط
        self.upload_progress = {}  # تقدم الرفع
    
    async def handle_message(self, message: Any) -> Optional[str]:
        """معالج الرسائل العامة"""
        try:
            # التحقق من نوع الرسالة
            if hasattr(message, 'text') and message.text:
                return await self._handle_text_message(message)
            elif hasattr(message, 'media') and message.media:
                return await self._handle_media_message(message)
            
            return None
            
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة الرسالة: {e}")
            return None
    
    async def _handle_text_message(self, message: Any) -> Optional[str]:
        """معالج الرسائل النصية"""
        try:
            text = message.text.strip()
            
            # التحقق من الأوامر
            if text.startswith('.yt'):
                return await self._handle_yt_command(message)
            elif text.startswith('.status'):
                return await self._handle_status_command(message)
            elif text.startswith('.stats'):
                return await self._handle_stats_command(message)
            elif text.startswith('.help'):
                return await self._handle_help_command(message)
            elif text.startswith('.cancel'):
                return await self._handle_cancel_command(message)
            
            return None
            
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة الرسالة النصية: {e}")
            return None
    
    async def _handle_media_message(self, message: Any) -> Optional[str]:
        """معالج الرسائل الوسائطية"""
        try:
            # يمكن إضافة معالجة للوسائط هنا
            # مثل تحليل الفيديوهات المرسلة أو الصور
            
            return None
            
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة الرسالة الوسائطية: {e}")
            return None
    
    async def _handle_yt_command(self, message: Any) -> str:
        """معالج أمر .yt"""
        try:
            # هذا سيتم معالجته في الملف الرئيسي
            return "تم استلام أمر التحميل"
            
        except Exception as e:
            logger.error(f"❌ خطأ في أمر .yt: {e}")
            return f"❌ خطأ: {str(e)}"
    
    async def _handle_status_command(self, message: Any) -> str:
        """معالج أمر .status"""
        try:
            user_id = getattr(message, 'sender_id', None)
            if not user_id:
                return "❌ لم يتم العثور على معرف المستخدم"
            
            # الحصول على حالة التحميلات
            async with db_manager.get_session() as session:
                downloads = await session.execute(
                    "SELECT * FROM downloads WHERE user_id = :user_id AND status IN ('pending', 'downloading') ORDER BY created_at DESC LIMIT 5",
                    {"user_id": str(user_id)}
                )
                
                if not downloads:
                    return "📭 لا توجد تحميلات نشطة حالياً."
                
                status_text = "📊 **حالة التحميلات النشطة:**\n\n"
                
                for download in downloads:
                    progress_bar = self._create_progress_bar(download.progress)
                    status_text += f"""
🎬 **{download.title or 'فيديو'}**
📈 التقدم: {progress_bar} {download.progress:.1f}%
⏱️ الحالة: {self._get_status_emoji(download.status)} {download.status}
📅 التاريخ: {download.created_at.strftime('%Y-%m-%d %H:%M')}
🔗 الرابط: {download.video_url[:50]}...
                    """
                
                return status_text
                
        except Exception as e:
            logger.error(f"❌ خطأ في أمر .status: {e}")
            return "❌ حدث خطأ في الحصول على الحالة"
    
    async def _handle_stats_command(self, message: Any) -> str:
        """معالج أمر .stats"""
        try:
            user_id = getattr(message, 'sender_id', None)
            if not user_id:
                return "❌ لم يتم العثور على معرف المستخدم"
            
            # الحصول على إحصائيات المستخدم
            async with db_manager.get_session() as session:
                user = await session.get(User, str(user_id))
                if not user:
                    return "❌ لم يتم العثور على بيانات المستخدم."
                
                # حساب الإحصائيات
                total_size_gb = user.total_size_bytes / (1024**3)
                
                stats_text = f"""
📊 **إحصائياتك الشخصية**

👤 **المعلومات:**
• الاسم: {user.first_name} {user.last_name or ''}
• اسم المستخدم: @{user.username or 'غير محدد'}
• تاريخ التسجيل: {user.created_at.strftime('%Y-%m-%d')}

📈 **التحميلات:**
• إجمالي التحميلات: {user.total_downloads}
• إجمالي الرفع: {user.total_uploads}
• إجمالي الحجم: {total_size_gb:.2f} جيجا

⚙️ **الإعدادات:**
• الجودة المفضلة: {user.preferred_quality}
• الحد الأقصى: {user.max_file_size_gb} جيجا
• اللغة: {user.language}

🏆 **المستوى:**
• الحالة: {'👑 Premium' if user.is_premium else '👤 عادي'}
• آخر ظهور: {user.last_seen.strftime('%Y-%m-%d %H:%M') if user.last_seen else 'غير محدد'}
                """
                
                return stats_text
                
        except Exception as e:
            logger.error(f"❌ خطأ في أمر .stats: {e}")
            return "❌ حدث خطأ في الحصول على الإحصائيات"
    
    async def _handle_help_command(self, message: Any) -> str:
        """معالج أمر .help"""
        help_text = """
📚 **دليل الاستخدام**

🎯 **الأوامر الأساسية:**
• `.yt <رابط>` - تحميل فيديو
• `.status` - حالة التحميلات
• `.stats` - إحصائياتك
• `.cancel <id>` - إلغاء التحميل
• `.help` - المساعدة

🔗 **أمثلة التحميل:**
• `.yt https://youtu.be/VIDEO_ID`
• `.yt https://youtu.be/VIDEO_ID --res 720`
• `.yt https://youtu.be/VIDEO_ID --audio-only`

⚙️ **خيارات الجودة:**
• `--res 360` - جودة منخفضة
• `--res 480` - جودة متوسطة
• `--res 720` - جودة عالية (افتراضي)
• `--res 1080` - جودة عالية جداً
• `--audio-only` - صوت فقط

📊 **معلومات إضافية:**
• الحد الأقصى: 2 جيجا
• التنسيق الافتراضي: MP4
• الحذف التلقائي بعد الرفع

❓ **للمساعدة الإضافية:**
تواصل مع الدعم الفني
        """
        
        return help_text
    
    async def _handle_cancel_command(self, message: Any) -> str:
        """معالج أمر .cancel"""
        try:
            # هذا سيتم معالجته في الملف الرئيسي
            return "تم استلام أمر الإلغاء"
            
        except Exception as e:
            logger.error(f"❌ خطأ في أمر .cancel: {e}")
            return f"❌ خطأ: {str(e)}"
    
    async def handle_upload_progress(self, upload_id: str, current: int, total: int):
        """معالج تقدم الرفع"""
        try:
            progress = (current / total) * 100
            self.upload_progress[upload_id] = {
                'current': current,
                'total': total,
                'progress': progress,
                'timestamp': datetime.now(timezone.utc)
            }
            
            logger.debug(f"📤 رفع التقدم {upload_id}: {progress:.1f}%")
            
        except Exception as e:
            logger.error(f"❌ خطأ في معالج تقدم الرفع: {e}")
    
    async def get_upload_progress(self, upload_id: str) -> Optional[Dict[str, Any]]:
        """الحصول على تقدم الرفع"""
        try:
            return self.upload_progress.get(upload_id)
            
        except Exception as e:
            logger.error(f"❌ خطأ في الحصول على تقدم الرفع: {e}")
            return None
    
    async def cleanup_upload_progress(self, upload_id: str):
        """تنظيف بيانات تقدم الرفع"""
        try:
            if upload_id in self.upload_progress:
                del self.upload_progress[upload_id]
                logger.debug(f"🗑️ تم تنظيف بيانات الرفع: {upload_id}")
                
        except Exception as e:
            logger.error(f"❌ خطأ في تنظيف بيانات الرفع: {e}")
    
    async def handle_download_completion(self, download_id: str, file_path: str, user_id: str):
        """معالج اكتمال التحميل"""
        try:
            logger.info(f"✅ تم اكتمال التحميل: {download_id}")
            
            # تحديث قاعدة البيانات
            async with db_manager.get_session() as session:
                download = await session.get(Download, download_id)
                if download:
                    download.status = "completed"
                    download.file_path = file_path
                    download.completed_at = datetime.now(timezone.utc)
                    await session.commit()
            
            # يمكن إضافة إشعارات هنا
            
        except Exception as e:
            logger.error(f"❌ خطأ في معالج اكتمال التحميل: {e}")
    
    async def handle_download_error(self, download_id: str, error_message: str):
        """معالج خطأ التحميل"""
        try:
            logger.error(f"❌ خطأ في التحميل {download_id}: {error_message}")
            
            # تحديث قاعدة البيانات
            async with db_manager.get_session() as session:
                download = await session.get(Download, download_id)
                if download:
                    download.status = "failed"
                    download.error_message = error_message
                    await session.commit()
            
            # يمكن إضافة إشعارات هنا
            
        except Exception as e:
            logger.error(f"❌ خطأ في معالج خطأ التحميل: {e}")
    
    async def handle_upload_completion(self, upload_id: str, message_id: int, chat_id: int):
        """معالج اكتمال الرفع"""
        try:
            logger.info(f"✅ تم اكتمال الرفع: {upload_id}")
            
            # تحديث قاعدة البيانات
            async with db_manager.get_session() as session:
                upload = await session.get(Upload, upload_id)
                if upload:
                    upload.status = "completed"
                    upload.telegram_message_id = message_id
                    upload.telegram_chat_id = chat_id
                    upload.completed_at = datetime.now(timezone.utc)
                    await session.commit()
            
            # تنظيف بيانات التقدم
            await self.cleanup_upload_progress(upload_id)
            
        except Exception as e:
            logger.error(f"❌ خطأ في معالج اكتمال الرفع: {e}")
    
    async def handle_upload_error(self, upload_id: str, error_message: str):
        """معالج خطأ الرفع"""
        try:
            logger.error(f"❌ خطأ في الرفع {upload_id}: {error_message}")
            
            # تحديث قاعدة البيانات
            async with db_manager.get_session() as session:
                upload = await session.get(Upload, upload_id)
                if upload:
                    upload.status = "failed"
                    upload.error_message = error_message
                    await session.commit()
            
            # تنظيف بيانات التقدم
            await self.cleanup_upload_progress(upload_id)
            
        except Exception as e:
            logger.error(f"❌ خطأ في معالج خطأ الرفع: {e}")
    
    def _create_progress_bar(self, progress: float, width: int = 20) -> str:
        """إنشاء شريط التقدم"""
        filled = int(width * progress / 100)
        empty = width - filled
        return "█" * filled + "░" * empty
    
    def _get_status_emoji(self, status: str) -> str:
        """الحصول على رمز الحالة"""
        emojis = {
            "pending": "⏳",
            "downloading": "📥",
            "completed": "✅",
            "failed": "❌",
            "cancelled": "🚫",
            "uploaded": "📤"
        }
        return emojis.get(status, "❓")
    
    async def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """الحصول على معلومات المستخدم"""
        try:
            async with db_manager.get_session() as session:
                user = await session.get(User, user_id)
                if user:
                    return {
                        'id': str(user.id),
                        'telegram_id': user.telegram_id,
                        'username': user.username,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'language': user.language,
                        'is_premium': user.is_premium,
                        'is_admin': user.is_admin,
                        'total_downloads': user.total_downloads,
                        'total_uploads': user.total_uploads,
                        'total_size_bytes': user.total_size_bytes,
                        'created_at': user.created_at.isoformat(),
                        'last_seen': user.last_seen.isoformat() if user.last_seen else None
                    }
                return None
                
        except Exception as e:
            logger.error(f"❌ خطأ في الحصول على معلومات المستخدم: {e}")
            return None
    
    async def update_user_last_seen(self, user_id: str):
        """تحديث آخر ظهور للمستخدم"""
        try:
            async with db_manager.get_session() as session:
                user = await session.get(User, user_id)
                if user:
                    user.last_seen = datetime.now(timezone.utc)
                    await session.commit()
                    
        except Exception as e:
            logger.error(f"❌ خطأ في تحديث آخر ظهور: {e}")
    
    async def increment_user_stats(self, user_id: str, download_size: int = 0):
        """زيادة إحصائيات المستخدم"""
        try:
            async with db_manager.get_session() as session:
                user = await session.get(User, user_id)
                if user:
                    user.total_downloads += 1
                    if download_size > 0:
                        user.total_size_bytes += download_size
                    await session.commit()
                    
        except Exception as e:
            logger.error(f"❌ خطأ في زيادة إحصائيات المستخدم: {e}")


# إنشاء نسخة عامة
userbot_handlers = UserBotHandlers()