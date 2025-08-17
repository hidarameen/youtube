"""
Command Handlers - معالجات الأوامر المتطورة
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta

from ..config import config
from ..database.manager import db_manager
from ..database.models import User, Download, Upload, Statistics
from ..downloader.manager import download_manager

logger = logging.getLogger(__name__)


class CommandHandlers:
    """معالجات الأوامر المتطورة"""
    
    def __init__(self):
        self.admin_users = set()  # قائمة المستخدمين المدراء
        self._load_admin_users()
    
    def _load_admin_users(self):
        """تحميل قائمة المستخدمين المدراء"""
        # يمكن تحميلها من قاعدة البيانات أو ملف الإعدادات
        admin_ids = getattr(config, 'admin_users', [])
        self.admin_users = set(admin_ids)
    
    async def handle_admin_command(self, user_id: int, command: str, args: List[str]) -> str:
        """معالجة أوامر الإدارة"""
        if user_id not in self.admin_users:
            return "❌ ليس لديك صلاحيات الإدارة."
        
        try:
            if command == "users":
                return await self._get_users_stats()
            elif command == "system":
                return await self._get_system_stats()
            elif command == "maintenance":
                return await self._perform_maintenance()
            elif command == "logs":
                return await self._get_system_logs()
            elif command == "health":
                return await self._get_system_health()
            else:
                return "❌ أمر غير معروف."
                
        except Exception as e:
            logger.error(f"❌ خطأ في أمر الإدارة: {e}")
            return f"❌ حدث خطأ: {str(e)}"
    
    async def _get_users_stats(self) -> str:
        """الحصول على إحصائيات المستخدمين"""
        try:
            async with db_manager.get_session() as session:
                # إحصائيات المستخدمين
                total_users = await session.execute("SELECT COUNT(*) FROM users")
                active_users = await session.execute(
                    "SELECT COUNT(*) FROM users WHERE last_seen > NOW() - INTERVAL '24 hours'"
                )
                new_users_today = await session.execute(
                    "SELECT COUNT(*) FROM users WHERE created_at > NOW() - INTERVAL '24 hours'"
                )
                
                # إحصائيات التحميل
                total_downloads = await session.execute("SELECT COUNT(*) FROM downloads")
                successful_downloads = await session.execute(
                    "SELECT COUNT(*) FROM downloads WHERE status = 'completed'"
                )
                failed_downloads = await session.execute(
                    "SELECT COUNT(*) FROM downloads WHERE status = 'failed'"
                )
                
                stats_text = f"""
📊 **إحصائيات المستخدمين**

👥 **المستخدمين:**
• إجمالي المستخدمين: {total_users.scalar() or 0}
• المستخدمين النشطين (24 ساعة): {active_users.scalar() or 0}
• مستخدمين جدد اليوم: {new_users_today.scalar() or 0}

📥 **التحميلات:**
• إجمالي التحميلات: {total_downloads.scalar() or 0}
• التحميلات الناجحة: {successful_downloads.scalar() or 0}
• التحميلات الفاشلة: {failed_downloads.scalar() or 0}
• نسبة النجاح: {(successful_downloads.scalar() or 0) / (total_downloads.scalar() or 1) * 100:.1f}%

📈 **النشاط:**
• التحميلات النشطة: {len(download_manager.active_downloads)}
• حجم الطابور: {download_manager.download_queue.qsize()}
                """
                
                return stats_text
                
        except Exception as e:
            logger.error(f"❌ خطأ في إحصائيات المستخدمين: {e}")
            return "❌ فشل في الحصول على الإحصائيات."
    
    async def _get_system_stats(self) -> str:
        """الحصول على إحصائيات النظام"""
        try:
            import psutil
            
            # إحصائيات النظام
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # إحصائيات الشبكة
            network = psutil.net_io_counters()
            
            # إحصائيات قاعدة البيانات
            db_stats = await db_manager.get_statistics()
            
            stats_text = f"""
🖥️ **إحصائيات النظام**

💻 **المعالج والذاكرة:**
• استخدام المعالج: {cpu_percent}%
• استخدام الذاكرة: {memory.percent}% ({memory.used // (1024**3):.1f}GB / {memory.total // (1024**3):.1f}GB)
• الذاكرة المتاحة: {memory.available // (1024**3):.1f}GB

💾 **التخزين:**
• استخدام القرص: {disk.percent}% ({disk.used // (1024**3):.1f}GB / {disk.total // (1024**3):.1f}GB)
• المساحة المتاحة: {disk.free // (1024**3):.1f}GB

🌐 **الشبكة:**
• البيانات المرسلة: {network.bytes_sent // (1024**3):.1f}GB
• البيانات المستلمة: {network.bytes_recv // (1024**3):.1f}GB

🗄️ **قاعدة البيانات:**
• إجمالي المستخدمين: {db_stats.get('total_users', 0)}
• إجمالي التحميلات: {db_stats.get('total_downloads', 0)}
• إجمالي الرفع: {db_stats.get('total_uploads', 0)}
• إجمالي الحجم: {db_stats.get('total_size', 0) // (1024**3):.1f}GB
                """
                
                return stats_text
                
        except Exception as e:
            logger.error(f"❌ خطأ في إحصائيات النظام: {e}")
            return "❌ فشل في الحصول على إحصائيات النظام."
    
    async def _perform_maintenance(self) -> str:
        """تنفيذ صيانة النظام"""
        try:
            maintenance_tasks = []
            
            # تنظيف الملفات المؤقتة
            from utils.file_utils import file_utils
            temp_cleaned = await file_utils.cleanup_temp_files(config.download.temp_dir)
            maintenance_tasks.append(f"🗑️ تم حذف {temp_cleaned} ملف مؤقت")
            
            # تنظيف قاعدة البيانات
            await db_manager.cleanup_old_data(days=30)
            maintenance_tasks.append("🗄️ تم تنظيف قاعدة البيانات")
            
            # إعادة تشغيل مدير التحميل
            await download_manager.stop()
            await asyncio.sleep(2)
            await download_manager.start()
            maintenance_tasks.append("🔄 تم إعادة تشغيل مدير التحميل")
            
            # فحص صحة النظام
            health_status = await db_manager.health_check()
            if all(health_status.values()):
                maintenance_tasks.append("✅ جميع الخدمات تعمل بشكل طبيعي")
            else:
                failed_services = [service for service, status in health_status.items() if not status]
                maintenance_tasks.append(f"⚠️ مشاكل في: {', '.join(failed_services)}")
            
            maintenance_text = "🔧 **تم تنفيذ الصيانة:**\n\n"
            for task in maintenance_tasks:
                maintenance_text += f"• {task}\n"
            
            return maintenance_text
            
        except Exception as e:
            logger.error(f"❌ خطأ في الصيانة: {e}")
            return f"❌ فشل في تنفيذ الصيانة: {str(e)}"
    
    async def _get_system_logs(self, lines: int = 50) -> str:
        """الحصول على سجلات النظام"""
        try:
            async with db_manager.get_session() as session:
                logs = await session.execute(
                    "SELECT * FROM system_logs ORDER BY created_at DESC LIMIT :lines",
                    {"lines": lines}
                )
                
                if not logs:
                    return "📋 لا توجد سجلات حديثة."
                
                logs_text = f"📋 **آخر {lines} سجل:**\n\n"
                
                for log in logs:
                    timestamp = log.created_at.strftime('%Y-%m-%d %H:%M:%S')
                    level_emoji = self._get_log_level_emoji(log.level)
                    logs_text += f"{level_emoji} **{timestamp}** [{log.level}]\n"
                    logs_text += f"📝 {log.message}\n"
                    if log.module:
                        logs_text += f"🔧 الوحدة: {log.module}\n"
                    logs_text += "\n"
                
                return logs_text
                
        except Exception as e:
            logger.error(f"❌ خطأ في سجلات النظام: {e}")
            return "❌ فشل في الحصول على السجلات."
    
    async def _get_system_health(self) -> str:
        """فحص صحة النظام"""
        try:
            health_status = await db_manager.health_check()
            
            health_text = "🏥 **حالة النظام:**\n\n"
            
            for service, status in health_status.items():
                status_emoji = "✅" if status else "❌"
                status_text = "يعمل" if status else "متوقف"
                health_text += f"{status_emoji} **{service}**: {status_text}\n"
            
            # فحص مدير التحميل
            download_status = "✅ يعمل" if download_manager._running else "❌ متوقف"
            health_text += f"\n📥 **مدير التحميل**: {download_status}"
            
            # فحص التحميلات النشطة
            active_downloads = len(download_manager.active_downloads)
            health_text += f"\n📊 **التحميلات النشطة**: {active_downloads}"
            
            # تقييم عام
            all_healthy = all(health_status.values()) and download_manager._running
            overall_status = "🟢 ممتاز" if all_healthy else "🟡 جيد" if any(health_status.values()) else "🔴 ضعيف"
            health_text += f"\n\n📈 **التقييم العام**: {overall_status}"
            
            return health_text
            
        except Exception as e:
            logger.error(f"❌ خطأ في فحص الصحة: {e}")
            return f"❌ فشل في فحص صحة النظام: {str(e)}"
    
    async def handle_user_command(self, user_id: int, command: str, args: List[str]) -> str:
        """معالجة أوامر المستخدم"""
        try:
            if command == "download":
                return await self._handle_download_command(user_id, args)
            elif command == "status":
                return await self._handle_status_command(user_id)
            elif command == "stats":
                return await self._handle_stats_command(user_id)
            elif command == "settings":
                return await self._handle_settings_command(user_id, args)
            elif command == "help":
                return await self._handle_help_command(args)
            else:
                return "❌ أمر غير معروف. استخدم /help للمساعدة."
                
        except Exception as e:
            logger.error(f"❌ خطأ في أمر المستخدم: {e}")
            return f"❌ حدث خطأ: {str(e)}"
    
    async def _handle_download_command(self, user_id: int, args: List[str]) -> str:
        """معالجة أمر التحميل"""
        if not args:
            return "❌ الرابط مطلوب. مثال: /download https://youtu.be/VIDEO_ID"
        
        url = args[0]
        quality = "720"
        audio_only = False
        
        # تحليل الخيارات
        for arg in args[1:]:
            if arg.startswith("--res="):
                quality = arg.split("=")[1]
            elif arg == "--audio-only":
                audio_only = True
        
        try:
            # إنشاء طلب التحميل
            from ..downloader.manager import DownloadRequest
            
            request = DownloadRequest(
                user_id=str(user_id),
                video_url=url,
                quality=quality,
                audio_only=audio_only
            )
            
            # بدء التحميل
            download_id = await download_manager.download_video(request)
            
            return f"""
✅ **تم بدء التحميل!**

🔗 الرابط: {url[:50]}...
🎯 الجودة: {quality}
🆔 معرف التحميل: {download_id[:8]}...

📊 استخدم /status لمراقبة التقدم
            """
            
        except Exception as e:
            logger.error(f"❌ خطأ في بدء التحميل: {e}")
            return f"❌ فشل في بدء التحميل: {str(e)}"
    
    async def _handle_status_command(self, user_id: int) -> str:
        """معالجة أمر الحالة"""
        try:
            # الحصول على التحميلات النشطة
            active_downloads = await download_manager.get_active_downloads()
            user_downloads = [d for d in active_downloads if d['user_id'] == str(user_id)]
            
            if not user_downloads:
                return "📭 لا توجد تحميلات نشطة حالياً."
            
            status_text = "📊 **حالة التحميلات النشطة:**\n\n"
            
            for download in user_downloads:
                progress_bar = self._create_progress_bar(download['progress'])
                status_text += f"""
🎬 **{download.get('title', 'فيديو')}**
📈 التقدم: {progress_bar} {download['progress']:.1f}%
⏱️ الحالة: {self._get_status_emoji(download['status'])} {download['status']}
📅 التاريخ: {download['created_at']}
🔗 الرابط: {download['video_url'][:50]}...
                """
            
            return status_text
            
        except Exception as e:
            logger.error(f"❌ خطأ في أمر الحالة: {e}")
            return "❌ فشل في الحصول على الحالة."
    
    async def _handle_stats_command(self, user_id: int) -> str:
        """معالجة أمر الإحصائيات"""
        try:
            async with db_manager.get_session() as session:
                user = await session.get(User, user_id)
                if not user:
                    return "❌ لم يتم العثور على بيانات المستخدم."
                
                # حساب الإحصائيات
                total_size_gb = user.total_size_bytes / (1024**3)
                
                # إحصائيات إضافية
                recent_downloads = await session.execute(
                    "SELECT COUNT(*) FROM downloads WHERE user_id = :user_id AND created_at > NOW() - INTERVAL '7 days'",
                    {"user_id": user_id}
                )
                
                stats_text = f"""
📊 **إحصائياتك الشخصية**

👤 **المعلومات:**
• الاسم: {user.first_name} {user.last_name or ''}
• اسم المستخدم: @{user.username or 'غير محدد'}
• تاريخ التسجيل: {user.created_at.strftime('%Y-%m-%d')}

📈 **التحميلات:**
• إجمالي التحميلات: {user.total_downloads}
• التحميلات الأسبوع الماضي: {recent_downloads.scalar() or 0}
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
            logger.error(f"❌ خطأ في أمر الإحصائيات: {e}")
            return "❌ فشل في الحصول على الإحصائيات."
    
    async def _handle_settings_command(self, user_id: int, args: List[str]) -> str:
        """معالجة أمر الإعدادات"""
        if not args:
            return """
⚙️ **الإعدادات المتاحة:**

🎯 **جودة التحميل:**
• /settings quality 720
• /settings quality 1080
• /settings quality auto

💾 **الحد الأقصى:**
• /settings maxsize 2
• /settings maxsize 4

🌍 **اللغة:**
• /settings language ar
• /settings language en

🔔 **الإشعارات:**
• /settings notifications on
• /settings notifications off
            """
        
        setting_type = args[0].lower()
        setting_value = args[1] if len(args) > 1 else None
        
        try:
            async with db_manager.get_session() as session:
                user = await session.get(User, user_id)
                if not user:
                    return "❌ لم يتم العثور على بيانات المستخدم."
                
                if setting_type == "quality":
                    user.preferred_quality = setting_value
                    await session.commit()
                    return f"✅ تم تحديث الجودة المفضلة إلى: {setting_value}"
                
                elif setting_type == "maxsize":
                    user.max_file_size_gb = float(setting_value)
                    await session.commit()
                    return f"✅ تم تحديث الحد الأقصى إلى: {setting_value} جيجا"
                
                elif setting_type == "language":
                    user.language = setting_value
                    await session.commit()
                    return f"✅ تم تحديث اللغة إلى: {setting_value}"
                
                elif setting_type == "notifications":
                    # يمكن إضافة إعدادات الإشعارات هنا
                    return f"✅ تم تحديث الإشعارات إلى: {setting_value}"
                
                else:
                    return "❌ نوع إعداد غير معروف."
                    
        except Exception as e:
            logger.error(f"❌ خطأ في تحديث الإعدادات: {e}")
            return f"❌ فشل في تحديث الإعدادات: {str(e)}"
    
    async def _handle_help_command(self, args: List[str]) -> str:
        """معالجة أمر المساعدة"""
        if not args:
            return """
📚 **دليل الاستخدام**

🎯 **الأوامر الأساسية:**
• /start - بدء البوت
• /download <رابط> - تحميل فيديو
• /status - حالة التحميلات
• /stats - إحصائياتك
• /settings - إعداداتك
• /help - المساعدة

🔗 **أمثلة التحميل:**
• /download https://youtu.be/VIDEO_ID
• /download https://youtu.be/VIDEO_ID --res=720
• /download https://youtu.be/VIDEO_ID --audio-only

⚙️ **خيارات الجودة:**
• 360p - جودة منخفضة
• 480p - جودة متوسطة
• 720p - جودة عالية (افتراضي)
• 1080p - جودة عالية جداً
• auto - أفضل جودة متاحة

📊 **معلومات إضافية:**
• الحد الأقصى: 2 جيجا
• التنسيق الافتراضي: MP4
• الحذف التلقائي بعد الرفع

❓ **للمساعدة الإضافية:**
استخدم /help <موضوع> للحصول على مساعدة مفصلة
            """
        
        topic = args[0].lower()
        
        help_topics = {
            "download": """
📥 **مساعدة التحميل**

🎯 **الطريقة الأساسية:**
/download <رابط يوتيوب>

🎯 **مع خيارات:**
/download <رابط> --res=720
/download <رابط> --audio-only

💡 **نصائح:**
• تأكد من أن الرابط صحيح
• يمكنك إرسال روابط من قوائم التشغيل
• الحد الأقصى: 2 جيجا
• التحميل قد يستغرق وقتاً حسب حجم الفيديو
            """,
            
            "settings": """
⚙️ **مساعدة الإعدادات**

🎯 **تغيير الجودة:**
/settings quality 720
/settings quality 1080
/settings quality auto

💾 **تغيير الحد الأقصى:**
/settings maxsize 2
/settings maxsize 4

🌍 **تغيير اللغة:**
/settings language ar
/settings language en

🔔 **الإشعارات:**
/settings notifications on
/settings notifications off
            """,
            
            "troubleshoot": """
🔧 **استكشاف الأخطاء**

❌ **مشاكل شائعة:**

1. **فشل في التحميل:**
   • تحقق من صحة الرابط
   • جرب جودة أقل
   • تحقق من اتصال الإنترنت

2. **الملف كبير جداً:**
   • استخدم جودة أقل
   • اختر صوت فقط
   • تحقق من الحد الأقصى

3. **بطء التحميل:**
   • تحقق من سرعة الإنترنت
   • جرب في وقت آخر
   • تحقق من حالة الخادم

🆘 **للمساعدة الإضافية:**
تواصل مع الدعم الفني
            """
        }
        
        return help_topics.get(topic, "❌ موضوع غير موجود. استخدم /help للحصول على القائمة الكاملة.")
    
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
            "cancelled": "🚫"
        }
        return emojis.get(status, "❓")
    
    def _get_log_level_emoji(self, level: str) -> str:
        """الحصول على رمز مستوى السجل"""
        emojis = {
            "DEBUG": "🔍",
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "CRITICAL": "🚨"
        }
        return emojis.get(level, "📝")


# إنشاء نسخة عامة
command_handlers = CommandHandlers()