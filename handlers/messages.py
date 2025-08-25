"""
Message handlers for processing user messages
Handles URL detection, video preview generation, and user interactions
"""

import asyncio
import logging
import hashlib
import json
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from services.downloader import VideoDownloader
from services.cache_manager import CacheManager
from services.progress_tracker import ProgressTracker
from utils.validators import is_valid_url, get_platform_from_url
from utils.formatters import format_file_size, format_duration, format_view_count
from utils.helpers import create_format_selection_keyboard, truncate_text
from static.icons import Icons

logger = logging.getLogger(__name__)

class MessageHandlers:
    """Handler class for user messages"""
    
    def __init__(
        self, 
        downloader: VideoDownloader, 
        cache_manager: CacheManager,
        progress_tracker: ProgressTracker
    ):
        self.downloader = downloader
        self.cache_manager = cache_manager
        self.progress_tracker = progress_tracker
    
    async def handle_url_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle messages containing video URLs"""
        try:
            user = update.effective_user
            message = update.message
            text = message.text.strip()
            
            logger.info(f"📝 Processing URL message from user {user.id}: {text[:100]}...")
            
            # Validate URL
            if not is_valid_url(text):
                await self._send_invalid_url_message(message)
                return
            
            # Check if platform is supported
            platform = get_platform_from_url(text)
            if not platform:
                await self._send_unsupported_platform_message(message)
                return
            
            # Import animations
            from utils.progress_animations import InteractiveMessages, progress_animator
            
            # Send simple fast processing message
            processing_message = await message.reply_text(
                f"🔄 معالجة الرابط...",
                parse_mode=ParseMode.HTML
            )
            
            try:
                # Extract video information
                video_info = await self.downloader.get_video_info(text, user.id)
                
                # Update message with success animation
                from utils.progress_animations import InteractiveMessages
                success_progress = progress_animator.get_animated_progress_bar(100, f"extract_{user.id}", "pulse")
                success_text = f"""
{Icons.SUCCESS} <b>Video information extracted successfully!</b>

{Icons.VIDEO} <b>Title:</b> {video_info.get('title', 'Untitled Video')[:50]}...
{Icons.TIMER} <b>Duration:</b> {video_info.get('duration_string', 'Unknown')}
{Icons.PLATFORMS} <b>Platform:</b> {platform.title()}

{success_progress}

{Icons.SPARKLES} <i>Choose your preferred quality and format...</i>
                """
                
                # Generate video preview immediately
                await self._send_video_preview(processing_message, video_info, text)
                
            except Exception as e:
                logger.error(f"❌ Video info extraction failed: {e}", exc_info=True)
                # Send beautiful error message with animation
                error_progress = progress_animator.get_animated_progress_bar(0, f"error_{user.id}", "default")
                error_text = InteractiveMessages.get_error_message(
                    str(e), 
                    f"\n{Icons.TIP} <b>Suggestions:</b>\n• Make sure the link is correct\n• Try a link from another platform\n• Retry after a moment"
                )
                
                # Create shorter callback data to avoid Telegram limits
                url_hash = hashlib.md5(text.encode()).hexdigest()[:8]
                
                retry_keyboard = [[
                    InlineKeyboardButton(f"{Icons.REFRESH} Retry", callback_data=f"retry_{url_hash}")
                ]]
                
                await processing_message.edit_text(
                    error_text, 
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(retry_keyboard)
                )
            
        except Exception as e:
            logger.error(f"❌ URL message handling error: {e}", exc_info=True)
            await message.reply_text(
                f"{Icons.ERROR} Sorry, something went wrong while processing your request."
            )
    
    async def _send_invalid_url_message(self, message):
        """Send invalid URL message"""
        invalid_msg = f"""
{Icons.ERROR} <b>Invalid URL</b>

Please send a valid video URL from supported platforms:

{Icons.PLATFORMS} <b>Supported Platforms:</b>
• YouTube
• Instagram  
• TikTok
• Facebook
• Twitter/X
• And 1500+ other sites

{Icons.EXAMPLE} <b>Example:</b>
<code>https://www.youtube.com/watch?v=VIDEO_ID</code>
        """
        
        await message.reply_text(
            invalid_msg,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
    
    async def _send_unsupported_platform_message(self, message):
        """Send unsupported platform message"""
        unsupported_msg = f"""
{Icons.WARNING} <b>Platform Not Recognized</b>

The URL you sent doesn't appear to be from a supported platform.

{Icons.TIP} <b>Supported platforms include:</b>
• YouTube, Instagram, TikTok
• Facebook, Twitter/X
• Dailymotion, Vimeo
• And many more!

{Icons.HELP} Try sending a direct video URL or use /help for more information.
        """
        
        await message.reply_text(
            unsupported_msg,
            parse_mode=ParseMode.HTML
        )
    
    async def _send_extraction_error(self, message, error: str):
        """Send extraction error message"""
        # Determine error type and provide specific guidance
        error_lower = error.lower()
        
        if "private" in error_lower or "unavailable" in error_lower:
            error_msg = f"""
{Icons.LOCK} <b>Video Access Issue</b>

This video appears to be private or unavailable.

{Icons.SOLUTIONS} <b>Possible solutions:</b>
• Make sure the video is public
• Check if the URL is correct
• Try a different video
• Some platforms require the video to be publicly accessible

{Icons.SUPPORT} If this is a public video, please contact support.
            """
        elif "age" in error_lower or "restricted" in error_lower:
            error_msg = f"""
{Icons.RESTRICTED} <b>Age-Restricted Content</b>

This video has age restrictions that prevent downloading.

{Icons.INFO} Unfortunately, we cannot download age-restricted content due to platform limitations.
            """
        elif "copyright" in error_lower or "blocked" in error_lower:
            error_msg = f"""
{Icons.COPYRIGHT} <b>Copyright Protected</b>

This video is protected by copyright and cannot be downloaded.

{Icons.RESPECT} We respect intellectual property rights and cannot bypass copyright protection.
            """
        elif "network" in error_lower or "timeout" in error_lower:
            error_msg = f"""
{Icons.NETWORK} <b>Network Issue</b>

There was a problem connecting to the video platform.

{Icons.RETRY} Please try again in a few moments. If the problem persists, the platform may be temporarily unavailable.
            """
        else:
            error_msg = f"""
{Icons.ERROR} <b>Extraction Failed</b>

Unable to extract video information.

{Icons.DETAILS} <b>Error details:</b>
<code>{error[:200]}...</code>

{Icons.SOLUTIONS} <b>Try:</b>
• Check if the URL is correct
• Make sure the video is publicly accessible
• Try again in a few minutes
• Use a different video URL
            """
        
        keyboard = [
            [
                InlineKeyboardButton(f"{Icons.HELP} Help", callback_data="help"),
                InlineKeyboardButton(f"{Icons.SUPPORT} Support", callback_data="support")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await message.edit_text(
            error_msg,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    
    async def _send_video_preview(self, message, video_info: Dict[str, Any], original_url: str):
        """Send video preview with format selection"""
        try:
            # Create video ID for caching
            video_id = hashlib.md5(original_url.encode()).hexdigest()[:12]
            
            # Cache video info for format selection
            cache_key = f"video_preview:{video_id}"
            await self.cache_manager.set(
                cache_key, 
                json.dumps(video_info, default=str), 
                expire=3600  # 1 hour
            )
            
            # Create preview message
            preview_text = self._create_preview_text(video_info)
            
            # Create format selection keyboard
            keyboard = self._create_format_keyboard(video_info, video_id)
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send preview with thumbnail if available
            if video_info.get('thumbnail'):
                try:
                    # Send photo with caption and keyboard
                    await message.edit_text(
                        preview_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup,
                        disable_web_page_preview=False
                    )
                except Exception as e:
                    logger.warning(f"Failed to send with thumbnail: {e}")
                    # Fallback to text message
                    await message.edit_text(
                        preview_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup,
                        disable_web_page_preview=True
                    )
            else:
                await message.edit_text(
                    preview_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                    disable_web_page_preview=True
                )
            
        except Exception as e:
            logger.error(f"❌ Failed to send video preview: {e}", exc_info=True)
            await message.edit_text(
                f"{Icons.ERROR} Failed to generate video preview. Please try again."
            )
    
    def _create_preview_text(self, video_info: Dict[str, Any]) -> str:
        """Create formatted preview text"""
        title = truncate_text(video_info.get('title', 'Unknown Title'), 60)
        uploader = truncate_text(video_info.get('uploader', 'Unknown'), 30)
        platform = video_info.get('platform', 'Unknown').title()
        duration = video_info.get('duration', 0)
        view_count = video_info.get('view_count', 0)
        upload_date = video_info.get('upload_date', '')
        
        # Format duration
        duration_str = format_duration(duration) if duration else 'Unknown'
        
        # Format view count
        views_str = format_view_count(view_count) if view_count else 'Unknown'
        
        # Format upload date
        if upload_date:
            try:
                from datetime import datetime
                date_obj = datetime.strptime(upload_date, '%Y%m%d')
                upload_date_str = date_obj.strftime('%B %d, %Y')
            except:
                upload_date_str = upload_date
        else:
            upload_date_str = 'Unknown'
        
        preview_text = f"""
{Icons.VIDEO} <b>{title}</b>

{Icons.USER} <b>Channel:</b> {uploader}
{Icons.PLATFORM} <b>Platform:</b> {platform}
{Icons.TIME} <b>Duration:</b> {duration_str}
{Icons.VIEWS} <b>Views:</b> {views_str}
{Icons.DATE} <b>Upload Date:</b> {upload_date_str}

{Icons.DOWNLOAD} <b>Choose format to download:</b>
        """
        
        # Add description preview if available
        description = video_info.get('description', '')
        if description:
            desc_preview = truncate_text(description, 100)
            preview_text += f"\n{Icons.INFO} <b>Description:</b> {desc_preview}"
        
        return preview_text
    
    def _create_format_keyboard(self, video_info: Dict[str, Any], video_id: str) -> List[List[InlineKeyboardButton]]:
        """Create format selection keyboard"""
        keyboard = []
        
        # Video formats
        video_formats = video_info.get('formats', [])
        if video_formats:
            keyboard.append([
                InlineKeyboardButton(
                    f"{Icons.VIDEO} Video Formats", 
                    callback_data="header_video"
                )
            ])
            
            # Group formats by quality for better display
            quality_groups = {}
            for fmt in video_formats[:8]:  # Limit to 8 formats
                quality = fmt['quality']
                if quality not in quality_groups:
                    quality_groups[quality] = []
                quality_groups[quality].append(fmt)
            
            # Create buttons for each quality
            row = []
            for quality, formats in quality_groups.items():
                # Use the best format for each quality
                fmt = max(formats, key=lambda x: x.get('tbr', 0))
                
                button_text = f"{quality} ({fmt['ext'].upper()}) - {fmt['file_size_str']}"
                callback_data = f"format_{video_id}_video_{fmt['format_id']}"
                
                button = InlineKeyboardButton(button_text, callback_data=callback_data)
                row.append(button)
                
                # Add row when we have 2 buttons or it's the last one
                if len(row) == 1 or fmt == list(quality_groups.values())[-1][-1]:
                    keyboard.append(row)
                    row = []
        
        # Audio formats
        audio_formats = video_info.get('audio_formats', [])
        if audio_formats:
            keyboard.append([
                InlineKeyboardButton(
                    f"{Icons.AUDIO} Audio Only (MP3)", 
                    callback_data="header_audio"
                )
            ])
            
            # Show top audio qualities
            for fmt in audio_formats[:3]:  # Limit to 3 audio formats
                button_text = f"MP3 {fmt['quality']} - {fmt['file_size_str']}"
                callback_data = f"format_{video_id}_audio_{fmt['format_id']}"
                
                keyboard.append([
                    InlineKeyboardButton(button_text, callback_data=callback_data)
                ])
        
        # Add utility buttons
        keyboard.append([
            InlineKeyboardButton(f"{Icons.REFRESH} Refresh Info", callback_data=f"refresh_{video_id}"),
            InlineKeyboardButton(f"{Icons.CANCEL} Cancel", callback_data="cancel_preview")
        ])
        
        return keyboard
    
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle non-URL text messages"""
        try:
            message = update.message
            text = message.text.lower().strip()
            
            # Check for common keywords and provide helpful responses
            if any(word in text for word in ['help', 'how', 'what', 'guide']):
                keyboard = [[
                    InlineKeyboardButton(f"{Icons.HELP} Show Help", callback_data="help")
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await message.reply_text(
                    f"{Icons.TIP} Need help? Click the button below for a complete guide!",
                    reply_markup=reply_markup
                )
                
            elif any(word in text for word in ['thank', 'thanks', 'awesome', 'great', 'good']):
                await message.reply_text(
                    f"{Icons.HEART} You're welcome! Send me any video URL to get started!"
                )
                
            elif any(word in text for word in ['hi', 'hello', 'hey', 'start']):
                await message.reply_text(
                    f"{Icons.WAVE} Hello! Send me a video URL from YouTube, TikTok, Instagram, or any supported platform to download it!"
                )
                
            else:
                # Generic response for unrecognized text
                await message.reply_text(
                    f"{Icons.QUESTION} Send me a video URL to download, or use /help for more information!"
                )
            
        except Exception as e:
            logger.error(f"❌ Text message handling error: {e}", exc_info=True)
            await update.message.reply_text(
                f"{Icons.ERROR} Sorry, I didn't understand that. Please send a video URL."
            )
    
    async def handle_document_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle document uploads (not supported)"""
        await update.message.reply_text(
            f"{Icons.INFO} I can download videos from URLs, but I don't process uploaded files.\n\n"
            f"Please send me a video URL instead!"
        )
    
    async def handle_photo_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo uploads (not supported)"""
        await update.message.reply_text(
            f"{Icons.CAMERA} Nice photo! But I specialize in downloading videos from URLs.\n\n"
            f"Send me a video link and I'll download it for you!"
        )
    
    async def handle_voice_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle voice messages (not supported)"""
        await update.message.reply_text(
            f"{Icons.VOICE} I heard your voice message, but I can only process text URLs.\n\n"
            f"Please type or paste a video URL!"
        )
    
    async def handle_sticker_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle sticker messages"""
        stickers_responses = [
            f"{Icons.STICKER} Nice sticker! Now send me a video URL to download!",
            f"{Icons.SMILE} I like that sticker! Ready for a video URL?",
            f"{Icons.FUN} Cool sticker! Drop me a video link and let's get downloading!"
        ]
        
        import random
        response = random.choice(stickers_responses)
        await update.message.reply_text(response)
