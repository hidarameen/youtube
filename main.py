#!/usr/bin/env python3
"""
Ultra High-Performance Telegram Video Downloader Bot
Main entry point for the application
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.settings import Settings
from core.bot import VideoDownloaderBot
from database.connection import DatabaseManager
from services.cache_manager import CacheManager
from utils.helpers import setup_logging, cleanup_temp_files

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

async def startup_checks():
    """Perform startup checks and initialization"""
    logger.info("🚀 Starting Ultra High-Performance Video Downloader Bot")
    
    # Verify environment variables
    settings = Settings()
    if not settings.validate():
        logger.error("❌ Configuration validation failed")
        sys.exit(1)
    
    # Create necessary directories
    os.makedirs("temp", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    # Clean up any leftover temporary files
    await cleanup_temp_files()
    
    logger.info("✅ Startup checks completed successfully")

async def shutdown_cleanup():
    """Cleanup resources on shutdown"""
    logger.info("🛑 Shutting down bot...")
    
    # Cleanup temporary files
    await cleanup_temp_files()
    
    # Close database connections
    db_manager = DatabaseManager()
    await db_manager.close_all_connections()
    
    # Close cache connections
    cache_manager = CacheManager()
    await cache_manager.close()
    
    logger.info("✅ Shutdown cleanup completed")

async def main():
    """Main application entry point"""
    try:
        # Startup initialization
        await startup_checks()
        
        # Initialize and start the bot
        bot = VideoDownloaderBot()
        await bot.initialize()
        
        # Start the bot
        logger.info("🤖 Bot is now running...")
        await bot.start()
        
    except KeyboardInterrupt:
        logger.info("📱 Received keyboard interrupt")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await shutdown_cleanup()

if __name__ == "__main__":
    # Run with optimized event loop
    try:
        import uvloop
        uvloop.install()
        logger.info("🔄 Using uvloop for enhanced performance")
    except ImportError:
        logger.info("🔄 Using default asyncio event loop")
    
    # Run the application
    asyncio.run(main())
