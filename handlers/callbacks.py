"""
Callback query handlers for inline keyboard interactions
Handles all button presses and interactive elements
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
        progress_tracker: ProgressTracker
    ):
        self.downloader = downloader
        self.file_manager = file_manager
        self.progress_tracker = progress_tracker
        
        # Track active downloads per user
        self.user_downloads: Dict[int, Dict[str, Any]] = {}
    
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
