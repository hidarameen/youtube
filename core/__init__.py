"""
Core Module - النواة الأساسية للمشروع الضخم
بوت تحميل يوتيوب وتلجرام المتطور
"""

__version__ = "2.0.0"
__author__ = "YouTube Telegram Bot Team"
__description__ = "مشروع ضخم ومتطور لبوت تحميل فيديوهات يوتيوب ورفعها إلى تلجرام"

from .config import Config
from .database import DatabaseManager
from .downloader import DownloadManager
from .uploader import UploadManager
from .bot import TelegramBot
from .userbot import UserBot

__all__ = [
    "Config",
    "DatabaseManager", 
    "DownloadManager",
    "UploadManager",
    "TelegramBot",
    "UserBot"
]