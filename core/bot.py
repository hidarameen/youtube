"""
Main bot class that orchestrates the entire video downloading system
Handles initialization, routing, and high-level bot operations
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)

from config.settings import settings
from core.telethon_client import TelethonManager
from database.connection import DatabaseManager
from services.cache_manager import CacheManager
from services.downloader import VideoDownloader
from services.file_manager import FileManager
from services.progress_tracker import ProgressTracker
from handlers.commands import CommandHandlers
from handlers.callbacks import CallbackHandlers
from handlers.messages import MessageHandlers
from middlewares.auth import AuthMiddleware
from middlewares.rate_limit import RateLimitMiddleware
from utils.helpers import create_error_message

logger = logging.getLogger(__name__)

class VideoDownloaderBot:
    """Ultra high-performance video downloader bot"""
    
    def __init__(self):
        self.application: Optional[Application] = None
        self.telethon_manager: Optional[TelethonManager] = None
        self.db_manager: Optional[DatabaseManager] = None
        self.cache_manager: Optional[CacheManager] = None
        self.downloader: Optional[VideoDownloader] = None
        self.file_manager: Optional[FileManager] = None
        self.progress_tracker: Optional[ProgressTracker] = None
        
        # Handler instances
        self.command_handlers: Optional[CommandHandlers] = None
        self.callback_handlers: Optional[CallbackHandlers] = None
        self.message_handlers: Optional[MessageHandlers] = None
        
        # Middleware
        self.auth_middleware: Optional[AuthMiddleware] = None
        self.rate_limit_middleware: Optional[RateLimitMiddleware] = None
        
        # Performance tracking
        self.active_downloads: Dict[str, Any] = {}
        self.active_uploads: Dict[str, Any] = {}
        
    async def initialize(self):
        """Initialize all bot components"""
        logger.info("🔧 Initializing bot components...")
        
        try:
            # Initialize core services
            await self._initialize_core_services()
            
            # Initialize handlers
            await self._initialize_handlers()
            
            # Initialize middleware
            await self._initialize_middleware()
            
            # Setup telegram application
            await self._setup_application()
            
            logger.info("✅ Bot initialization completed successfully")
            
        except Exception as e:
            logger.error(f"❌ Bot initialization failed: {e}", exc_info=True)
            raise
    
    async def _initialize_core_services(self):
        """Initialize core services and managers"""
        # Database manager
        self.db_manager = DatabaseManager()
        await self.db_manager.initialize()
        
        # Cache manager  
        self.cache_manager = CacheManager()
        await self.cache_manager.initialize()
        
        # Telethon manager
        self.telethon_manager = TelethonManager()
        await self.telethon_manager.initialize()
        
        # Progress tracker
        self.progress_tracker = ProgressTracker(self.cache_manager)
        
        # File manager
        self.file_manager = FileManager(
            self.telethon_manager, 
            self.progress_tracker
        )
        
        # Video downloader
        self.downloader = VideoDownloader(
            self.file_manager,
            self.progress_tracker,
            self.cache_manager
        )
        
        logger.info("✅ Core services initialized")
    
    async def _initialize_handlers(self):
        """Initialize message and callback handlers"""
        self.command_handlers = CommandHandlers(
            self.downloader,
            self.file_manager,
            self.db_manager,
            self.cache_manager
        )
        
        self.callback_handlers = CallbackHandlers(
            self.downloader,
            self.file_manager,
            self.progress_tracker,
            self.db_manager,
            self.cache_manager
        )
        
        self.message_handlers = MessageHandlers(
            self.downloader,
            self.cache_manager,
            self.progress_tracker
        )
        
        logger.info("✅ Handlers initialized")
    
    async def _initialize_middleware(self):
        """Initialize middleware components"""
        self.auth_middleware = AuthMiddleware()
        self.rate_limit_middleware = RateLimitMiddleware(self.cache_manager)
        
        logger.info("✅ Middleware initialized")
    
    async def _setup_application(self):
        """Setup Telegram Bot API application"""
        # Create application with optimized settings
        builder = Application.builder()
        builder.token(settings.BOT_TOKEN)
        builder.concurrent_updates(True)
        builder.pool_timeout(30)
        builder.connect_timeout(30)
        builder.read_timeout(30)
        builder.write_timeout(30)
        builder.get_updates_pool_timeout(1)
        
        self.application = builder.build()
        
        # Add error handler
        self.application.add_error_handler(self._error_handler)
        
        # Add command handlers
        await self._register_handlers()
        
        logger.info("✅ Telegram application configured")
    
    async def _register_handlers(self):
        """Register all bot handlers with middleware"""
        # Command handlers
        self.application.add_handler(
            CommandHandler("start", self._with_middleware(self.command_handlers.start_command))
        )
        self.application.add_handler(
            CommandHandler("help", self._with_middleware(self.command_handlers.help_command))
        )
        self.application.add_handler(
            CommandHandler("stats", self._with_middleware(self.command_handlers.stats_command))
        )
        self.application.add_handler(
            CommandHandler("status", self._with_middleware(self.command_handlers.status_command))
        )
        self.application.add_handler(
            CommandHandler("cancel", self._with_middleware(self.command_handlers.cancel_command))
        )
        self.application.add_handler(
            CommandHandler("settings", self._with_middleware(self.command_handlers.settings_command))
        )
        
        # Message handlers  
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self._with_middleware(self.message_handlers.handle_url_message)
            )
        )
        
        # Master callback query handler
        self.application.add_handler(
            CallbackQueryHandler(
                self._with_middleware(self.callback_handlers.handle_callback_query)
            )
        )
        
        logger.info("✅ All handlers registered")
    
    def _with_middleware(self, handler):
        """Wrap handler with middleware"""
        async def wrapped_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            # Apply authentication middleware
            if not await self.auth_middleware.check_access(update):
                await update.effective_message.reply_text(
                    "❌ Access denied. This bot is restricted to authorized groups only."
                )
                return
            
            # Apply rate limiting middleware
            if not await self.rate_limit_middleware.check_rate_limit(update):
                await update.effective_message.reply_text(
                    "⏳ Please wait a moment before sending another request."
                )
                return
            
            # Execute the actual handler
            try:
                await handler(update, context)
            except Exception as e:
                logger.error(f"Handler error: {e}", exc_info=True)
                await self._send_error_message(update, e)
        
        return wrapped_handler
    
    async def _error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Global error handler"""
        logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)
        
        if update and update.effective_message:
            await self._send_error_message(update, context.error)
    
    async def _send_error_message(self, update: Update, error: Exception):
        """Send user-friendly error message"""
        error_msg = create_error_message(error)
        
        try:
            if update.callback_query:
                await update.callback_query.message.reply_text(error_msg)
            else:
                await update.effective_message.reply_text(error_msg)
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")
    
    async def start(self):
        """Start the bot"""
        try:
            logger.info("🚀 Starting bot polling...")
            
            # Initialize application
            await self.application.initialize()
            
            # Start polling in a way compatible with existing event loop
            await self.application.updater.start_polling(
                allowed_updates=["message", "callback_query"],
                drop_pending_updates=True
            )
            
            # Start the application
            await self.application.start()
            
            logger.info("✅ Bot is now running and ready to receive messages!")
            
            # Keep the bot running
            try:
                # In Replit, we don't want to block, just keep alive
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("📱 Received stop signal")
                
        except Exception as e:
            logger.error(f"❌ Bot polling failed: {e}", exc_info=True)
            raise
    
    async def stop(self):
        """Stop the bot and cleanup resources"""
        logger.info("🛑 Stopping bot...")
        
        if self.application:
            await self.application.shutdown()
        
        # Cleanup services
        if self.telethon_manager:
            await self.telethon_manager.disconnect()
        
        if self.db_manager:
            await self.db_manager.close_all_connections()
        
        if self.cache_manager:
            await self.cache_manager.close()
        
        logger.info("✅ Bot stopped successfully")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get current performance statistics"""
        return {
            'active_downloads': len(self.active_downloads),
            'active_uploads': len(self.active_uploads),
            'max_concurrent_downloads': settings.MAX_CONCURRENT_DOWNLOADS,
            'max_concurrent_uploads': settings.MAX_CONCURRENT_UPLOADS,
            'total_processed': getattr(self, 'total_processed', 0),
            'uptime': getattr(self, 'start_time', 0),
        }
