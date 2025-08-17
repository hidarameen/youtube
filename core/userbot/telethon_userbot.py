"""
Telethon UserBot - يوزر البوت المتطور
"""

import asyncio
import logging
import re
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pathlib import Path

from telethon import TelegramClient, events
from telethon.tl.types import Message, DocumentAttributeVideo, DocumentAttributeAudio
from telethon.errors import FloodWaitError, FilePartMissingError

from ..config import config
from ..database.manager import db_manager
from ..database.models import User, Download, Upload
from ..downloader.manager import download_manager
from ..uploader.manager import UploadManager
from .handlers import UserBotHandlers

logger = logging.getLogger(__name__)


class TelethonUserBot:
    """يوزر البوت المتطور باستخدام Telethon"""
    
    def __init__(self):
        self.client = TelegramClient(
            config.telegram.session_name,
            config.telegram.api_id,
            config.telegram.api_hash
        )
        self.handlers = UserBotHandlers()
        self.upload_manager = UploadManager()
        self._running = False
        self._semaphore = asyncio.Semaphore(1)  # منع التحميلات المتزامنة
        
        # تسجيل المعالجات
        self._register_handlers()
    
    async def start(self):
        """بدء يوزر البوت"""
        if self._running:
            return
        
        try:
            logger.info("👤 بدء يوزر البوت...")
            
            # بدء العميل
            await self.client.start()
            
            # التحقق من الاتصال
            if not await self.client.is_user_authorized():
                logger.error("❌ فشل في تفويض المستخدم")
                raise Exception("فشل في تفويض المستخدم")
            
            # الحصول على معلومات المستخدم
            me = await self.client.get_me()
            logger.info(f"✅ تم تسجيل الدخول كـ: {me.first_name} (@{me.username})")
            
            self._running = True
            logger.info("✅ تم بدء يوزر البوت بنجاح!")
            
            # بدء مراقبة الرسائل
            await self.client.run_until_disconnected()
            
        except Exception as e:
            logger.error(f"❌ فشل في بدء يوزر البوت: {e}")
            raise
    
    async def stop(self):
        """إيقاف يوزر البوت"""
        if not self._running:
            return
        
        try:
            logger.info("🛑 إيقاف يوزر البوت...")
            await self.client.disconnect()
            self._running = False
            logger.info("✅ تم إيقاف يوزر البوت بنجاح!")
            
        except Exception as e:
            logger.error(f"❌ خطأ في إيقاف يوزر البوت: {e}")
    
    def _register_handlers(self):
        """تسجيل معالجات الأحداث"""
        
        @self.client.on(events.NewMessage(outgoing=True, pattern=r'^\.yt\s+(.+)$'))
        async def handle_yt_command(event):
            """معالج أمر .yt"""
            await self._handle_yt_command(event)
        
        @self.client.on(events.NewMessage(outgoing=True, pattern=r'^\.status$'))
        async def handle_status_command(event):
            """معالج أمر .status"""
            await self._handle_status_command(event)
        
        @self.client.on(events.NewMessage(outgoing=True, pattern=r'^\.stats$'))
        async def handle_stats_command(event):
            """معالج أمر .stats"""
            await self._handle_stats_command(event)
        
        @self.client.on(events.NewMessage(outgoing=True, pattern=r'^\.cancel\s+(.+)$'))
        async def handle_cancel_command(event):
            """معالج أمر .cancel"""
            await self._handle_cancel_command(event)
        
        @self.client.on(events.NewMessage(outgoing=True, pattern=r'^\.help$'))
        async def handle_help_command(event):
            """معالج أمر .help"""
            await self._handle_help_command(event)
        
        @self.client.on(events.NewMessage(outgoing=True, pattern=r'^\.settings$'))
        async def handle_settings_command(event):
            """معالج أمر .settings"""
            await self._handle_settings_command(event)
    
    async def _handle_yt_command(self, event: Message):
        """معالج أمر .yt"""
        try:
            async with self._semaphore:
                # تحليل الأمر
                command_text = event.text
                match = re.match(r'^\.yt\s+(.+)$', command_text)
                if not match:
                    await event.reply("❌ الرابط مطلوب. مثال: `.yt https://youtu.be/VIDEO_ID`")
                    return
                
                url = match.group(1).strip()
                quality = "720"  # افتراضي
                audio_only = False
                
                # تحليل الخيارات
                if "--res" in command_text:
                    res_match = re.search(r'--res\s+(\d+)', command_text)
                    if res_match:
                        quality = res_match.group(1)
                
                if "--audio-only" in command_text:
                    audio_only = True
                
                # التحقق من صحة الرابط
                if not self._is_youtube_url(url):
                    await event.reply("❌ الرابط غير صحيح. يجب أن يكون رابط يوتيوب.")
                    return
                
                # إرسال رسالة البداية
                status_message = await event.reply(
                    "⏳ **جاري بدء التحميل...**\n\n"
                    f"🔗 الرابط: {url[:50]}...\n"
                    f"🎯 الجودة: {quality}\n"
                    f"📊 الحالة: جاري التحضير..."
                )
                
                # إنشاء أو تحديث المستخدم
                user_id = await self._ensure_user_exists(event.sender_id)
                
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
                
                # تحديث الرسالة
                await status_message.edit(
                    "✅ **تم بدء التحميل!**\n\n"
                    f"🔗 الرابط: {url[:50]}...\n"
                    f"🎯 الجودة: {quality}\n"
                    f"📊 الحالة: جاري التحميل...\n"
                    f"🆔 معرف التحميل: {download_id[:8]}..."
                )
                
                # بدء مراقبة التقدم
                asyncio.create_task(self._monitor_download_progress(download_id, status_message, event.chat_id))
                
        except Exception as e:
            logger.error(f"❌ خطأ في أمر .yt: {e}")
            await event.reply(f"❌ فشل في بدء التحميل: {str(e)}")
    
    async def _handle_status_command(self, event: Message):
        """معالج أمر .status"""
        try:
            user_id = event.sender_id
            
            # الحصول على التحميلات النشطة للمستخدم
            async with db_manager.get_session() as session:
                downloads = await session.execute(
                    "SELECT * FROM downloads WHERE user_id = :user_id AND status IN ('pending', 'downloading') ORDER BY created_at DESC LIMIT 5",
                    {"user_id": str(user_id)}
                )
                
                if not downloads:
                    await event.reply("📭 لا توجد تحميلات نشطة حالياً.")
                    return
                
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
                
                await event.reply(status_text)
                
        except Exception as e:
            logger.error(f"❌ خطأ في أمر .status: {e}")
            await event.reply("❌ حدث خطأ، يرجى المحاولة مرة أخرى.")
    
    async def _handle_stats_command(self, event: Message):
        """معالج أمر .stats"""
        try:
            user_id = event.sender_id
            
            # الحصول على إحصائيات المستخدم
            async with db_manager.get_session() as session:
                user = await session.get(User, str(user_id))
                if not user:
                    await event.reply("❌ لم يتم العثور على بيانات المستخدم.")
                    return
                
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
                
                await event.reply(stats_text)
                
        except Exception as e:
            logger.error(f"❌ خطأ في أمر .stats: {e}")
            await event.reply("❌ حدث خطأ، يرجى المحاولة مرة أخرى.")
    
    async def _handle_cancel_command(self, event: Message):
        """معالج أمر .cancel"""
        try:
            command_text = event.text
            match = re.match(r'^\.cancel\s+(.+)$', command_text)
            if not match:
                await event.reply("❌ معرف التحميل مطلوب. مثال: `.cancel download_id`")
                return
            
            download_id = match.group(1).strip()
            
            # إلغاء التحميل
            success = await download_manager.cancel_download(download_id)
            
            if success:
                await event.reply(f"✅ تم إلغاء التحميل: {download_id[:8]}...")
            else:
                await event.reply(f"❌ فشل في إلغاء التحميل: {download_id[:8]}...")
                
        except Exception as e:
            logger.error(f"❌ خطأ في أمر .cancel: {e}")
            await event.reply("❌ حدث خطأ، يرجى المحاولة مرة أخرى.")
    
    async def _handle_help_command(self, event: Message):
        """معالج أمر .help"""
        help_text = """
📚 **دليل الاستخدام**

🎯 **الأوامر الأساسية:**
• `.yt <رابط>` - تحميل فيديو
• `.status` - حالة التحميلات
• `.stats` - إحصائياتك
• `.cancel <id>` - إلغاء التحميل
• `.settings` - إعداداتك
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
        
        await event.reply(help_text)
    
    async def _handle_settings_command(self, event: Message):
        """معالج أمر .settings"""
        try:
            user_id = event.sender_id
            
            # الحصول على إعدادات المستخدم
            async with db_manager.get_session() as session:
                user = await session.get(User, str(user_id))
                if not user:
                    await event.reply("❌ لم يتم العثور على بيانات المستخدم.")
                    return
                
                settings_text = f"""
⚙️ **إعداداتك الشخصية**

🎯 **إعدادات التحميل:**
• الجودة المفضلة: {user.preferred_quality}
• الحد الأقصى: {user.max_file_size_gb} جيجا
• التنسيق الافتراضي: MP4

🌍 **إعدادات عامة:**
• اللغة: {user.language}
• المنطقة الزمنية: {user.timezone}

🔔 **الإشعارات:**
• إشعارات التحميل: ✅ مفعلة
• إشعارات النظام: ✅ مفعلة
• إشعارات التحديثات: ✅ مفعلة

💾 **التخزين:**
• الحذف التلقائي: ✅ مفعل
• ضغط الملفات: ✅ مفعل
• تشفير البيانات: ✅ مفعل
                """
                
                await event.reply(settings_text)
                
        except Exception as e:
            logger.error(f"❌ خطأ في أمر .settings: {e}")
            await event.reply("❌ حدث خطأ، يرجى المحاولة مرة أخرى.")
    
    async def _monitor_download_progress(self, download_id: str, status_message: Message, chat_id: int):
        """مراقبة تقدم التحميل"""
        try:
            while True:
                # الحصول على حالة التحميل
                status = await download_manager.get_download_status(download_id)
                if not status:
                    break
                
                # تحديث الرسالة
                progress_bar = self._create_progress_bar(status['progress'])
                status_text = f"""
📥 **حالة التحميل**

🔗 الرابط: {status.get('title', 'جاري التحميل...')}
📊 التقدم: {progress_bar} {status['progress']:.1f}%
⏱️ الحالة: {self._get_status_emoji(status['status'])} {status['status']}
💾 الحجم: {self._format_size(status.get('downloaded_size', 0))} / {self._format_size(status.get('file_size', 0))}
🆔 المعرف: {download_id[:8]}...
                """
                
                await status_message.edit(status_text)
                
                # التحقق من اكتمال التحميل
                if status['status'] in ['completed', 'failed']:
                    if status['status'] == 'completed':
                        await status_message.edit(
                            f"✅ **تم التحميل بنجاح!**\n\n"
                            f"🎬 العنوان: {status.get('title', 'غير محدد')}\n"
                            f"💾 الحجم: {self._format_size(status.get('file_size', 0))}\n"
                            f"📅 التاريخ: {status.get('completed_at', 'غير محدد')}\n\n"
                            f"📤 جاري الرفع إلى تلجرام..."
                        )
                        
                        # بدء عملية الرفع
                        await self._upload_to_telegram(download_id, chat_id)
                    else:
                        await status_message.edit(
                            f"❌ **فشل في التحميل**\n\n"
                            f"🔗 الرابط: {status.get('video_url', 'غير محدد')}\n"
                            f"❌ الخطأ: {status.get('error_message', 'خطأ غير محدد')}\n\n"
                            f"🔄 يرجى المحاولة مرة أخرى"
                        )
                    break
                
                # انتظار قبل التحديث التالي
                await asyncio.sleep(5)
                
        except Exception as e:
            logger.error(f"❌ خطأ في مراقبة التقدم: {e}")
    
    async def _upload_to_telegram(self, download_id: str, chat_id: int):
        """رفع الملف إلى تلجرام"""
        try:
            # الحصول على معلومات التحميل
            async with db_manager.get_session() as session:
                download = await session.get(Download, download_id)
                if not download or not download.file_path:
                    logger.error(f"❌ لم يتم العثور على ملف التحميل: {download_id}")
                    return
                
                file_path = Path(download.file_path)
                if not file_path.exists():
                    logger.error(f"❌ الملف غير موجود: {file_path}")
                    return
                
                # التحقق من حجم الملف
                file_size = file_path.stat().st_size
                if file_size > config.telegram.max_file_size_bytes:
                    await self.client.send_message(
                        chat_id,
                        f"❌ **الملف كبير جداً!**\n\n"
                        f"💾 حجم الملف: {self._format_size(file_size)}\n"
                        f"📏 الحد الأقصى: {self._format_size(config.telegram.max_file_size_bytes)}\n\n"
                        f"💡 جرب جودة أقل أو اختر صوت فقط."
                    )
                    return
                
                # إنشاء التسمية
                caption = f"""
🎬 **{download.title or 'فيديو من يوتيوب'}**

📊 **المعلومات:**
• الجودة: {download.quality}p
• التنسيق: {download.format}
• الحجم: {self._format_size(file_size)}
• المدة: {self._format_duration(download.duration) if download.duration else 'غير محدد'}

🔗 **الرابط الأصلي:**
{download.video_url}

📅 **تاريخ التحميل:**
{download.completed_at.strftime('%Y-%m-%d %H:%M:%S')}

⚡ **تم التحميل بواسطة بوت يوتيوب وتلجرام الضخم**
                """
                
                # رفع الملف
                await self.client.send_file(
                    chat_id,
                    file_path,
                    caption=caption,
                    supports_streaming=True,
                    progress_callback=lambda current, total: self._upload_progress_callback(current, total, chat_id)
                )
                
                # تحديث قاعدة البيانات
                download.status = "uploaded"
                await session.commit()
                
                # حذف الملف المحلي
                file_path.unlink()
                
                await self.client.send_message(
                    chat_id,
                    "✅ **تم الرفع بنجاح!**\n\n"
                    "🎉 يمكنك الآن مشاهدة الفيديو أعلاه.\n"
                    "🗑️ تم حذف الملف المحلي تلقائياً."
                )
                
        except FloodWaitError as e:
            await self.client.send_message(
                chat_id,
                f"⏳ **انتظار مطلوب**\n\n"
                f"🕐 يجب الانتظار {e.seconds} ثانية قبل المحاولة مرة أخرى.\n"
                f"📊 هذا بسبب حدود تلجرام."
            )
        except FilePartMissingError:
            await self.client.send_message(
                chat_id,
                "❌ **خطأ في الملف**\n\n"
                "🔧 يبدو أن الملف تالف أو غير مكتمل.\n"
                "🔄 يرجى المحاولة مرة أخرى."
            )
        except Exception as e:
            logger.error(f"❌ خطأ في رفع الملف: {e}")
            await self.client.send_message(
                chat_id,
                f"❌ **فشل في الرفع**\n\n"
                f"🔧 حدث خطأ أثناء رفع الملف.\n"
                f"📝 الخطأ: {str(e)}"
            )
    
    async def _upload_progress_callback(self, current: int, total: int, chat_id: int):
        """callback لتقدم الرفع"""
        try:
            progress = (current / total) * 100
            progress_bar = self._create_progress_bar(progress)
            
            # يمكن إرسال تحديثات التقدم هنا إذا لزم الأمر
            logger.debug(f"📤 رفع التقدم: {progress_bar} {progress:.1f}%")
            
        except Exception as e:
            logger.error(f"❌ خطأ في callback الرفع: {e}")
    
    async def _ensure_user_exists(self, telegram_id: int) -> str:
        """التأكد من وجود المستخدم في قاعدة البيانات"""
        try:
            async with db_manager.get_session() as session:
                existing_user = await session.execute(
                    "SELECT * FROM users WHERE telegram_id = :telegram_id",
                    {"telegram_id": telegram_id}
                )
                
                if not existing_user:
                    # الحصول على معلومات المستخدم من تلجرام
                    user_info = await self.client.get_entity(telegram_id)
                    
                    # إنشاء مستخدم جديد
                    new_user = User(
                        telegram_id=telegram_id,
                        username=user_info.username,
                        first_name=user_info.first_name,
                        last_name=user_info.last_name,
                        language="ar"
                    )
                    session.add(new_user)
                    await session.commit()
                    await session.refresh(new_user)
                    logger.info(f"✅ تم إنشاء مستخدم جديد: {telegram_id}")
                    return str(new_user.id)
                else:
                    return str(existing_user.id)
                
        except Exception as e:
            logger.error(f"❌ خطأ في إنشاء المستخدم: {e}")
            return str(telegram_id)
    
    def _is_youtube_url(self, url: str) -> bool:
        """التحقق من كون الرابط رابط يوتيوب"""
        youtube_patterns = [
            r'youtube\.com/watch\?v=',
            r'youtu\.be/',
            r'youtube\.com/embed/',
            r'youtube\.com/v/',
            r'youtube\.com/shorts/'
        ]
        
        return any(re.search(pattern, url) for pattern in youtube_patterns)
    
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
    
    def _format_size(self, size_bytes: int) -> str:
        """تنسيق الحجم"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"
    
    def _format_duration(self, seconds: int) -> str:
        """تنسيق المدة"""
        if not seconds:
            return "غير محدد"
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"


# إنشاء نسخة عامة من يوزر البوت
telethon_userbot = TelethonUserBot()