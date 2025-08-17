"""
Telegram Bot - بوت تلجرام المتطور
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    Message, CallbackQuery
)

from ..config import config
from ..database.manager import db_manager
from ..database.models import User, Download, Upload
from ..downloader.manager import download_manager
from .keyboards import InlineKeyboards
from .handlers import CommandHandlers
from sqlalchemy import select, desc
import contextlib

logger = logging.getLogger(__name__)


class DownloadStates(StatesGroup):
    """حالات التحميل"""
    waiting_for_url = State()
    waiting_for_quality = State()
    waiting_for_format = State()
    downloading = State()


class TelegramBot:
    """بوت تلجرام المتطور"""
    
    def __init__(self):
        self.bot = Bot(token=config.telegram.bot_token)
        self.dp = Dispatcher(storage=MemoryStorage())
        self.router = Router()
        self.keyboards = InlineKeyboards()
        self.handlers = CommandHandlers()
        self._running = False
        self._polling_task: Optional[asyncio.Task] = None
        
        # تسجيل المعالجات
        self._register_handlers()
    
    async def start(self):
        """بدء البوت"""
        if self._running:
            return
        
        try:
            logger.info("🤖 بدء بوت تلجرام...")
            
            # بدء البوت
            await self.bot.delete_webhook(drop_pending_updates=True)
            self._polling_task = asyncio.create_task(self.dp.start_polling(self.bot))
            
            self._running = True
            logger.info("✅ تم بدء بوت تلجرام بنجاح!")
            
        except Exception as e:
            logger.error(f"❌ فشل في بدء بوت تلجرام: {e}")
            raise
    
    async def stop(self):
        """إيقاف البوت"""
        if not self._running:
            return
        
        try:
            logger.info("🛑 إيقاف بوت تلجرام...")
            if self._polling_task is not None:
                self._polling_task.cancel()
                with contextlib.suppress(Exception):
                    await self._polling_task
            await self.bot.session.close()
            self._running = False
            logger.info("✅ تم إيقاف بوت تلجرام بنجاح!")
            
        except Exception as e:
            logger.error(f"❌ خطأ في إيقاف بوت تلجرام: {e}")
    
    def _register_handlers(self):
        """تسجيل معالجات الأوامر"""
        
        # أوامر أساسية
        self.router.message.register(self._start_command, Command("start"))
        self.router.message.register(self._help_command, Command("help"))
        self.router.message.register(self._download_command, Command("download"))
        self.router.message.register(self._status_command, Command("status"))
        self.router.message.register(self._stats_command, Command("stats"))
        self.router.message.register(self._settings_command, Command("settings"))
        
        # أوامر الإدارة
        self.router.message.register(self._admin_command, Command("admin"))
        self.router.message.register(self._users_command, Command("users"))
        self.router.message.register(self._system_command, Command("system"))
        
        # معالجات النصوص
        self.router.message.register(self._handle_text, F.text.startswith(".yt"))
        self.router.message.register(
            self._handle_url,
            F.text.regexp(r"(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be)")
        )
        
        # معالجات Callback
        self.router.callback_query.register(self._handle_callback)
        
        # إضافة الراوتر للديسباتشر
        self.dp.include_router(self.router)
    
    async def _start_command(self, message: Message):
        """معالج أمر /start"""
        try:
            user_name = message.from_user.first_name
            
            # إنشاء أو تحديث المستخدم في قاعدة البيانات
            await self._ensure_user_exists(message.from_user)
            
            welcome_text = f"""
🎉 مرحباً {user_name}! 

مرحباً بك في بوت تحميل يوتيوب وتلجرام الضخم! 🚀

📋 **الأوامر المتاحة:**
• `/download` - تحميل فيديو جديد
• `/status` - حالة التحميلات
• `/stats` - إحصائياتك
• `/settings` - إعداداتك
• `/help` - المساعدة

💡 **طريقة سريعة:**
أرسل رابط يوتيوب مباشرة أو استخدم:
`.yt <رابط> --res 720`

⚡ **الميزات:**
• تحميل حتى 2 جيجا
• دعم جميع الدقات
• رفع سريع لتلجرام
• مراقبة التقدم المباشر

🚀 **ابدأ الآن!**
            """
            
            keyboard = self.keyboards.get_main_menu()
            await message.answer(welcome_text, reply_markup=keyboard)
            
        except Exception as e:
            logger.error(f"❌ خطأ في أمر start: {e}")
            await message.answer("❌ حدث خطأ، يرجى المحاولة مرة أخرى.")
    
    async def _help_command(self, message: Message):
        """معالج أمر /help"""
        help_text = """
📚 **دليل الاستخدام**

🎯 **الأوامر الأساسية:**
• `/start` - بدء البوت
• `/download` - تحميل فيديو جديد
• `/status` - حالة التحميلات
• `/stats` - إحصائياتك
• `/settings` - إعداداتك

🔗 **طريقة التحميل:**
1. أرسل رابط يوتيوب مباشرة
2. أو استخدم: `.yt <رابط> --res 720`
3. أو استخدم أمر `/download`

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
        
        keyboard = self.keyboards.get_help_menu()
        await message.answer(help_text, reply_markup=keyboard)
    
    async def _download_command(self, message: Message, state: FSMContext):
        """معالج أمر /download"""
        try:
            await state.set_state(DownloadStates.waiting_for_url)
            
            text = """
📥 **تحميل فيديو جديد**

أرسل رابط فيديو يوتيوب الذي تريد تحميله:

🔗 **مثال:**
https://youtu.be/VIDEO_ID

💡 **نصائح:**
• تأكد من أن الرابط صحيح
• يمكنك إرسال روابط من قوائم التشغيل
• الحد الأقصى: 2 جيجا

❌ **للإلغاء:** أرسل /cancel
            """
            
            keyboard = self.keyboards.get_cancel_keyboard()
            await message.answer(text, reply_markup=keyboard)
            
        except Exception as e:
            logger.error(f"❌ خطأ في أمر download: {e}")
            await message.answer("❌ حدث خطأ، يرجى المحاولة مرة أخرى.")
    
    async def _status_command(self, message: Message):
        """معالج أمر /status"""
        try:
            user_tg_id = message.from_user.id
            
            # الحصول على التحميلات النشطة للمستخدم عبر ORM
            async with db_manager.get_session() as session:
                result_user = await session.execute(select(User).where(User.telegram_id == user_tg_id))
                user = result_user.scalars().first()
                if not user:
                    await message.answer("📭 لا توجد تحميلات نشطة حالياً.")
                    return
                result = await session.execute(
                    select(Download)
                    .where(Download.user_id == user.id, Download.status.in_(['pending', 'downloading']))
                    .order_by(desc(Download.created_at))
                    .limit(5)
                )
                downloads = result.scalars().all()
                
                if not downloads:
                    await message.answer("📭 لا توجد تحميلات نشطة حالياً.")
                    return
                
                status_text = "📊 **حالة التحميلات النشطة:**\n\n"
                
                for download in downloads:
                    progress_bar = self._create_progress_bar(download.progress or 0.0)
                    status_text += f"""
🎬 **{download.title or 'فيديو'}**
📈 التقدم: {progress_bar} {download.progress or 0.0:.1f}%
⏱️ الحالة: {self._get_status_emoji(download.status)} {download.status}
📅 التاريخ: {download.created_at.strftime('%Y-%m-%d %H:%M')}
🔗 الرابط: {download.video_url[:50]}...
                    """
                
                keyboard = self.keyboards.get_status_menu()
                await message.answer(status_text, reply_markup=keyboard)
                
        except Exception as e:
            logger.error(f"❌ خطأ في أمر status: {e}")
            await message.answer("❌ حدث خطأ، يرجى المحاولة مرة أخرى.")
    
    async def _stats_command(self, message: Message):
        """معالج أمر /stats"""
        try:
            user_tg_id = message.from_user.id
            
            # الحصول على إحصائيات المستخدم
            async with db_manager.get_session() as session:
                result_user = await session.execute(select(User).where(User.telegram_id == user_tg_id))
                user = result_user.scalars().first()
                if not user:
                    await message.answer("❌ لم يتم العثور على بيانات المستخدم.")
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
                
                keyboard = self.keyboards.get_stats_menu()
                await message.answer(stats_text, reply_markup=keyboard)
                
        except Exception as e:
            logger.error(f"❌ خطأ في أمر stats: {e}")
            await message.answer("❌ حدث خطأ، يرجى المحاولة مرة أخرى.")
    
    async def _settings_command(self, message: Message):
        """معالج أمر /settings"""
        try:
            user_tg_id = message.from_user.id
            
            # الحصول على إعدادات المستخدم
            async with db_manager.get_session() as session:
                result_user = await session.execute(select(User).where(User.telegram_id == user_tg_id))
                user = result_user.scalars().first()
                if not user:
                    await message.answer("❌ لم يتم العثور على بيانات المستخدم.")
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
                
                keyboard = self.keyboards.get_settings_menu()
                await message.answer(settings_text, reply_markup=keyboard)
                
        except Exception as e:
            logger.error(f"❌ خطأ في أمر settings: {e}")
            await message.answer("❌ حدث خطأ، يرجى المحاولة مرة أخرى.")

    async def _admin_command(self, message: Message):
        """معالج أمر /admin <command> [args...] يوجه إلى CommandHandlers"""
        try:
            parts = (message.text or "").split()
            # parts[0] هو /admin
            subcmd = parts[1].lower() if len(parts) > 1 else ""
            args = parts[2:] if len(parts) > 2 else []
            if not subcmd:
                await message.answer("❌ استخدم: /admin <users|system|maintenance|logs|health> [args]")
                return
            result = await self.handlers.handle_admin_command(message.from_user.id, subcmd, args)
            await message.answer(result)
        except Exception as e:
            logger.error(f"❌ خطأ في أمر admin: {e}")
            await message.answer("❌ حدث خطأ في أمر الإدارة")

    async def _users_command(self, message: Message):
        """معالج أمر /users يوجه لأمر إدارة users"""
        try:
            result = await self.handlers.handle_admin_command(message.from_user.id, "users", [])
            await message.answer(result)
        except Exception as e:
            logger.error(f"❌ خطأ في أمر users: {e}")
            await message.answer("❌ حدث خطأ أثناء جلب المستخدمين")

    async def _system_command(self, message: Message):
        """معالج أمر /system يوجه لأمر إدارة system"""
        try:
            result = await self.handlers.handle_admin_command(message.from_user.id, "system", [])
            await message.answer(result)
        except Exception as e:
            logger.error(f"❌ خطأ في أمر system: {e}")
            await message.answer("❌ حدث خطأ أثناء جلب معلومات النظام")
    
    async def _handle_text(self, message: Message):
        """معالج النصوص التي تبدأ بـ .yt"""
        try:
            text = message.text
            
            # تحليل الأمر
            parts = text.split()
            if len(parts) < 2:
                await message.answer("❌ الرابط مطلوب. مثال: `.yt https://youtu.be/VIDEO_ID`")
                return
            
            url = parts[1]
            quality = "720"  # افتراضي
            audio_only = False
            
            # تحليل الخيارات
            for part in parts[2:]:
                if part.startswith("--res"):
                    try:
                        quality = part.split("=")[1]
                    except:
                        pass
                elif part == "--audio-only":
                    audio_only = True
            
            # بدء التحميل
            await self._start_download(message, url, quality, audio_only)
            
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة النص: {e}")
            await message.answer("❌ حدث خطأ، يرجى المحاولة مرة أخرى.")
    
    async def _handle_url(self, message: Message):
        """معالج روابط يوتيوب"""
        try:
            url = message.text
            
            # عرض خيارات الجودة
            keyboard = self.keyboards.get_quality_selection(url)
            await message.answer(
                "🎬 **اختر جودة التحميل:**",
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة الرابط: {e}")
            await message.answer("❌ حدث خطأ، يرجى المحاولة مرة أخرى.")
    
    async def _handle_callback(self, callback: CallbackQuery):
        """معالج Callback Queries"""
        try:
            data = callback.data
            
            if data.startswith("quality_"):
                # اختيار الجودة
                parts = data.split("_")
                quality = parts[1]
                url = parts[2]
                await self._start_download(callback.message, url, quality)
                
            elif data.startswith("cancel"):
                # إلغاء العملية
                await callback.message.edit_text("❌ تم إلغاء العملية.")
                
            elif data.startswith("settings_"):
                # إعدادات
                setting = data.split("_")[1]
                await self._handle_setting_change(callback, setting)
                
            await callback.answer()
            
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة callback: {e}")
            await callback.answer("❌ حدث خطأ")
    
    async def _start_download(self, message: Message, url: str, quality: str = "720", audio_only: bool = False):
        """بدء عملية التحميل"""
        try:
            # التأكد من وجود المستخدم والحصول على معرفه في قاعدة البيانات
            user_db_id = await self._ensure_user_exists(message.from_user)
            
            # إنشاء طلب التحميل
            from ..downloader.manager import DownloadRequest
            
            request = DownloadRequest(
                user_id=str(user_db_id),
                video_url=url,
                quality=quality,
                audio_only=audio_only
            )
            
            # إرسال رسالة التحميل
            status_message = await message.answer(
                "⏳ **جاري بدء التحميل...**\n\n"
                f"🔗 الرابط: {url[:50]}...\n"
                f"🎯 الجودة: {quality}\n"
                f"📊 الحالة: جاري التحضير..."
            )
            
            # بدء التحميل
            download_id = await download_manager.download_video(request)
            
            # تحديث الرسالة
            await status_message.edit_text(
                "✅ **تم بدء التحميل!**\n\n"
                f"🔗 الرابط: {url[:50]}...\n"
                f"🎯 الجودة: {quality}\n"
                f"📊 الحالة: جاري التحميل...\n"
                f"🆔 معرف التحميل: {download_id[:8]}..."
            )
            
            # بدء مراقبة التقدم
            asyncio.create_task(self._monitor_download_progress(download_id, status_message))
            
        except Exception as e:
            logger.error(f"❌ خطأ في بدء التحميل: {e}")
            await message.answer(f"❌ فشل في بدء التحميل: {str(e)}")
    
    async def _monitor_download_progress(self, download_id: str, message: Message):
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
                
                await message.edit_text(status_text)
                
                # التحقق من اكتمال التحميل
                if status['status'] in ['completed', 'failed']:
                    if status['status'] == 'completed':
                        await message.edit_text(
                            f"✅ **تم التحميل بنجاح!**\n\n"
                            f"🎬 العنوان: {status.get('title', 'غير محدد')}\n"
                            f"💾 الحجم: {self._format_size(status.get('file_size', 0))}\n"
                            f"📅 التاريخ: {status.get('completed_at', 'غير محدد')}\n\n"
                            f"📤 جاري الرفع إلى تلجرام..."
                        )
                    else:
                        await message.edit_text(
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
    
    async def _ensure_user_exists(self, user: types.User) -> str:
        """التأكد من وجود المستخدم في قاعدة البيانات وإرجاع معرفه في قاعدة البيانات"""
        try:
            async with db_manager.get_session() as session:
                result = await session.execute(select(User).where(User.telegram_id == user.id))
                existing = result.scalars().first()
                if not existing:
                    new_user = User(
                        telegram_id=user.id,
                        username=user.username,
                        first_name=user.first_name,
                        last_name=user.last_name,
                        language="ar",
                    )
                    session.add(new_user)
                    await session.commit()
                    await session.refresh(new_user)
                    logger.info(f"✅ تم إنشاء مستخدم جديد: {user.id}")
                    return str(new_user.id)
                else:
                    return str(existing.id)
        except Exception as e:
            logger.error(f"❌ خطأ في إنشاء المستخدم: {e}")
            return str(user.id)
    
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
    
    def _is_youtube_url(self, message: Message) -> bool:
        """التحقق من كون الرسالة رابط يوتيوب"""
        text = message.text.lower()
        return any(domain in text for domain in ['youtube.com', 'youtu.be', 'youtube-nocookie.com'])


# ملاحظة: لا تنشئ مثيلاً عاماً هنا لتجنّب تفعيل التوكن أثناء الاستيراد