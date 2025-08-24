"""
Command handlers for the Telegram bot
Handles all bot commands like /start, /help, /stats, etc.
"""

import asyncio
import logging
from typing import Dict, Any, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from services.downloader import VideoDownloader
from services.file_manager import FileManager
from database.connection import DatabaseManager
from services.cache_manager import CacheManager
from config.settings import settings
from utils.formatters import format_file_size, format_duration, format_uptime
from utils.helpers import get_system_stats, create_welcome_message
from static.icons import Icons

logger = logging.getLogger(__name__)

class CommandHandlers:
    """Handler class for bot commands"""
    
    def __init__(
        self, 
        downloader: VideoDownloader, 
        file_manager: FileManager,
        db_manager: DatabaseManager,
        cache_manager: CacheManager
    ):
        self.downloader = downloader
        self.file_manager = file_manager
        self.db_manager = db_manager
        self.cache_manager = cache_manager
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
            user = update.effective_user
            chat = update.effective_chat
            
            if not user or not chat:
                logger.error("❌ No user or chat in update")
                return
                
            logger.info(f"📱 Start command from user {user.id} in chat {chat.id}")
            
            # Register user in database
            await self.db_manager.create_or_update_user(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                chat_id=chat.id
            )
            
            # Import interactive messages
            from utils.progress_animations import InteractiveMessages
            
            # Create beautiful animated welcome message
            welcome_msg = InteractiveMessages.get_welcome_message(user.first_name)
            
            # Create inline keyboard with main options
            keyboard = [
                [
                    InlineKeyboardButton(f"{Icons.HELP} Help", callback_data="help"),
                    InlineKeyboardButton(f"{Icons.STATS} Stats", callback_data="stats")
                ],
                [
                    InlineKeyboardButton(f"{Icons.SETTINGS} Settings", callback_data="settings"),
                    InlineKeyboardButton(f"{Icons.INFO} About", callback_data="about")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.message:
                await update.message.reply_text(
                    welcome_msg,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                    disable_web_page_preview=True
                )
            
        except Exception as e:
            logger.error(f"❌ Start command error: {e}", exc_info=True)
            if update.message:
                await update.message.reply_text(
                    f"{Icons.ERROR} Sorry, something went wrong. Please try again."
                )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        try:
            help_text = f"""
{Icons.ROBOT} <b>Ultra Video Downloader Bot</b>

{Icons.DOWNLOAD} <b>How to use:</b>
1. Send me any video URL from supported platforms
2. Choose your preferred quality and format
3. Get your video uploaded instantly!

{Icons.PLATFORMS} <b>Supported Platforms:</b>
• YouTube (all qualities up to 4K)
• Instagram (posts, reels, stories)
• TikTok (with/without watermark)
• Facebook (public videos)
• Twitter/X (videos and GIFs)
• And 1500+ other sites!

{Icons.FEATURES} <b>Features:</b>
• {Icons.SPEED} Lightning-fast downloads
• {Icons.QUALITY} Multiple quality options
• {Icons.AUDIO} Audio extraction (MP3)
• {Icons.PROGRESS} Real-time progress tracking
• {Icons.LARGE_FILE} Up to 2GB file support
• {Icons.BATCH} Batch processing
• {Icons.HISTORY} Download history

{Icons.COMMANDS} <b>Commands:</b>
/start - Start the bot
/help - Show this help message
/stats - View your statistics
/status - Check bot status
/cancel - Cancel current downloads
/settings - Bot settings

{Icons.TIP} <b>Tip:</b> Just send me a video URL and I'll handle the rest!

{Icons.SUPPORT} Need help? Contact support or check our FAQ.
            """
            
            keyboard = [
                [
                    InlineKeyboardButton(f"{Icons.BACK} Back to Menu", callback_data="start"),
                    InlineKeyboardButton(f"{Icons.STATS} My Stats", callback_data="stats")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    help_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                    disable_web_page_preview=True
                )
            else:
                if update.message:
                    await update.message.reply_text(
                        help_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup,
                        disable_web_page_preview=True
                    )
            
        except Exception as e:
            logger.error(f"❌ Help command error: {e}", exc_info=True)
            if update.effective_message:
                await update.effective_message.reply_text(
                    f"{Icons.ERROR} Sorry, couldn't load help information."
                )
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        try:
            user = update.effective_user
            if not user:
                logger.error("❌ No user in update")
                return
            user_id = user.id
            
            # Get user statistics from database
            user_stats = await self.db_manager.get_user_stats(user_id)
            
            # Get current progress
            user_progress = await self.downloader.progress_tracker.get_user_progress(user_id)
            
            # Get upload history
            upload_history = await self.file_manager.get_upload_history(user_id, limit=5)
            
            # Format statistics
            stats_text = f"""
{Icons.STATS} <b>Your Statistics</b>

{Icons.USER} <b>Profile:</b>
• User ID: <code>{user_id}</code>
• Member since: {user_stats.get('created_at', 'Unknown')}
• Last active: {user_stats.get('last_active', 'Now')}

{Icons.DOWNLOAD} <b>Downloads:</b>
• Total downloads: {user_stats.get('total_downloads', 0)}
• Successful: {user_stats.get('successful_downloads', 0)}
• Failed: {user_stats.get('failed_downloads', 0)}
• Success rate: {user_stats.get('success_rate', 0):.1f}%

{Icons.DATA} <b>Data Usage:</b>
• Total downloaded: {format_file_size(user_stats.get('total_bytes_downloaded', 0))}
• Total uploaded: {format_file_size(user_stats.get('total_bytes_uploaded', 0))}
• Average file size: {format_file_size(user_stats.get('avg_file_size', 0))}

{Icons.SPEED} <b>Performance:</b>
• Average download speed: {format_file_size(user_stats.get('avg_download_speed', 0))}/s
• Average upload speed: {format_file_size(user_stats.get('avg_upload_speed', 0))}/s
• Fastest download: {format_file_size(user_stats.get('fastest_download_speed', 0))}/s

{Icons.TIME} <b>Time Stats:</b>
• Total download time: {format_duration(user_stats.get('total_download_time', 0))}
• Total upload time: {format_duration(user_stats.get('total_upload_time', 0))}
• Average processing time: {format_duration(user_stats.get('avg_processing_time', 0))}
            """
            
            # Add current activity if any
            if user_progress['total_active'] > 0:
                stats_text += f"\n{Icons.PROGRESS} <b>Current Activity:</b>\n"
                stats_text += f"• Active downloads: {len(user_progress['downloads'])}\n"
                stats_text += f"• Active uploads: {len(user_progress['uploads'])}"
            
            keyboard = [
                [
                    InlineKeyboardButton(f"{Icons.REFRESH} Refresh", callback_data="refresh_stats"),
                    InlineKeyboardButton(f"{Icons.HISTORY} History", callback_data="download_history")
                ],
                [
                    InlineKeyboardButton(f"{Icons.BACK} Back", callback_data="start")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    stats_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup
                )
            else:
                if update.message:
                    await update.message.reply_text(
                        stats_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup
                    )
            
        except Exception as e:
            logger.error(f"❌ Stats command error: {e}", exc_info=True)
            if update.effective_message:
                await update.effective_message.reply_text(
                    f"{Icons.ERROR} Sorry, couldn't load statistics."
                )
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command - show bot system status"""
        try:
            # Get system statistics
            system_stats = get_system_stats()
            
            # Get service performance stats
            downloader_stats = await self.downloader.get_performance_stats()
            file_manager_stats = await self.file_manager.get_performance_stats()
            cache_stats = await self.cache_manager.get_cache_info()
            
            # Get database stats
            db_stats = await self.db_manager.get_database_stats()
            
            status_text = f"""
{Icons.STATUS} <b>Bot System Status</b>

{Icons.SERVER} <b>System Resources:</b>
• CPU Usage: {system_stats.get('cpu_percent', 0):.1f}%
• RAM Usage: {system_stats.get('memory_percent', 0):.1f}%
• Available RAM: {format_file_size(system_stats.get('available_memory', 0))}
• Disk Usage: {system_stats.get('disk_percent', 0):.1f}%
• Uptime: {format_uptime(system_stats.get('uptime', 0))}

{Icons.DOWNLOAD} <b>Download Service:</b>
• Active downloads: {downloader_stats.get('active_downloads', 0)}/{settings.MAX_CONCURRENT_DOWNLOADS}
• Queue size: {downloader_stats.get('queue_size', 0)}
• Temp directory: {format_file_size(downloader_stats.get('temp_dir_size', 0))}

{Icons.UPLOAD} <b>Upload Service:</b>
• Active uploads: {file_manager_stats.get('active_uploads', 0)}/{settings.MAX_CONCURRENT_UPLOADS}
• Queue size: {file_manager_stats.get('upload_queue_size', 0)}
• Completed uploads: {file_manager_stats.get('total_uploads_completed', 0)}

{Icons.CACHE} <b>Cache Service:</b>
• Status: {'✅ Connected' if cache_stats.get('connected') else '❌ Disconnected'}
• Type: {cache_stats.get('type', 'Unknown').title()}
• Hit rate: {cache_stats.get('hit_rate', 0):.1f}%
• Used memory: {cache_stats.get('used_memory_human', 'Unknown')}

{Icons.DATABASE} <b>Database:</b>
• Status: {'✅ Connected' if db_stats.get('connected') else '❌ Disconnected'}
• Total users: {db_stats.get('total_users', 0):,}
• Total downloads: {db_stats.get('total_downloads', 0):,}
• Database size: {format_file_size(db_stats.get('database_size', 0))}
            """
            
            keyboard = [
                [
                    InlineKeyboardButton(f"{Icons.REFRESH} Refresh", callback_data="refresh_status"),
                    InlineKeyboardButton(f"{Icons.CLEANUP} Cleanup", callback_data="system_cleanup")
                ],
                [
                    InlineKeyboardButton(f"{Icons.BACK} Back", callback_data="start")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    status_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup
                )
            else:
                if update.message:
                    await update.message.reply_text(
                        status_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup
                    )
            
        except Exception as e:
            logger.error(f"❌ Status command error: {e}", exc_info=True)
            if update.effective_message:
                await update.effective_message.reply_text(
                    f"{Icons.ERROR} Sorry, couldn't load system status."
                )
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cancel command - cancel user's active operations"""
        try:
            user = update.effective_user
            if not user:
                logger.error("❌ No user in update")
                return
            user_id = user.id
            
            # Get user's active progress
            user_progress = await self.downloader.progress_tracker.get_user_progress(user_id)
            
            if user_progress['total_active'] == 0:
                if update.message:
                    await update.message.reply_text(
                        f"{Icons.INFO} No active downloads or uploads to cancel."
                    )
                return
            
            # Cancel all active downloads and uploads
            cancelled_count = 0
            
            for download in user_progress['downloads']:
                task_id = download['task_id']
                if await self.downloader.cancel_download(task_id):
                    cancelled_count += 1
            
            for upload in user_progress['uploads']:
                task_id = upload['task_id']
                if await self.file_manager.cancel_upload(task_id):
                    cancelled_count += 1
            
            if cancelled_count > 0:
                if update.message:
                    await update.message.reply_text(
                        f"{Icons.SUCCESS} Cancelled {cancelled_count} active operation(s)."
                    )
            else:
                if update.message:
                    await update.message.reply_text(
                        f"{Icons.WARNING} No operations could be cancelled."
                    )
            
        except Exception as e:
            logger.error(f"❌ Cancel command error: {e}", exc_info=True)
            if update.message:
                await update.message.reply_text(
                    f"{Icons.ERROR} Sorry, couldn't cancel operations."
                )
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /settings command"""
        try:
            user = update.effective_user
            if not user:
                logger.error("❌ No user in update")
                return
            user_id = user.id
            
            # Get user settings from database
            user_settings = await self.db_manager.get_user_settings(user_id)
            
            settings_text = f"""
{Icons.SETTINGS} <b>Your Settings</b>

{Icons.QUALITY} <b>Default Quality:</b>
Current: {user_settings.get('default_quality', 'Best Available')}

{Icons.FORMAT} <b>Default Format:</b>
Current: {user_settings.get('default_format', 'MP4')}

{Icons.NOTIFICATIONS} <b>Notifications:</b>
• Progress updates: {'✅ Enabled' if user_settings.get('progress_notifications', True) else '❌ Disabled'}
• Completion alerts: {'✅ Enabled' if user_settings.get('completion_notifications', True) else '❌ Disabled'}
• Error notifications: {'✅ Enabled' if user_settings.get('error_notifications', True) else '❌ Disabled'}

{Icons.ADVANCED} <b>Advanced:</b>
• Auto-cleanup: {'✅ Enabled' if user_settings.get('auto_cleanup', True) else '❌ Disabled'}
• Fast mode: {'✅ Enabled' if user_settings.get('fast_mode', True) else '❌ Disabled'}
• Thumbnail generation: {'✅ Enabled' if user_settings.get('generate_thumbnails', True) else '❌ Disabled'}
            """
            
            keyboard = [
                [
                    InlineKeyboardButton(f"{Icons.QUALITY} Quality", callback_data="setting_quality"),
                    InlineKeyboardButton(f"{Icons.FORMAT} Format", callback_data="setting_format")
                ],
                [
                    InlineKeyboardButton(f"{Icons.NOTIFICATIONS} Notifications", callback_data="setting_notifications"),
                    InlineKeyboardButton(f"{Icons.ADVANCED} Advanced", callback_data="setting_advanced")
                ],
                [
                    InlineKeyboardButton(f"{Icons.RESET} Reset to Defaults", callback_data="reset_settings"),
                ],
                [
                    InlineKeyboardButton(f"{Icons.BACK} Back", callback_data="start")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    settings_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text(
                    settings_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup
                )
            
        except Exception as e:
            logger.error(f"❌ Settings command error: {e}", exc_info=True)
            await update.effective_message.reply_text(
                f"{Icons.ERROR} Sorry, couldn't load settings."
            )
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin commands (only for admin users)"""
        try:
            user = update.effective_user
            if not user:
                logger.error("❌ No user in update")
                return
            user_id = user.id
            
            # Check if user is admin
            if user_id not in settings.ADMIN_USER_IDS:
                await update.message.reply_text(
                    f"{Icons.ERROR} Access denied. Admin privileges required."
                )
                return
            
            # Get global statistics
            global_stats = await self.db_manager.get_global_stats()
            system_stats = get_system_stats()
            
            admin_text = f"""
{Icons.ADMIN} <b>Admin Dashboard</b>

{Icons.USERS} <b>Users:</b>
• Total users: {global_stats.get('total_users', 0):,}
• Active today: {global_stats.get('active_today', 0):,}
• New users (24h): {global_stats.get('new_users_24h', 0):,}

{Icons.DOWNLOADS} <b>Downloads:</b>
• Total downloads: {global_stats.get('total_downloads', 0):,}
• Successful: {global_stats.get('successful_downloads', 0):,}
• Failed: {global_stats.get('failed_downloads', 0):,}
• Success rate: {global_stats.get('global_success_rate', 0):.1f}%

{Icons.DATA} <b>Data Transfer:</b>
• Total data processed: {format_file_size(global_stats.get('total_data_processed', 0))}
• Data today: {format_file_size(global_stats.get('data_today', 0))}
• Average per user: {format_file_size(global_stats.get('avg_per_user', 0))}

{Icons.PERFORMANCE} <b>Performance:</b>
• Average speed: {format_file_size(global_stats.get('avg_speed', 0))}/s
• Peak speed: {format_file_size(global_stats.get('peak_speed', 0))}/s
• System load: {system_stats.get('cpu_percent', 0):.1f}%
            """
            
            keyboard = [
                [
                    InlineKeyboardButton(f"{Icons.BROADCAST} Broadcast", callback_data="admin_broadcast"),
                    InlineKeyboardButton(f"{Icons.MAINTENANCE} Maintenance", callback_data="admin_maintenance")
                ],
                [
                    InlineKeyboardButton(f"{Icons.LOGS} View Logs", callback_data="admin_logs"),
                    InlineKeyboardButton(f"{Icons.BACKUP} Backup", callback_data="admin_backup")
                ],
                [
                    InlineKeyboardButton(f"{Icons.BACK} Back", callback_data="start")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                admin_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"❌ Admin command error: {e}", exc_info=True)
            await update.message.reply_text(
                f"{Icons.ERROR} Sorry, couldn't load admin dashboard."
            )
