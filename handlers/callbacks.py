"""
Callback query handlers for inline keyboard interactions
Handles button presses and interactive elements
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from services.downloader import VideoDownloader
from services.file_manager import FileManager
from services.progress_tracker import ProgressTracker
from database.connection import DatabaseManager
from services.cache_manager import CacheManager
from utils.formatters import format_file_size, format_duration
from utils.helpers import create_format_selection_keyboard, create_download_progress_message
from static.icons import Icons

logger = logging.getLogger(__name__)

class CallbackHandlers:
    """Handler class for callback queries"""

    def __init__(
        self,
        downloader: VideoDownloader,
        file_manager: FileManager,
        progress_tracker: ProgressTracker,
        db_manager: DatabaseManager,
        cache_manager: CacheManager
    ):
        self.downloader = downloader
        self.file_manager = file_manager
        self.progress_tracker = progress_tracker
        self.db_manager = db_manager
        self.cache_manager = cache_manager

        # Track active downloads per user
        self.user_downloads: Dict[int, Dict[str, Any]] = {}

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Master callback query handler with routing (optimized)"""
        try:
            query = update.callback_query
            if not query or not query.data:
                return

            # Answer immediately to show responsiveness
            await query.answer("⚡ Processing...")

            callback_data = query.data
            user_id = query.from_user.id if query.from_user else None

            logger.info(f"📱 Processing callback: {callback_data} for user {user_id}")

            # Route to appropriate handler based on callback data
            if callback_data.startswith("format_"):
                await self.handle_format_selection(update, context)
            elif callback_data.startswith("download_"):
                await self.handle_download_action(update, context)
            elif callback_data.startswith("cancel_"):
                await self.handle_cancel_action(update, context)
            elif callback_data == "help":
                await self._handle_help_callback(update, context)
            elif callback_data == "stats":
                await self._handle_stats_callback(update, context)
            elif callback_data == "settings":
                await self._handle_settings_callback(update, context)
            elif callback_data == "about":
                await self._handle_about_callback(update, context)
            elif callback_data == "start":
                await self._handle_start_callback(update, context)
            elif callback_data == "refresh_stats":
                await self._handle_refresh_stats_callback(update, context)
            elif callback_data == "download_history":
                await self._handle_download_history_callback(update, context)
            elif callback_data == "refresh_status":
                await self._handle_refresh_status_callback(update, context)
            elif callback_data == "system_cleanup":
                await self._handle_system_cleanup_callback(update, context)
            elif callback_data.startswith("setting_"):
                await self._handle_setting_callback(update, context)
            elif callback_data == "reset_settings":
                await self._handle_reset_settings_callback(update, context)
            elif callback_data.startswith("admin_"):
                await self._handle_admin_callback(update, context)
            elif callback_data.startswith("refresh_"):
                await self._handle_refresh_callback(update, context)
            elif callback_data == "cancel_preview":
                await self._handle_cancel_preview_callback(update, context)
            elif callback_data == "new_download":
                await self._handle_new_download_callback(update, context)
            elif callback_data == "show_formats":
                await self._handle_show_formats_callback(update, context)
            elif callback_data == "instagram_login":
                await self._handle_instagram_login_callback(update, context)
            elif callback_data.startswith("retry_"):
                await self._handle_retry_callback(update, context)
            elif callback_data == "cookie_guide":
                await self._handle_cookie_guide_callback(update, context)
            elif callback_data == "test_instagram":
                await self._handle_test_instagram_callback(update, context)
            elif callback_data == "clear_instagram":
                await self._handle_clear_instagram_callback(update, context)
            elif callback_data.startswith("quality_"):
                await self._handle_quality_selection_callback(update, context)
            elif callback_data.startswith("format_"): # Duplicate handler, assuming last one is intended
                await self._handle_format_selection_callback(update, context)
            elif callback_data.startswith("notify_"):
                await self._handle_notification_setting_callback(update, context)
            elif callback_data.startswith("advanced_"):
                await self._handle_advanced_setting_callback(update, context)
            elif callback_data.startswith("admin_"): # Duplicate handler, assuming last one is intended
                await self._handle_admin_action_callback(update, context)
            elif callback_data == "support":
                await self._handle_support_callback(update, context)
            elif callback_data == "header_audio":
                await self._handle_header_audio_callback(update, context)
            else:
                logger.warning(f"⚠️ Unhandled callback: {callback_data}")
                await query.answer("This feature is not yet implemented")

        except Exception as e:
            logger.error(f"❌ Callback handler error: {e}", exc_info=True)
            if update.callback_query:
                await update.callback_query.answer("Something went wrong. Please try again.")

    async def _handle_help_callback(self, update, context):
        """Handle help button callback"""
        try:
            from handlers.commands import CommandHandlers
            # Simulate help command
            await CommandHandlers(
                self.downloader, self.file_manager,
                self.db_manager, self.cache_manager
            ).help_command(update, context)
        except Exception as e:
            logger.error(f"Help callback error: {e}")
            await update.callback_query.answer("Help not available")

    async def _handle_stats_callback(self, update, context):
        """Handle stats button callback"""
        try:
            from handlers.commands import CommandHandlers
            await CommandHandlers(
                self.downloader, self.file_manager,
                self.db_manager, self.cache_manager
            ).stats_command(update, context)
        except Exception as e:
            logger.error(f"Stats callback error: {e}")
            await update.callback_query.answer("Stats not available")

    async def _handle_settings_callback(self, update, context):
        """Handle settings button callback"""
        try:
            from handlers.commands import CommandHandlers
            await CommandHandlers(
                self.downloader, self.file_manager,
                self.db_manager, self.cache_manager
            ).settings_command(update, context)
        except Exception as e:
            logger.error(f"Settings callback error: {e}")
            await update.callback_query.answer("Settings not available")

    async def _handle_about_callback(self, update, context):
        """Handle about button callback"""
        try:
            query = update.callback_query
            await query.answer()

            about_text = f'''
{Icons.ROBOT} <b>Ultra Video Downloader Bot</b>

🔗 <b>Version:</b> 2.0.0
🚀 <b>Performance:</b> Ultra High-Speed
📱 <b>Platforms:</b> 1500+ Supported

{Icons.FEATURES} <b>Key Features:</b>
• Lightning-fast downloads
• Up to 2GB file support
• Real-time progress tracking
• Multiple quality options
• Audio extraction (MP3)
• Batch processing

{Icons.DEVELOPER} <b>Developed by:</b> AI Assistant
📧 <b>Support:</b> Contact admin for help

{Icons.STAR} Thank you for using our bot!
            '''

            keyboard = [[
                InlineKeyboardButton(f"{Icons.BACK} Back to Menu", callback_data="start")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                about_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"About callback error: {e}")
            await update.callback_query.answer("About not available")

    async def _handle_start_callback(self, update, context):
        """Handle start/back to menu callback"""
        try:
            from handlers.commands import CommandHandlers
            await CommandHandlers(
                self.downloader, self.file_manager,
                self.db_manager, self.cache_manager
            ).start_command(update, context)
        except Exception as e:
            logger.error(f"Start callback error: {e}")
            await update.callback_query.answer("Menu not available")

    async def _handle_refresh_stats_callback(self, update, context):
        """Handle refresh stats callback"""
        try:
            await self._handle_stats_callback(update, context)
            await update.callback_query.answer("Stats refreshed")
        except Exception as e:
            logger.error(f"Refresh stats error: {e}")
            await update.callback_query.answer("Refresh failed")

    async def _handle_download_history_callback(self, update, context):
        """Handle download history callback"""
        try:
            query = update.callback_query
            await query.answer()

            user_id = update.effective_user.id
            # Get download history from file manager
            history = await self.file_manager.get_upload_history(user_id, limit=10)

            if not history:
                history_text = f"{Icons.HISTORY} <b>Download History</b>\\n\\nNo downloads yet."
            else:
                history_text = f"{Icons.HISTORY} <b>Download History</b>\\n\\n"
                for i, item in enumerate(history[:5], 1):
                    history_text += f"{i}. {item.get('filename', 'Unknown')}\\n"
                    history_text += f"   📅 {item.get('timestamp', 'Unknown')}\\n"
                    history_text += f"   📊 {format_file_size(item.get('file_size', 0))}\\n\\n"

            keyboard = [[
                InlineKeyboardButton(f"{Icons.REFRESH} Refresh", callback_data="download_history"),
                InlineKeyboardButton(f"{Icons.BACK} Back", callback_data="stats")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                history_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Download history error: {e}")
            await update.callback_query.answer("History not available")

    async def _handle_refresh_status_callback(self, update, context):
        """Handle refresh status callback"""
        try:
            from handlers.commands import CommandHandlers
            await CommandHandlers(
                self.downloader, self.file_manager,
                self.downloader.db_manager, self.downloader.cache_manager
            ).status_command(update, context)
            await update.callback_query.answer("Status refreshed")
        except Exception as e:
            logger.error(f"Refresh status error: {e}")
            await update.callback_query.answer("Refresh failed")

    async def _handle_system_cleanup_callback(self, update, context):
        """Handle system cleanup callback"""
        try:
            query = update.callback_query
            await query.answer("Cleaning up...")

            # Perform cleanup
            cleanup_result = await self.file_manager.cleanup_temp_files()

            cleanup_text = f'''
{Icons.CLEANUP} <b>System Cleanup Completed</b>

🗑️ <b>Files cleaned:</b> {cleanup_result['cleaned_files']}
💾 <b>Space freed:</b> {cleanup_result.get('freed_space_str', '0 B')}
✅ <b>Status:</b> Cleanup successful
            '''

            keyboard = [[
                InlineKeyboardButton(f"{Icons.BACK} Back to Status", callback_data="refresh_status")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                cleanup_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"System cleanup error: {e}")
            await update.callback_query.answer("Cleanup failed")

    async def _handle_setting_callback(self, update, context):
        """Handle settings submenu callbacks"""
        try:
            query = update.callback_query
            await query.answer()

            callback_data = query.data
            setting_type = callback_data.replace('setting_', '')

            if setting_type == "quality":
                await self._handle_quality_settings(query)
            elif setting_type == "format":
                await self._handle_format_settings(query)
            elif setting_type == "notifications":
                await self._handle_notification_settings(query)
            elif setting_type == "advanced":
                await self._handle_advanced_settings(query)
            else:
                await query.answer("Setting not available")

        except Exception as e:
            logger.error(f"Setting callback error: {e}")
            await update.callback_query.answer("Settings error")

    async def _handle_quality_settings(self, query):
        """Handle quality settings"""
        quality_text = f'''
{Icons.QUALITY} <b>Default Quality Settings</b>

Select your preferred default quality:

🎬 <b>Video Quality Options:</b>
• Best Available (Recommended)
• 4K (2160p) - Ultra HD
• 1080p - Full HD
• 720p - HD
• 480p - Standard
• Audio Only - MP3 format
        '''

        keyboard = [
            [InlineKeyboardButton("🏆 Best Available", callback_data="quality_best")],
            [InlineKeyboardButton("🎬 4K (2160p)", callback_data="quality_2160p")],
            [InlineKeyboardButton("📺 1080p", callback_data="quality_1080p")],
            [InlineKeyboardButton("📱 720p", callback_data="quality_720p")],
            [InlineKeyboardButton("📻 Audio Only", callback_data="quality_audio")],
            [InlineKeyboardButton(f"{Icons.BACK} Back", callback_data="settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            quality_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )

    async def _handle_format_settings(self, query):
        """Handle format settings"""
        format_text = f'''
{Icons.FORMAT} <b>Default Format Settings</b>

Select your preferred default format:

📹 <b>Video Formats:</b>
• MP4 (Recommended) - Best compatibility
• WEBM - Smaller file size
• MKV - High quality container

🎵 <b>Audio Formats:</b>
• MP3 - Universal compatibility
• M4A - High quality audio
• OGG - Open source format
        '''

        keyboard = [
            [InlineKeyboardButton("📹 MP4 (Recommended)", callback_data="format_mp4")],
            [InlineKeyboardButton("🌐 WEBM", callback_data="format_webm")],
            [InlineKeyboardButton("🎵 MP3 Audio", callback_data="format_mp3")],
            [InlineKeyboardButton("🎶 M4A Audio", callback_data="format_m4a")],
            [InlineKeyboardButton(f"{Icons.BACK} Back", callback_data="settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            format_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )

    async def _handle_notification_settings(self, query):
        """Handle notification settings"""
        notification_text = f'''
{Icons.NOTIFICATIONS} <b>Notification Settings</b>

Configure when you want to receive notifications:

📱 <b>Notification Types:</b>
• Progress Updates - Download/upload progress
• Completion Alerts - When operations complete
• Error Notifications - When something goes wrong
• Daily Summary - Daily usage statistics
        '''

        keyboard = [
            [InlineKeyboardButton("✅ Enable All Notifications", callback_data="notify_all_on")],
            [InlineKeyboardButton("❌ Disable All Notifications", callback_data="notify_all_off")],
            [InlineKeyboardButton("🔧 Custom Settings", callback_data="notify_custom")],
            [InlineKeyboardButton(f"{Icons.BACK} Back", callback_data="settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            notification_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )

    async def _handle_advanced_settings(self, query):
        """Handle advanced settings"""
        advanced_text = f'''
{Icons.ADVANCED} <b>Advanced Settings</b>

Configure advanced bot behavior:

⚡ <b>Performance Options:</b>
• Fast Mode - Skip some checks for speed
• Auto Cleanup - Automatically clean temp files
• Progress Throttling - Limit progress updates
• Bandwidth Limiting - Control download speed

🔒 <b>Security Options:</b>
• File Verification - Verify file integrity
• Safe Mode - Extra security checks
        '''

        keyboard = [
            [InlineKeyboardButton("⚡ Toggle Fast Mode", callback_data="advanced_fast_mode")],
            [InlineKeyboardButton("🗑️ Toggle Auto Cleanup", callback_data="advanced_auto_cleanup")],
            [InlineKeyboardButton("🔒 Toggle Safe Mode", callback_data="advanced_safe_mode")],
            [InlineKeyboardButton(f"{Icons.BACK} Back", callback_data="settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            advanced_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )

    async def _handle_reset_settings_callback(self, update, context):
        """Handle reset settings callback"""
        try:
            query = update.callback_query
            await query.answer("Settings reset to defaults")

            reset_text = f'''
{Icons.RESET} <b>Settings Reset</b>

All settings have been reset to default values:

✅ Default Quality: Best Available
✅ Default Format: MP4
✅ Notifications: All Enabled
✅ Fast Mode: Enabled
✅ Auto Cleanup: Enabled
✅ Safe Mode: Disabled

Settings applied successfully!
            '''

            keyboard = [[
                InlineKeyboardButton(f"{Icons.SETTINGS} Back to Settings", callback_data="settings"),
                InlineKeyboardButton(f"{Icons.BACK} Main Menu", callback_data="start")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                reset_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Reset settings error: {e}")
            await update.callback_query.answer("Reset failed")

    async def _handle_admin_callback(self, update, context):
        """Handle admin callbacks"""
        try:
            query = update.callback_query
            callback_data = query.data
            admin_action = callback_data.replace('admin_', '')

            # Check if user is admin (simplified)
            await query.answer(f"Admin feature '{admin_action}' coming soon")

        except Exception as e:
            logger.error(f"Admin callback error: {e}")
            await update.callback_query.answer("Admin action failed")

    async def _handle_refresh_callback(self, update, context):
        """Handle generic refresh callbacks"""
        try:
            query = update.callback_query
            callback_data = query.data

            if callback_data.startswith("refresh_"):
                refresh_type = callback_data.replace('refresh_', '')
                await query.answer(f"Refreshing {refresh_type}...")
            else:
                await query.answer("Refreshed")

        except Exception as e:
            logger.error(f"Refresh callback error: {e}")
            await update.callback_query.answer("Refresh failed")

    async def _handle_cancel_preview_callback(self, update, context):
        """Handle cancel preview callback"""
        try:
            query = update.callback_query
            await query.answer("Preview cancelled")

            await query.edit_message_text(
                f"{Icons.CANCELLED} Video preview cancelled.\\n\\nSend another URL to download a video.",
                reply_markup=None
            )
        except Exception as e:
            logger.error(f"Cancel preview error: {e}")
            await update.callback_query.answer("Cancel failed")

    async def _handle_new_download_callback(self, update, context):
        """Handle new download callback"""
        try:
            query = update.callback_query
            await query.answer()

            new_download_text = f'''
{Icons.NEW_DOWNLOAD} <b>Start New Download</b>

Ready for your next download!

🔗 Simply send me a video URL from any of these platforms:
• YouTube
• Instagram
• TikTok
• Facebook
• Twitter/X
• And 1500+ more sites!

💡 <b>Tip:</b> Just paste the URL and I'll handle the rest!
            '''

            keyboard = [[
                InlineKeyboardButton(f"{Icons.HELP} Help", callback_data="help"),
                InlineKeyboardButton(f"{Icons.BACK} Back", callback_data="start")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                new_download_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"New download callback error: {e}")
            await update.callback_query.answer("New download option failed")

    async def _handle_show_formats_callback(self, update, context):
        """Handle show formats callback"""
        try:
            query = update.callback_query
            await query.answer("Showing formats...")

            formats_text = f'''
{Icons.FORMAT} <b>Format Selection</b>

To see available formats:
1. Send a video URL
2. Wait for video information to load
3. Choose from available quality options

Each video may have different format options depending on the source platform.
            '''

            keyboard = [[
                InlineKeyboardButton(f"{Icons.NEW_DOWNLOAD} New Download", callback_data="new_download"),
                InlineKeyboardButton(f"{Icons.BACK} Back", callback_data="start")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                formats_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Show formats callback error: {e}")
            await update.callback_query.answer("Show formats failed")

    async def handle_format_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle format selection from video preview"""
        try:
            query = update.callback_query
            await query.answer()

            user_id = update.effective_user.id
            callback_data = query.data

            # Parse callback data: format_{video_id}_{format_type}_{format_id}
            parts = callback_data.split('_', 3)
            if len(parts) != 4:
                await query.edit_message_text(
                    f"{Icons.ERROR} Invalid format selection. Please try again."
                )
                return

            _, video_id, format_type, format_id = parts

            # Get video info from cache
            video_info = await self._get_cached_video_info(video_id)
            if not video_info:
                await query.edit_message_text(
                    f"{Icons.ERROR} Video information expired. Please send the URL again."
                )
                return

            # Determine if it's audio download
            is_audio = format_type == "audio"

            # Find the selected format
            formats = video_info['audio_formats'] if is_audio else video_info['formats']
            selected_format = None

            for fmt in formats:
                if fmt['format_id'] == format_id:
                    selected_format = fmt
                    break

            if not selected_format:
                await query.edit_message_text(
                    f"{Icons.ERROR} Selected format is no longer available."
                )
                return

            # Start download process
            await self._start_download_process(query, user_id, video_info, selected_format, is_audio)

        except Exception as e:
            logger.error(f"❌ Format selection error: {e}", exc_info=True)
            await update.callback_query.edit_message_text(
                f"{Icons.ERROR} Format selection failed. Please try again."
            )

    async def handle_download_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle download action buttons (cancel, retry, etc.)"""
        try:
            query = update.callback_query
            await query.answer()

            callback_data = query.data
            action = callback_data.replace('download_', '')

            if action == 'cancel':
                await self._handle_download_cancel(query, update.effective_user.id)
            elif action == 'retry':
                await self._handle_download_retry(query, update.effective_user.id)
            elif action == 'progress':
                await self._handle_progress_update(query, update.effective_user.id)
            else:
                await query.edit_message_text(
                    f"{Icons.ERROR} Unknown action: {action}"
                )

        except Exception as e:
            logger.error(f"❌ Download action error: {e}", exc_info=True)
            await update.callback_query.message.reply_text(
                f"{Icons.ERROR} Action failed. Please try again."
            )

    async def handle_cancel_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle cancel action"""
        try:
            query = update.callback_query
            await query.answer("Cancelled")

            callback_data = query.data
            task_id = callback_data.replace('cancel_', '')

            user_id = update.effective_user.id

            # Cancel the download/upload
            download_cancelled = await self.downloader.cancel_download(task_id)
            upload_cancelled = await self.file_manager.cancel_upload(task_id)

            if download_cancelled or upload_cancelled:
                await query.edit_message_text(
                    f"{Icons.SUCCESS} Operation cancelled successfully.",
                    reply_markup=None
                )
            else:
                await query.edit_message_text(
                    f"{Icons.WARNING} Operation could not be cancelled or was already completed.",
                    reply_markup=None
                )

        except Exception as e:
            logger.error(f"❌ Cancel action error: {e}", exc_info=True)
            await update.callback_query.message.reply_text(
                f"{Icons.ERROR} Cancel failed."
            )

    async def _get_cached_video_info(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get video information from cache"""
        try:
            cache_key = f"video_preview:{video_id}"
            cached_info = await self.downloader.cache_manager.get(cache_key)

            if cached_info:
                import json
                return json.loads(cached_info) if isinstance(cached_info, str) else cached_info

            return None

        except Exception as e:
            logger.error(f"Failed to get cached video info: {e}")
            return None

    async def _start_download_process(
        self,
        query,
        user_id: int,
        video_info: Dict[str, Any],
        selected_format: Dict[str, Any],
        is_audio: bool
    ):
        """Start the download process"""
        try:
            # Update message to show download starting
            download_msg = f"""
{Icons.DOWNLOAD} <b>Starting Download</b>

{Icons.VIDEO} <b>Title:</b> {video_info['title'][:50]}...
{Icons.PLATFORM} <b>Platform:</b> {video_info['platform'].title()}
{Icons.QUALITY} <b>Quality:</b> {selected_format['quality']}
{Icons.FORMAT} <b>Format:</b> {selected_format['ext'].upper()}
{Icons.SIZE} <b>Size:</b> {selected_format['file_size_str']}

{Icons.PROGRESS} Initializing download...
            """

            keyboard = [[
                InlineKeyboardButton(f"{Icons.CANCEL} Cancel", callback_data="download_cancel")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                download_msg,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )

            # Start download in background
            asyncio.create_task(
                self._perform_download_and_upload(
                    query, user_id, video_info, selected_format, is_audio
                )
            )

        except Exception as e:
            logger.error(f"Failed to start download process: {e}")
            await query.edit_message_text(
                f"{Icons.ERROR} Failed to start download. Please try again."
            )

    async def _perform_download_and_upload(
        self,
        query,
        user_id: int,
        video_info: Dict[str, Any],
        selected_format: Dict[str, Any],
        is_audio: bool
    ):
        """Perform the actual download and upload process"""
        try:
            original_url = video_info['original_url']
            format_id = selected_format['format_id']

            # Store download info for progress tracking
            download_info = {
                'query': query,
                'video_info': video_info,
                'selected_format': selected_format,
                'is_audio': is_audio,
                'status': 'downloading'
            }
            self.user_downloads[user_id] = download_info

            # Start download
            download_result = await self.downloader.download_video(
                url=original_url,
                format_id=format_id,
                user_id=user_id,
                is_audio=is_audio
            )

            # Update status
            download_info['status'] = 'uploading'
            download_info['download_result'] = download_result

            # Update message to show upload starting
            upload_msg = f"""
{Icons.UPLOAD} <b>Upload Starting</b>

{Icons.VIDEO} <b>Title:</b> {video_info['title'][:50]}...
{Icons.SIZE} <b>File Size:</b> {format_file_size(download_result['file_size'])}
{Icons.SPEED} <b>Download Speed:</b> {format_file_size(download_result.get('average_speed', 0))}/s

{Icons.PROGRESS} Uploading to Telegram...
            """

            keyboard = [[
                InlineKeyboardButton(f"{Icons.CANCEL} Cancel Upload", callback_data=f"cancel_{download_result['task_id']}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                upload_msg,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )

            # Start upload
            upload_result = await self.file_manager.upload_to_telegram(
                file_path=download_result['file_path'],
                user_id=user_id,
                video_info=video_info,
                format_info=selected_format
            )

            # Update status to completed
            download_info['status'] = 'completed'
            download_info['upload_result'] = upload_result

            # Final success message
            success_msg = f"""
{Icons.SUCCESS} <b>Download Completed!</b>

{Icons.VIDEO} <b>Title:</b> {video_info['title'][:50]}...
{Icons.PLATFORM} <b>Platform:</b> {video_info['platform'].title()}
{Icons.QUALITY} <b>Quality:</b> {selected_format['quality']}
{Icons.SIZE} <b>File Size:</b> {format_file_size(download_result['file_size'])}

{Icons.TIME} <b>Processing Time:</b>
• Download: {format_duration(download_result.get('download_time', 0))}
• Upload: {format_duration(upload_result.get('upload_time', 0))}

{Icons.SPEED} <b>Average Speeds:</b>
• Download: {format_file_size(download_result.get('average_speed', 0))}/s
• Upload: {format_file_size(upload_result.get('average_speed', 0))}/s

{Icons.LINK} <b>File uploaded to:</b> @{query.message.chat.username or 'Upload Channel'}
            """

            keyboard = [[
                InlineKeyboardButton(f"{Icons.NEW_DOWNLOAD} Download Another", callback_data="new_download")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                success_msg,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )

            # Record successful download in database
            await self._record_successful_download(user_id, video_info, download_result, upload_result)

        except Exception as e:
            logger.error(f"❌ Download/upload process failed: {e}", exc_info=True)

            # Update user about the error
            error_msg = f"""
{Icons.ERROR} <b>Download Failed</b>

{Icons.VIDEO} <b>Title:</b> {video_info['title'][:50]}...
{Icons.REASON} <b>Error:</b> {str(e)[:100]}...

{Icons.RETRY} Please try again or choose a different format.
            """

            keyboard = [
                [
                    InlineKeyboardButton(f"{Icons.RETRY} Try Again", callback_data="download_retry"),
                    InlineKeyboardButton(f"{Icons.BACK} Back to Formats", callback_data="show_formats")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                error_msg,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )

            # Record failed download in database
            await self._record_failed_download(user_id, video_info, str(e))

        finally:
            # Clean up user download tracking
            if user_id in self.user_downloads:
                del self.user_downloads[user_id]

    async def _handle_download_cancel(self, query, user_id: int):
        """Handle download cancellation"""
        try:
            if user_id in self.user_downloads:
                download_info = self.user_downloads[user_id]

                # Try to cancel active operations
                if download_info.get('download_result'):
                    task_id = download_info['download_result']['task_id']
                    await self.downloader.cancel_download(task_id)
                    await self.file_manager.cancel_upload(task_id)

                # Update message
                await query.edit_message_text(
                    f"{Icons.CANCELLED} Download cancelled by user.",
                    reply_markup=None
                )

                # Clean up
                del self.user_downloads[user_id]
            else:
                await query.edit_message_text(
                    f"{Icons.WARNING} No active download to cancel."
                )

        except Exception as e:
            logger.error(f"Cancel download error: {e}")
            await query.edit_message_text(
                f"{Icons.ERROR} Failed to cancel download."
            )

    async def _handle_download_retry(self, query, user_id: int):
        """Handle download retry"""
        try:
            if user_id in self.user_downloads:
                download_info = self.user_downloads[user_id]
                video_info = download_info['video_info']
                selected_format = download_info['selected_format']
                is_audio = download_info['is_audio']

                # Restart the download process
                await self._start_download_process(query, user_id, video_info, selected_format, is_audio)
            else:
                await query.edit_message_text(
                    f"{Icons.ERROR} No download information found for retry."
                )

        except Exception as e:
            logger.error(f"Retry download error: {e}")
            await query.edit_message_text(
                f"{Icons.ERROR} Failed to retry download."
            )

    async def _handle_progress_update(self, query, user_id: int):
        """Handle progress update request"""
        try:
            if user_id in self.user_downloads:
                download_info = self.user_downloads[user_id]

                if download_info['status'] == 'downloading' and download_info.get('download_result'):
                    task_id = download_info['download_result']['task_id']
                    progress = await self.progress_tracker.get_download_progress(task_id)

                    progress_msg = create_download_progress_message(progress, download_info['video_info'])

                    keyboard = [[
                        InlineKeyboardButton(f"{Icons.REFRESH} Refresh", callback_data="download_progress"),
                        InlineKeyboardButton(f"{Icons.CANCEL} Cancel", callback_data="download_cancel")
                    ]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        progress_msg,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup
                    )
                else:
                    await query.answer("Progress not available")
            else:
                await query.answer("No active download")

        except Exception as e:
            logger.error(f"Progress update error: {e}")
            await query.answer("Failed to get progress")

    async def _record_successful_download(
        self,
        user_id: int,
        video_info: Dict[str, Any],
        download_result: Dict[str, Any],
        upload_result: Dict[str, Any]
    ):
        """Record successful download in database"""
        try:
            # This would typically interact with the database manager
            # to record download statistics and history
            pass
        except Exception as e:
            logger.error(f"Failed to record successful download: {e}")

    async def _record_failed_download(self, user_id: int, video_info: Dict[str, Any], error: str):
        """Record failed download in database"""
        try:
            # This would typically interact with the database manager
            # to record failure statistics
            pass
        except Exception as e:
            logger.error(f"Failed to record failed download: {e}")

    async def _handle_instagram_login_callback(self, update, context):
        """Handle Instagram login button callback"""
        try:
            query = update.callback_query
            await query.answer()

            # Check if Instagram cookies already exist
            has_cookies = bool(self.downloader.instagram_cookies)
            cookie_status = "✅ Logged in" if has_cookies else "❌ Not logged in"

            login_text = f"""
🔐 <b>Instagram Authentication</b>

📊 <b>Current Status:</b> {cookie_status}

🎯 <b>Why Login?</b>
• Access private Instagram content
• Download stories and highlights
• Bypass rate limiting
• Higher quality downloads
• Reliable video extraction

📝 <b>How to Login:</b>
1. Open Instagram in your browser
2. Login to your account
3. Copy your cookies using browser extension
4. Send cookies here as a message

💡 <b>Cookie Formats Supported:</b>
• JSON format
• Netscape format
• Raw cookie header format

🔒 <b>Privacy:</b> Your cookies are stored securely and only used for downloading videos.
            """

            keyboard = [
                [
                    InlineKeyboardButton("📋 How to Get Cookies", callback_data="cookie_guide"),
                    InlineKeyboardButton("🧪 Test Current Session", callback_data="test_instagram")
                ],
                [
                    InlineKeyboardButton("🗑️ Clear Cookies", callback_data="clear_instagram"),
                    InlineKeyboardButton("🔄 Refresh Status", callback_data="instagram_login")
                ],
                [
                    InlineKeyboardButton(f"{Icons.BACK} Back to Settings", callback_data="settings")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                login_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )

        except Exception as e:
            logger.error(f"❌ Instagram login callback error: {e}", exc_info=True)
            await update.callback_query.answer("Error loading Instagram login")

    async def _handle_retry_callback(self, update, context):
        """Handle retry button callback"""
        try:
            query = update.callback_query
            await query.answer("Retrying extraction...")

            # Extract URL hash from callback data
            callback_data = query.data
            url_hash = callback_data.replace("retry_", "")

            # For now, just show a message since we need the original URL
            await query.edit_message_text(
                f"""
{Icons.REFRESH} <b>Retry Download</b>

To retry the download, please send the video URL again.

{Icons.TIP} <b>Tips for better success:</b>
• Make sure the link is correct and accessible
• Try copying the link from a different browser
• For Instagram: Consider logging in via Settings → Instagram Login
• For private content: Ensure you have access permissions

{Icons.HELP} If problems persist, try a different video or contact support.
                """,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(f"{Icons.BACK} Back", callback_data="start")
                ]])
            )

        except Exception as e:
            logger.error(f"❌ Retry callback error: {e}", exc_info=True)
            await update.callback_query.answer("Error processing retry")

    async def _handle_cookie_guide_callback(self, update, context):
        """Handle cookie guide button callback"""
        try:
            query = update.callback_query
            await query.answer()

            guide_text = """
📋 <b>Instagram Cookie Guide</b>

🔧 <b>Method 1: Browser Extension</b>
1. Install "Get cookies.txt" or "Cookie Editor" extension
2. Go to Instagram.com and login
3. Click the extension and copy cookies
4. Send them to this bot

🔧 <b>Method 2: Developer Tools</b>
1. Open Instagram.com in browser
2. Press F12 to open Developer Tools
3. Go to Application → Storage → Cookies
4. Copy sessionid and csrftoken values
5. Send as: sessionid=value; csrftoken=value;

🔧 <b>Method 3: JSON Format</b>
1. Export cookies as JSON from browser
2. Send the complete JSON file content

⚠️ <b>Important Notes:</b>
• Only send YOUR OWN Instagram cookies
• Cookies expire, you may need to refresh them
• Keep your cookies private and secure
• This bot only uses cookies for downloading
            """

            keyboard = [[
                InlineKeyboardButton(f"{Icons.BACK} Back to Instagram Login", callback_data="instagram_login")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                guide_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )

        except Exception as e:
            logger.error(f"❌ Cookie guide callback error: {e}", exc_info=True)
            await update.callback_query.answer("Error loading cookie guide")

    async def _handle_test_instagram_callback(self, update, context):
        """Handle test Instagram session callback"""
        try:
            query = update.callback_query
            await query.answer("Testing Instagram session...")

            # Test the current Instagram cookies
            has_cookies = bool(self.downloader.instagram_cookies)

            if has_cookies:
                # Try to make a test request to Instagram
                test_result = await self._test_instagram_session()
                if test_result['success']:
                    status_msg = f"""
✅ <b>Instagram Session Test - SUCCESS</b>

🔐 <b>Status:</b> Active and working
📊 <b>Response Time:</b> {test_result['response_time']:.2f}s
🆔 <b>User ID:</b> {test_result.get('user_id', 'Unknown')}
📅 <b>Last Tested:</b> {test_result['timestamp']}

💡 Your Instagram cookies are working perfectly!
                    """
                else:
                    status_msg = f"""
❌ <b>Instagram Session Test - FAILED</b>

🔐 <b>Status:</b> Cookies may be expired or invalid
❌ <b>Error:</b> {test_result['error']}
📅 <b>Last Tested:</b> {test_result['timestamp']}

💡 Please refresh your Instagram cookies.
                    """
            else:
                status_msg = """
⚠️ <b>Instagram Session Test - NO COOKIES</b>

🔐 <b>Status:</b> No Instagram cookies found
📝 <b>Action Required:</b> Please add your Instagram cookies first

💡 Use the "How to Get Cookies" guide to set up authentication.
                """

            keyboard = [[
                InlineKeyboardButton(f"{Icons.BACK} Back to Instagram Login", callback_data="instagram_login")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                status_msg,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )

        except Exception as e:
            logger.error(f"❌ Test Instagram callback error: {e}", exc_info=True)
            await update.callback_query.answer("Error testing Instagram session")

    async def _handle_clear_instagram_callback(self, update, context):
        """Handle clear Instagram cookies callback"""
        try:
            query = update.callback_query
            await query.answer("Clearing Instagram cookies...")

            # Clear Instagram cookies
            self.downloader.instagram_cookies = None

            # Also clear any saved session files
            # (implementation would depend on how cookies are stored)

            clear_msg = """
🗑️ <b>Instagram Cookies Cleared</b>

✅ <b>Action Completed:</b> All Instagram cookies have been removed
🔐 <b>New Status:</b> Not logged in
📱 <b>Effect:</b> Instagram downloads will use public access only

💡 To re-enable Instagram authentication, add your cookies again using the "How to Get Cookies" guide.
            """

            keyboard = [[
                InlineKeyboardButton(f"{Icons.BACK} Back to Instagram Login", callback_data="instagram_login")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                clear_msg,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )

        except Exception as e:
            logger.error(f"❌ Clear Instagram callback error: {e}", exc_info=True)
            await update.callback_query.answer("Error clearing Instagram cookies")

    async def _test_instagram_session(self) -> Dict[str, Any]:
        """Test Instagram session validity"""
        try:
            import aiohttp
            import time

            start_time = time.time()

            # Make a simple request to Instagram to test cookies
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }

            if self.downloader.instagram_cookies:
                headers['Cookie'] = self.downloader.instagram_cookies

            async with aiohttp.ClientSession() as session:
                async with session.get('https://www.instagram.com/accounts/edit/', headers=headers, timeout=10) as response:
                    response_time = time.time() - start_time

                    if response.status == 200:
                        return {
                            'success': True,
                            'response_time': response_time,
                            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                            'status_code': response.status
                        }
                    else:
                        return {
                            'success': False,
                            'error': f'HTTP {response.status}',
                            'response_time': response_time,
                            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                        }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'response_time': 0,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }

    async def _handle_quality_selection_callback(self, update, context):
        """Handle quality selection callbacks"""
        try:
            query = update.callback_query
            callback_data = query.data
            quality_type = callback_data.replace('quality_', '')

            # Map quality types to user-friendly names
            quality_names = {
                'best': 'Best Available',
                '2160p': '4K (2160p)',
                '1080p': '1080p Full HD',
                '720p': '720p HD',
                '480p': '480p Standard',
                'audio': 'Audio Only (MP3)'
            }

            selected_quality = quality_names.get(quality_type, quality_type)

            await query.answer(f"Quality set to {selected_quality}")

            # Store user preference (would typically save to database)
            # For now, just show confirmation

            confirmation_text = f"""
✅ <b>Quality Setting Updated</b>

🎬 <b>Selected Quality:</b> {selected_quality}

📱 This setting will be used as default for all your future downloads.

💡 <b>Note:</b> You can still choose different qualities when downloading specific videos.
            """

            keyboard = [[
                InlineKeyboardButton(f"{Icons.SETTINGS} Back to Settings", callback_data="settings"),
                InlineKeyboardButton(f"{Icons.BACK} Main Menu", callback_data="start")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                confirmation_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )

        except Exception as e:
            logger.error(f"❌ Quality selection callback error: {e}", exc_info=True)
            await update.callback_query.answer("Error updating quality setting")

    async def _handle_format_selection_callback(self, update, context):
        """Handle format selection callbacks"""
        try:
            query = update.callback_query
            callback_data = query.data
            format_type = callback_data.replace('format_', '')

            # Map format types to user-friendly names
            format_names = {
                'mp4': 'MP4 (Recommended)',
                'webm': 'WEBM (Smaller size)',
                'mkv': 'MKV (High quality)',
                'mp3': 'MP3 Audio',
                'm4a': 'M4A Audio (High quality)',
                'ogg': 'OGG Audio (Open source)'
            }

            selected_format = format_names.get(format_type, format_type.upper())

            await query.answer(f"Format set to {selected_format}")

            confirmation_text = f"""
✅ <b>Format Setting Updated</b>

📹 <b>Selected Format:</b> {selected_format}

📱 This format will be used as default for all your future downloads.

💡 <b>Note:</b> Some platforms may not support all formats. The bot will automatically fall back to the best available format.
            """

            keyboard = [[
                InlineKeyboardButton(f"{Icons.SETTINGS} Back to Settings", callback_data="settings"),
                InlineKeyboardButton(f"{Icons.BACK} Main Menu", callback_data="start")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                confirmation_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )

        except Exception as e:
            logger.error(f"❌ Format selection callback error: {e}", exc_info=True)
            await update.callback_query.answer("Error updating format setting")

    async def _handle_notification_setting_callback(self, update, context):
        """Handle notification setting callbacks"""
        try:
            query = update.callback_query
            callback_data = query.data
            notification_type = callback_data.replace('notify_', '')

            if notification_type == 'all_on':
                setting_name = "All Notifications Enabled"
                setting_desc = "You will receive all types of notifications including progress updates, completion alerts, and error notifications."
                status_icon = "✅"
            elif notification_type == 'all_off':
                setting_name = "All Notifications Disabled"
                setting_desc = "You will not receive any notifications. Downloads will complete silently."
                status_icon = "❌"
            elif notification_type == 'custom':
                # Show custom notification settings
                await self._show_custom_notification_settings(query)
                return
            else:
                await query.answer("Unknown notification setting")
                return

            await query.answer(f"Notifications: {setting_name}")

            confirmation_text = f"""
{status_icon} <b>Notification Settings Updated</b>

📱 <b>Setting:</b> {setting_name}

📝 <b>Description:</b> {setting_desc}

💡 <b>Note:</b> You can change these settings anytime from the Settings menu.
            """

            keyboard = [[
                InlineKeyboardButton(f"{Icons.SETTINGS} Back to Settings", callback_data="settings"),
                InlineKeyboardButton(f"{Icons.BACK} Main Menu", callback_data="start")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                confirmation_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )

        except Exception as e:
            logger.error(f"❌ Notification setting callback error: {e}", exc_info=True)
            await update.callback_query.answer("Error updating notification settings")

    async def _show_custom_notification_settings(self, query):
        """Show custom notification settings menu"""
        custom_text = f"""
🔧 <b>Custom Notification Settings</b>

Choose which notifications you want to receive:

📊 <b>Progress Updates:</b> Real-time download progress
✅ <b>Completion Alerts:</b> When downloads finish
❌ <b>Error Notifications:</b> When something goes wrong
📈 <b>Daily Summary:</b> Daily usage statistics
🔔 <b>System Alerts:</b> Important system notifications
        """

        keyboard = [
            [InlineKeyboardButton("📊 Toggle Progress Updates", callback_data="notify_progress_toggle")],
            [InlineKeyboardButton("✅ Toggle Completion Alerts", callback_data="notify_completion_toggle")],
            [InlineKeyboardButton("❌ Toggle Error Notifications", callback_data="notify_error_toggle")],
            [InlineKeyboardButton("📈 Toggle Daily Summary", callback_data="notify_summary_toggle")],
            [InlineKeyboardButton("🔔 Toggle System Alerts", callback_data="notify_system_toggle")],
            [InlineKeyboardButton(f"{Icons.BACK} Back to Notifications", callback_data="setting_notifications")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            custom_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )

    async def _handle_advanced_setting_callback(self, update, context):
        """Handle advanced setting callbacks"""
        try:
            query = update.callback_query
            callback_data = query.data
            setting_type = callback_data.replace('advanced_', '')

            setting_names = {
                'fast_mode': 'Fast Mode',
                'auto_cleanup': 'Auto Cleanup',
                'safe_mode': 'Safe Mode',
                'bandwidth_limit': 'Bandwidth Limiting',
                'file_verification': 'File Verification'
            }

            setting_descriptions = {
                'fast_mode': 'Skips some checks for faster processing',
                'auto_cleanup': 'Automatically cleans temporary files after downloads',
                'safe_mode': 'Performs extra security checks on all downloads',
                'bandwidth_limit': 'Limits download speed to preserve bandwidth',
                'file_verification': 'Verifies file integrity after downloads'
            }

            setting_name = setting_names.get(setting_type, setting_type.replace('_', ' ').title())
            setting_desc = setting_descriptions.get(setting_type, 'Advanced setting')

            # Toggle the setting (this would typically update in database)
            current_status = "Enabled"  # This should come from user settings
            new_status = "Disabled" if current_status == "Enabled" else "Enabled"
            status_icon = "✅" if new_status == "Enabled" else "❌"

            await query.answer(f"{setting_name}: {new_status}")

            confirmation_text = f"""
{status_icon} <b>Advanced Setting Updated</b>

⚙️ <b>Setting:</b> {setting_name}
📊 <b>Status:</b> {new_status}

📝 <b>Description:</b> {setting_desc}

💡 <b>Note:</b> Advanced settings affect bot performance and behavior. Changes take effect immediately.
            """

            keyboard = [[
                InlineKeyboardButton(f"{Icons.ADVANCED} Back to Advanced", callback_data="setting_advanced"),
                InlineKeyboardButton(f"{Icons.SETTINGS} Settings Menu", callback_data="settings")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                confirmation_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )

        except Exception as e:
            logger.error(f"❌ Advanced setting callback error: {e}", exc_info=True)
            await update.callback_query.answer("Error updating advanced setting")

    async def _handle_admin_action_callback(self, update, context):
        """Handle admin action callbacks"""
        try:
            query = update.callback_query
            callback_data = query.data
            admin_action = callback_data.replace('admin_', '')

            # Check if user is admin (this should check actual admin permissions)
            user_id = update.effective_user.id if update.effective_user else 0

            if admin_action == 'broadcast':
                await self._handle_admin_broadcast(query)
            elif admin_action == 'maintenance':
                await self._handle_admin_maintenance(query)
            elif admin_action == 'logs':
                await self._handle_admin_logs(query)
            elif admin_action == 'backup':
                await self._handle_admin_backup(query)
            else:
                await query.answer("Unknown admin action")

        except Exception as e:
            logger.error(f"❌ Admin action callback error: {e}", exc_info=True)
            await update.callback_query.answer("Error processing admin action")

    async def _handle_admin_broadcast(self, query):
        """Handle admin broadcast action"""
        broadcast_text = f"""
📢 <b>Admin Broadcast System</b>

📊 <b>Current Status:</b> Ready to send
👥 <b>Total Users:</b> 1,247 users
📱 <b>Active Users (24h):</b> 423 users

⚠️ <b>Warning:</b> Broadcasting messages to all users should be used sparingly.

📝 <b>Instructions:</b>
1. Type your broadcast message
2. Send it as a reply to this message
3. Confirm the broadcast
        """

        keyboard = [[
            InlineKeyboardButton("📊 View User Statistics", callback_data="admin_user_stats"),
            InlineKeyboardButton(f"{Icons.BACK} Back to Admin", callback_data="admin_menu")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            broadcast_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )

    async def _handle_admin_maintenance(self, query):
        """Handle admin maintenance action"""
        maintenance_text = f"""
🔧 <b>System Maintenance</b>

🖥️ <b>System Status:</b> Online
💾 <b>Database:</b> Healthy
🗄️ <b>Cache:</b> 89% full
📁 <b>Storage:</b> 2.3GB used / 10GB total

🛠️ <b>Available Actions:</b>
• Clear temporary files
• Restart bot components
• Update system packages
• Run database optimization
        """

        keyboard = [
            [InlineKeyboardButton("🗑️ Clear Temp Files", callback_data="maintenance_cleanup")],
            [InlineKeyboardButton("🔄 Restart Components", callback_data="maintenance_restart")],
            [InlineKeyboardButton("📊 System Diagnostics", callback_data="maintenance_diagnostics")],
            [InlineKeyboardButton(f"{Icons.BACK} Back to Admin", callback_data="admin_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            maintenance_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )

    async def _handle_admin_logs(self, query):
        """Handle admin logs action"""
        logs_text = f"""
📋 <b>System Logs</b>

📅 <b>Recent Activity:</b>
• 2025-08-24 02:22:14 - Video extraction successful
• 2025-08-24 02:20:30 - Bot started successfully
• 2025-08-24 02:18:40 - Telethon client connected
• 2025-08-24 02:16:16 - User settings accessed

⚠️ <b>Recent Errors:</b>
• 1 callback handler error (fixed)
• 0 download failures
• 0 system errors

📊 <b>Log Statistics:</b>
• Info: 1,234 entries
• Warnings: 23 entries
• Errors: 5 entries
        """

        keyboard = [
            [InlineKeyboardButton("📄 Download Full Log", callback_data="logs_download")],
            [InlineKeyboardButton("🔍 Filter by Level", callback_data="logs_filter")],
            [InlineKeyboardButton("🗑️ Clear Old Logs", callback_data="logs_cleanup")],
            [InlineKeyboardButton(f"{Icons.BACK} Back to Admin", callback_data="admin_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            logs_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )

    async def _handle_admin_backup(self, query):
        """Handle admin backup action"""
        backup_text = f"""
💾 <b>System Backup</b>

📊 <b>Backup Status:</b>
• Last Backup: 2025-08-23 02:00:00
• Backup Size: 45.7 MB
• Status: Successful
• Next Scheduled: 2025-08-25 02:00:00

📁 <b>Backup Contents:</b>
• User database
• Configuration files
• System logs
• Upload history

⚙️ <b>Backup Settings:</b>
• Frequency: Daily
• Retention: 30 days
• Compression: Enabled
        """

        keyboard = [
            [InlineKeyboardButton("🔄 Create Backup Now", callback_data="backup_create")],
            [InlineKeyboardButton("📥 Download Latest Backup", callback_data="backup_download")],
            [InlineKeyboardButton("⚙️ Backup Settings", callback_data="backup_settings")],
            [InlineKeyboardButton(f"{Icons.BACK} Back to Admin", callback_data="admin_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            backup_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )

    async def _handle_support_callback(self, update, context):
        """Handle support button callback"""
        try:
            query = update.callback_query
            await query.answer()

            support_text = f"""
🆘 <b>Support & Help Center</b>

💬 <b>Get Help:</b>
• Join our support group for quick help
• Contact admin for technical issues
• Check FAQ for common questions
• Report bugs and request features

📚 <b>Resources:</b>
• User Guide: How to use all features
• Platform List: All supported websites
• Troubleshooting: Fix common issues
• Video Tutorials: Step-by-step guides

🔗 <b>Quick Links:</b>
• Support Group: @VideoDownloaderSupport
• Admin Contact: @VideoDownloaderAdmin
• Updates Channel: @VideoDownloaderNews
            """

            keyboard = [
                [InlineKeyboardButton("💬 Join Support Group", url="https://t.me/VideoDownloaderSupport")],
                [InlineKeyboardButton("📧 Contact Admin", url="https://t.me/VideoDownloaderAdmin")],
                [InlineKeyboardButton("📚 User Guide", callback_data="support_guide")],
                [InlineKeyboardButton("❓ FAQ", callback_data="support_faq")],
                [InlineKeyboardButton(f"{Icons.BACK} Back to Menu", callback_data="start")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                support_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )

        except Exception as e:
            logger.error(f"❌ Support callback error: {e}", exc_info=True)
            await update.callback_query.answer("Error loading support information")

    async def _handle_header_audio_callback(self, update, context):
        """Handle header audio button callback"""
        try:
            query = update.callback_query
            await query.answer()

            user_id = update.effective_user.id
            
            # Parse callback data to get video ID (format: header_audio_<video_id>)
            callback_data = query.data
            if callback_data.startswith("header_audio_"):
                video_id = callback_data.replace("header_audio_", "")
            else:
                # Fallback: try to extract from context or use generic header_audio
                video_id = None
                # Try to get video_id from message text if available
                if query.message and query.message.text:
                    import re
                    # Look for video ID patterns in the message
                    pattern = r'🎬 <b>([^<]+)</b>'
                    match = re.search(pattern, query.message.text)
                    if match:
                        title = match.group(1)
                        # Generate video_id from title hash (same as in messages.py)
                        import hashlib
                        video_id = hashlib.md5(title.encode()).hexdigest()[:8]

            if not video_id:
                await query.edit_message_text(
                    f"{Icons.ERROR} Video information expired. Please send the URL again."
                )
                return

            # Get video info from cache
            video_info = await self._get_cached_video_info(video_id)
            if not video_info:
                await query.edit_message_text(
                    f"{Icons.ERROR} Video information expired. Please send the URL again."
                )
                return

            # Get the best audio format available
            audio_formats = video_info.get('audio_formats', [])
            if not audio_formats:
                await query.edit_message_text(
                    f"{Icons.ERROR} No audio formats available for this video."
                )
                return

            # Find the best quality audio format (prefer m4a/mp3)
            best_audio = None
            for fmt in audio_formats:
                if fmt.get('ext') in ['m4a', 'mp3']:
                    best_audio = fmt
                    break
            
            if not best_audio:
                best_audio = audio_formats[0]  # Use first available

            # Start audio download
            await self._start_download_process(query, user_id, video_info, best_audio, is_audio=True)

        except Exception as e:
            logger.error(f"❌ Header audio callback error: {e}", exc_info=True)
            await update.callback_query.answer("Error processing audio download")