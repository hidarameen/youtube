"""
Telethon client manager for high-performance file operations
Handles MTProto connections, file uploads, and FastTelethon optimization
"""

import asyncio
import logging
import os
from typing import Optional, Callable, Any, Dict
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeVideo, DocumentAttributeFilename

from config.settings import settings
from utils.helpers import format_file_size, calculate_upload_speed

logger = logging.getLogger(__name__)

class TelethonManager:
    """High-performance Telethon client manager"""
    
    def __init__(self):
        self.client: Optional[TelegramClient] = None
        self.is_connected = False
        self.upload_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_UPLOADS)
        self.fast_telethon_available = False
        
        # Performance tracking
        self.upload_stats: Dict[str, Any] = {}
        
    async def initialize(self):
        """Initialize Telethon client with optimizations"""
        logger.info("🔧 Initializing Telethon client...")
        
        try:
            # Check for FastTelethon availability
            await self._check_fast_telethon()
            
            # Create optimized client
            await self._create_client()
            
            # Connect and authenticate
            await self._connect_and_auth()
            
            # Setup event handlers
            await self._setup_events()
            
            logger.info("✅ Telethon client initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Telethon initialization failed: {e}", exc_info=True)
            raise
    
    async def _check_fast_telethon(self):
        """Check and configure FastTelethon if available"""
        try:
            if settings.USE_FAST_TELETHON:
                # Try multiple FastTelethon package names
                global fast_upload, fast_download
                try:
                    from FastTelethon import fast_upload, fast_download
                except ImportError:
                    try:
                        from fast_telethon import fast_upload, fast_download
                    except ImportError:
                        # If FastTelethon not available, optimize standard Telethon
                        logger.warning("⚠️ FastTelethon not available, using optimized standard Telethon")
                        self.fast_telethon_available = False
                        return
                
                self.fast_telethon_available = True
                logger.info("🚀 FastTelethon enabled for enhanced performance")
        except Exception as e:
            logger.warning(f"⚠️ FastTelethon check failed: {e}, using optimized standard Telethon")
            self.fast_telethon_available = False
    
    async def _create_client(self):
        """Create optimized Telethon client"""
        # Use string session if provided, otherwise create new
        session = StringSession(settings.SESSION_STRING) if settings.SESSION_STRING else "video_bot_session"
        
        self.client = TelegramClient(
            session,
            settings.API_ID,
            settings.API_HASH,
            connection_retries=settings.CONNECTION_RETRIES,
            retry_delay=0.5,  # Ultra-fast retry
            timeout=settings.REQUEST_TIMEOUT,
            request_retries=3,  # Balanced retries
            flood_sleep_threshold=15,  # Aggressive flood threshold
            device_model="VideoBot Ultra Pro",
            system_version="3.0",
            app_version="3.0",
            lang_code="en",
            system_lang_code="en",
            # Ultra-performance optimizations
            auto_reconnect=True,
            sequential_updates=False,  # Allow parallel updates
            receive_updates=False  # Disable updates for upload-only client
        )
    
    async def _connect_and_auth(self):
        """Connect and authenticate the client"""
        await self.client.connect()
        
        if not await self.client.is_user_authorized():
            if settings.SESSION_STRING:
                logger.error("❌ Invalid session string provided")
                raise ValueError("Invalid session string")
            else:
                logger.error("❌ Client not authorized. Please provide SESSION_STRING")
                raise ValueError("Client authorization required")
        
        # Get client info
        me = await self.client.get_me()
        logger.info(f"✅ Connected as: {me.first_name} (@{me.username})")
        
        self.is_connected = True
    
    async def _setup_events(self):
        """Setup event handlers for monitoring"""
        @self.client.on(events.Raw)
        async def raw_handler(event):
            # Monitor for connection issues
            if hasattr(event, 'error'):
                logger.warning(f"Telethon event error: {event.error}")
    
    async def upload_file(
        self,
        file_path: str,
        chat_id: int,
        caption: str = "",
        progress_callback: Optional[Callable] = None,
        thumbnail: Optional[str] = None,
        video_metadata: Optional[Dict] = None
    ) -> Any:
        """
        High-performance file upload with FastTelethon optimization
        """
        async with self.upload_semaphore:
            try:
                if not os.path.exists(file_path):
                    raise FileNotFoundError(f"File not found: {file_path}")
                
                file_size = os.path.getsize(file_path)
                if file_size > settings.MAX_FILE_SIZE:
                    raise ValueError(f"File too large: {format_file_size(file_size)}")
                
                logger.info(f"📤 Starting upload: {os.path.basename(file_path)} ({format_file_size(file_size)})")
                
                # Prepare upload attributes
                attributes = await self._prepare_attributes(file_path, video_metadata)
                
                # Upload with progress tracking
                uploaded_file = await self._upload_with_progress(
                    file_path, progress_callback, file_size
                )
                
                # Send the file
                message = await self.client.send_file(
                    chat_id,
                    uploaded_file,
                    caption=caption,
                    attributes=attributes,
                    thumb=thumbnail,
                    force_document=file_size > 10 * 1024 * 1024,  # Force document for files > 10MB (faster)
                    parse_mode='HTML'
                )
                
                logger.info(f"✅ Upload completed: {os.path.basename(file_path)}")
                return message
                
            except Exception as e:
                logger.error(f"❌ Upload failed for {file_path}: {e}", exc_info=True)
                raise
    
    async def _upload_with_progress(
        self, 
        file_path: str, 
        progress_callback: Optional[Callable],
        file_size: int
    ):
        """Upload file with progress tracking and optimization"""
        
        if self.fast_telethon_available and settings.USE_FAST_TELETHON:
            # Use FastTelethon with ultra-optimized settings
            return await fast_upload(
                self.client,
                file_path,
                progress_callback=progress_callback,
                workers=getattr(settings, 'UPLOAD_WORKERS', 16),  # More workers for speed
                part_size_kb=512  # 512KB parts (max allowed)
            )
        else:
            # Use standard Telethon upload with ultra-optimized settings
            return await self.client.upload_file(
                file_path,
                progress_callback=progress_callback,
                part_size_kb=512,  # 512KB parts (max allowed)
                file_size=file_size if file_size else None  # Provide file size for optimization
            )
    
    async def _prepare_attributes(self, file_path: str, video_metadata: Optional[Dict] = None):
        """Prepare file attributes for upload"""
        attributes = []
        
        # Add filename attribute
        filename = os.path.basename(file_path)
        attributes.append(DocumentAttributeFilename(filename))
        
        # Add video attributes if it's a video file
        if video_metadata and filename.lower().endswith(('.mp4', '.avi', '.mkv', '.mov', '.webm')):
            attributes.append(DocumentAttributeVideo(
                duration=video_metadata.get('duration', 0),
                w=video_metadata.get('width', 0),
                h=video_metadata.get('height', 0),
                supports_streaming=True
            ))
        
        return attributes
    
    async def download_media(
        self,
        message,
        file_path: str,
        progress_callback: Optional[Callable] = None
    ) -> str:
        """
        High-performance media download
        """
        try:
            logger.info(f"📥 Starting download to: {file_path}")
            
            if self.fast_telethon_available:
                # Use FastTelethon for enhanced download speed
                return await fast_download(
                    self.client,
                    message,
                    file_path,
                    progress_callback=progress_callback
                )
            else:
                # Use standard Telethon download
                return await self.client.download_media(
                    message,
                    file=file_path,
                    progress_callback=progress_callback
                )
                
        except Exception as e:
            logger.error(f"❌ Download failed: {e}", exc_info=True)
            raise
    
    async def get_chat_info(self, chat_id: int):
        """Get information about a chat"""
        try:
            return await self.client.get_entity(chat_id)
        except Exception as e:
            logger.error(f"❌ Failed to get chat info for {chat_id}: {e}")
            return None
    
    async def send_message(self, chat_id: int, message: str, **kwargs):
        """Send a text message"""
        try:
            return await self.client.send_message(chat_id, message, **kwargs)
        except Exception as e:
            logger.error(f"❌ Failed to send message: {e}")
            raise
    
    def create_progress_callback(self, task_id: str, total_size: int):
        """Create a progress callback for tracking uploads/downloads"""
        def progress_callback(current: int, total: int):
            percentage = (current / total) * 100 if total > 0 else 0
            speed = calculate_upload_speed(current, total_size)
            
            # Update progress tracking
            self.upload_stats[task_id] = {
                'current': current,
                'total': total,
                'percentage': percentage,
                'speed': speed,
                'task_id': task_id
            }
        
        return progress_callback
    
    async def disconnect(self):
        """Disconnect the Telethon client"""
        if self.client and self.is_connected:
            await self.client.disconnect()
            self.is_connected = False
            logger.info("🔌 Telethon client disconnected")
    
    def is_ready(self) -> bool:
        """Check if client is ready for operations"""
        return self.client is not None and self.is_connected
    
    async def get_performance_stats(self) -> Dict[str, Any]:
        """Get current performance statistics"""
        if not self.client:
            return {}
        
        return {
            'connected': self.is_connected,
            'fast_telethon_enabled': self.fast_telethon_available,
            'active_uploads': len(self.upload_stats),
            'upload_queue_size': self.upload_semaphore._value,
            'max_concurrent_uploads': settings.MAX_CONCURRENT_UPLOADS,
        }
