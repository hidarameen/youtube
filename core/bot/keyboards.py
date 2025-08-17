"""
Inline Keyboards - لوحات المفاتيح التفاعلية المتطورة
"""

import logging
from typing import List, Dict, Any, Optional
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)

logger = logging.getLogger(__name__)


class InlineKeyboards:
    """لوحات المفاتيح التفاعلية المتطورة"""
    
    def get_main_menu(self) -> InlineKeyboardMarkup:
        """القائمة الرئيسية"""
        keyboard = [
            [
                InlineKeyboardButton(text="📥 تحميل فيديو", callback_data="download_video"),
                InlineKeyboardButton(text="📊 إحصائياتي", callback_data="my_stats")
            ],
            [
                InlineKeyboardButton(text="⚙️ الإعدادات", callback_data="settings"),
                InlineKeyboardButton(text="❓ المساعدة", callback_data="help")
            ],
            [
                InlineKeyboardButton(text="🆘 الدعم الفني", callback_data="support"),
                InlineKeyboardButton(text="⭐ تقييم البوت", callback_data="rate_bot")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    def get_help_menu(self) -> InlineKeyboardMarkup:
        """قائمة المساعدة"""
        keyboard = [
            [
                InlineKeyboardButton(text="📚 الدليل الكامل", callback_data="full_guide"),
                InlineKeyboardButton(text="🎯 أمثلة الاستخدام", callback_data="usage_examples")
            ],
            [
                InlineKeyboardButton(text="❓ الأسئلة الشائعة", callback_data="faq"),
                InlineKeyboardButton(text="🔧 استكشاف الأخطاء", callback_data="troubleshoot")
            ],
            [
                InlineKeyboardButton(text="📞 التواصل مع الدعم", callback_data="contact_support"),
                InlineKeyboardButton(text="🔙 العودة للقائمة الرئيسية", callback_data="main_menu")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    def get_quality_selection(self, url: str) -> InlineKeyboardMarkup:
        """اختيار جودة التحميل"""
        # ترميز الرابط للـ callback
        encoded_url = url.replace(":", "_").replace("/", "_").replace(".", "_")
        
        keyboard = [
            [
                InlineKeyboardButton(text="🎬 1080p (أعلى جودة)", callback_data=f"quality_1080_{encoded_url}"),
                InlineKeyboardButton(text="🎬 720p (جودة عالية)", callback_data=f"quality_720_{encoded_url}")
            ],
            [
                InlineKeyboardButton(text="🎬 480p (جودة متوسطة)", callback_data=f"quality_480_{encoded_url}"),
                InlineKeyboardButton(text="🎬 360p (جودة منخفضة)", callback_data=f"quality_360_{encoded_url}")
            ],
            [
                InlineKeyboardButton(text="🎵 صوت فقط (MP3)", callback_data=f"quality_audio_{encoded_url}"),
                InlineKeyboardButton(text="🎵 صوت فقط (M4A)", callback_data=f"quality_m4a_{encoded_url}")
            ],
            [
                InlineKeyboardButton(text="❌ إلغاء", callback_data="cancel_download")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    def get_cancel_keyboard(self) -> InlineKeyboardMarkup:
        """لوحة إلغاء العملية"""
        keyboard = [
            [
                InlineKeyboardButton(text="❌ إلغاء العملية", callback_data="cancel_operation")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    def get_status_menu(self) -> InlineKeyboardMarkup:
        """قائمة حالة التحميلات"""
        keyboard = [
            [
                InlineKeyboardButton(text="🔄 تحديث الحالة", callback_data="refresh_status"),
                InlineKeyboardButton(text="❌ إلغاء جميع التحميلات", callback_data="cancel_all_downloads")
            ],
            [
                InlineKeyboardButton(text="📊 إحصائيات مفصلة", callback_data="detailed_stats"),
                InlineKeyboardButton(text="📋 سجل التحميلات", callback_data="download_history")
            ],
            [
                InlineKeyboardButton(text="🔙 العودة للقائمة الرئيسية", callback_data="main_menu")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    def get_stats_menu(self) -> InlineKeyboardMarkup:
        """قائمة الإحصائيات"""
        keyboard = [
            [
                InlineKeyboardButton(text="📈 إحصائيات التحميل", callback_data="download_stats"),
                InlineKeyboardButton(text="📊 إحصائيات الرفع", callback_data="upload_stats")
            ],
            [
                InlineKeyboardButton(text="💾 استخدام المساحة", callback_data="storage_stats"),
                InlineKeyboardButton(text="⏱️ إحصائيات الوقت", callback_data="time_stats")
            ],
            [
                InlineKeyboardButton(text="🏆 المستوى والإنجازات", callback_data="achievements"),
                InlineKeyboardButton(text="📋 التقرير الشهري", callback_data="monthly_report")
            ],
            [
                InlineKeyboardButton(text="🔙 العودة للقائمة الرئيسية", callback_data="main_menu")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    def get_settings_menu(self) -> InlineKeyboardMarkup:
        """قائمة الإعدادات"""
        keyboard = [
            [
                InlineKeyboardButton(text="🎯 جودة التحميل", callback_data="setting_quality"),
                InlineKeyboardButton(text="💾 الحد الأقصى", callback_data="setting_max_size")
            ],
            [
                InlineKeyboardButton(text="🌍 اللغة", callback_data="setting_language"),
                InlineKeyboardButton(text="⏰ المنطقة الزمنية", callback_data="setting_timezone")
            ],
            [
                InlineKeyboardButton(text="🔔 الإشعارات", callback_data="setting_notifications"),
                InlineKeyboardButton(text="🔒 الخصوصية", callback_data="setting_privacy")
            ],
            [
                InlineKeyboardButton(text="💾 إعدادات التخزين", callback_data="setting_storage"),
                InlineKeyboardButton(text="🔄 إعادة تعيين الإعدادات", callback_data="reset_settings")
            ],
            [
                InlineKeyboardButton(text="🔙 العودة للقائمة الرئيسية", callback_data="main_menu")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    def get_quality_settings(self) -> InlineKeyboardMarkup:
        """إعدادات الجودة"""
        keyboard = [
            [
                InlineKeyboardButton(text="🎬 1080p", callback_data="set_quality_1080"),
                InlineKeyboardButton(text="🎬 720p", callback_data="set_quality_720")
            ],
            [
                InlineKeyboardButton(text="🎬 480p", callback_data="set_quality_480"),
                InlineKeyboardButton(text="🎬 360p", callback_data="set_quality_360")
            ],
            [
                InlineKeyboardButton(text="🎵 تلقائي (أفضل جودة)", callback_data="set_quality_auto")
            ],
            [
                InlineKeyboardButton(text="🔙 العودة للإعدادات", callback_data="settings")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    def get_size_settings(self) -> InlineKeyboardMarkup:
        """إعدادات الحد الأقصى"""
        keyboard = [
            [
                InlineKeyboardButton(text="💾 500MB", callback_data="set_max_size_0.5"),
                InlineKeyboardButton(text="💾 1GB", callback_data="set_max_size_1")
            ],
            [
                InlineKeyboardButton(text="💾 2GB", callback_data="set_max_size_2"),
                InlineKeyboardButton(text="💾 4GB", callback_data="set_max_size_4")
            ],
            [
                InlineKeyboardButton(text="💾 غير محدود", callback_data="set_max_size_unlimited")
            ],
            [
                InlineKeyboardButton(text="🔙 العودة للإعدادات", callback_data="settings")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    def get_language_settings(self) -> InlineKeyboardMarkup:
        """إعدادات اللغة"""
        keyboard = [
            [
                InlineKeyboardButton(text="🇸🇦 العربية", callback_data="set_language_ar"),
                InlineKeyboardButton(text="🇺🇸 English", callback_data="set_language_en")
            ],
            [
                InlineKeyboardButton(text="🇪🇸 Español", callback_data="set_language_es"),
                InlineKeyboardButton(text="🇫🇷 Français", callback_data="set_language_fr")
            ],
            [
                InlineKeyboardButton(text="🇩🇳 中文", callback_data="set_language_zh"),
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_language_ru")
            ],
            [
                InlineKeyboardButton(text="🔙 العودة للإعدادات", callback_data="settings")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    def get_notification_settings(self) -> InlineKeyboardMarkup:
        """إعدادات الإشعارات"""
        keyboard = [
            [
                InlineKeyboardButton(text="🔔 تفعيل جميع الإشعارات", callback_data="notifications_all_on"),
                InlineKeyboardButton(text="🔕 إيقاف جميع الإشعارات", callback_data="notifications_all_off")
            ],
            [
                InlineKeyboardButton(text="📥 إشعارات التحميل", callback_data="notification_download"),
                InlineKeyboardButton(text="📤 إشعارات الرفع", callback_data="notification_upload")
            ],
            [
                InlineKeyboardButton(text="⚙️ إشعارات النظام", callback_data="notification_system"),
                InlineKeyboardButton(text="🆕 إشعارات التحديثات", callback_data="notification_updates")
            ],
            [
                InlineKeyboardButton(text="🔙 العودة للإعدادات", callback_data="settings")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    def get_privacy_settings(self) -> InlineKeyboardMarkup:
        """إعدادات الخصوصية"""
        keyboard = [
            [
                InlineKeyboardButton(text="🔒 خصوصية عالية", callback_data="privacy_high"),
                InlineKeyboardButton(text="🔓 خصوصية متوسطة", callback_data="privacy_medium")
            ],
            [
                InlineKeyboardButton(text="🌐 خصوصية منخفضة", callback_data="privacy_low"),
                InlineKeyboardButton(text="👁️ إعدادات مخصصة", callback_data="privacy_custom")
            ],
            [
                InlineKeyboardButton(text="🗑️ حذف جميع البيانات", callback_data="delete_all_data"),
                InlineKeyboardButton(text="📋 تصدير البيانات", callback_data="export_data")
            ],
            [
                InlineKeyboardButton(text="🔙 العودة للإعدادات", callback_data="settings")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    def get_storage_settings(self) -> InlineKeyboardMarkup:
        """إعدادات التخزين"""
        keyboard = [
            [
                InlineKeyboardButton(text="🗑️ حذف الملفات المؤقتة", callback_data="clear_temp_files"),
                InlineKeyboardButton(text="🗑️ حذف السجلات القديمة", callback_data="clear_old_logs")
            ],
            [
                InlineKeyboardButton(text="💾 ضغط الملفات", callback_data="compression_on"),
                InlineKeyboardButton(text="🔐 تشفير البيانات", callback_data="encryption_on")
            ],
            [
                InlineKeyboardButton(text="📊 تحليل المساحة", callback_data="analyze_storage"),
                InlineKeyboardButton(text="🔄 تنظيف تلقائي", callback_data="auto_cleanup")
            ],
            [
                InlineKeyboardButton(text="🔙 العودة للإعدادات", callback_data="settings")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    def get_admin_menu(self) -> InlineKeyboardMarkup:
        """قائمة الإدارة"""
        keyboard = [
            [
                InlineKeyboardButton(text="👥 إدارة المستخدمين", callback_data="admin_users"),
                InlineKeyboardButton(text="📊 إحصائيات النظام", callback_data="admin_stats")
            ],
            [
                InlineKeyboardButton(text="⚙️ إعدادات النظام", callback_data="admin_settings"),
                InlineKeyboardButton(text="🔧 صيانة النظام", callback_data="admin_maintenance")
            ],
            [
                InlineKeyboardButton(text="📋 سجلات النظام", callback_data="admin_logs"),
                InlineKeyboardButton(text="🆘 حالة النظام", callback_data="admin_health")
            ],
            [
                InlineKeyboardButton(text="🔙 العودة للقائمة الرئيسية", callback_data="main_menu")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    def get_support_menu(self) -> InlineKeyboardMarkup:
        """قائمة الدعم الفني"""
        keyboard = [
            [
                InlineKeyboardButton(text="📞 التواصل المباشر", callback_data="support_chat"),
                InlineKeyboardButton(text="📧 البريد الإلكتروني", callback_data="support_email")
            ],
            [
                InlineKeyboardButton(text="💬 مجموعة الدعم", callback_data="support_group"),
                InlineKeyboardButton(text="📱 قناة التحديثات", callback_data="updates_channel")
            ],
            [
                InlineKeyboardButton(text="🐛 الإبلاغ عن خطأ", callback_data="report_bug"),
                InlineKeyboardButton(text="💡 اقتراح ميزة", callback_data="suggest_feature")
            ],
            [
                InlineKeyboardButton(text="🔙 العودة للقائمة الرئيسية", callback_data="main_menu")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    def get_achievement_menu(self) -> InlineKeyboardMarkup:
        """قائمة الإنجازات"""
        keyboard = [
            [
                InlineKeyboardButton(text="🏆 الإنجازات المكتسبة", callback_data="achievements_earned"),
                InlineKeyboardButton(text="🎯 الإنجازات المتاحة", callback_data="achievements_available")
            ],
            [
                InlineKeyboardButton(text="📈 تقدم المستوى", callback_data="level_progress"),
                InlineKeyboardButton(text="⭐ النقاط والجوائز", callback_data="points_rewards")
            ],
            [
                InlineKeyboardButton(text="🔙 العودة للقائمة الرئيسية", callback_data="main_menu")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    def get_confirm_keyboard(self, action: str) -> InlineKeyboardMarkup:
        """لوحة تأكيد العملية"""
        keyboard = [
            [
                InlineKeyboardButton(text="✅ تأكيد", callback_data=f"confirm_{action}"),
                InlineKeyboardButton(text="❌ إلغاء", callback_data="cancel_action")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    def get_pagination_keyboard(self, current_page: int, total_pages: int, action: str) -> InlineKeyboardMarkup:
        """لوحة التنقل بين الصفحات"""
        keyboard = []
        
        # أزرار التنقل
        nav_buttons = []
        if current_page > 1:
            nav_buttons.append(InlineKeyboardButton(text="◀️ السابق", callback_data=f"{action}_page_{current_page-1}"))
        
        nav_buttons.append(InlineKeyboardButton(text=f"📄 {current_page}/{total_pages}", callback_data="current_page"))
        
        if current_page < total_pages:
            nav_buttons.append(InlineKeyboardButton(text="▶️ التالي", callback_data=f"{action}_page_{current_page+1}"))
        
        keyboard.append(nav_buttons)
        
        # زر العودة
        keyboard.append([InlineKeyboardButton(text="🔙 العودة", callback_data="back_to_main")])
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard)


# إنشاء نسخة عامة
inline_keyboards = InlineKeyboards()