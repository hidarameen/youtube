# Ultra High-Performance Telegram Video Downloader Bot

## Overview

This is an ultra high-performance Telegram bot designed for downloading videos from 1500+ platforms including YouTube, TikTok, Instagram, Facebook, and Twitter. The bot is built with Python using python-telegram-bot and Telethon for handling large file uploads (up to 2GB), and leverages yt-dlp for video extraction. The architecture prioritizes performance, scalability, and reliability with features like concurrent downloads/uploads, intelligent caching, real-time progress tracking, and comprehensive rate limiting.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Core Architecture Pattern
- **Modular Service Architecture**: The application follows a clean separation of concerns with distinct modules for bot handling, video downloading, file management, database operations, and caching
- **Async/Await Concurrency**: Built entirely on asyncio for high-performance concurrent operations with semaphore-controlled resource management
- **Dual Telegram Client Strategy**: Uses both python-telegram-bot for user interactions and Telethon for high-performance file operations and 2GB file support

### Bot Framework Integration
- **python-telegram-bot**: Primary framework for handling user interactions, commands, and callback queries
- **Telethon**: Secondary client specifically for file uploads, leveraging MTProto for faster transfers and larger file support
- **Handler-based Routing**: Organized into command handlers, callback handlers, and message handlers for clean request processing

### Video Processing Pipeline
- **yt-dlp Integration**: Uses yt-dlp as the core video extraction engine supporting 1500+ platforms
- **Format Selection**: Intelligent format detection and user-selectable quality options
- **Concurrent Downloads**: Semaphore-controlled concurrent downloads with configurable limits
- **Progress Tracking**: Real-time download and upload progress with Redis-based state management

### Database Design
- **PostgreSQL with SQLAlchemy**: Uses async SQLAlchemy with connection pooling for optimal database performance
- **User Management**: Tracks users, download history, analytics, and user preferences
- **Statistics Tracking**: Comprehensive system statistics, user analytics, and error logging
- **Connection Pooling**: Optimized connection pool settings for high-throughput operations

### Caching Strategy
- **Redis Cache Manager**: High-performance Redis caching for video metadata, user sessions, and temporary data
- **Intelligent Cache Keys**: Strategic caching of video information to reduce API calls and improve response times
- **TTL Management**: Automatic cache expiration and cleanup for optimal memory usage

### File Management System
- **Temporary File Handling**: Secure temporary file management with automatic cleanup
- **Upload Optimization**: Chunked uploads with progress tracking and error recovery
- **File Size Management**: Support for files up to 2GB using Telethon's large file capabilities
- **Format Processing**: Automatic file format detection and optimization

### Security and Access Control
- **Chat-based Authorization**: Restricts bot access to specific chat IDs and authorized users
- **Rate Limiting**: Multi-level rate limiting (global, per-user, per-operation) to prevent abuse
- **Input Validation**: Comprehensive URL validation and sanitization
- **Error Handling**: Robust error handling with logging and user-friendly error messages

### Performance Optimizations
- **Connection Pooling**: Both database and Redis connections use optimized pooling
- **Concurrent Processing**: Configurable semaphores for downloads, uploads, and processing operations
- **Memory Management**: Efficient temporary file handling and automatic cleanup
- **Fast Telethon**: Optional FastTelethon integration for enhanced upload speeds

### Monitoring and Analytics
- **Progress Tracking**: Real-time progress updates stored in Redis for fast access
- **System Statistics**: Comprehensive tracking of downloads, success rates, and system performance
- **User Analytics**: Per-user statistics and usage patterns
- **Error Logging**: Detailed error tracking and logging for debugging and monitoring

## External Dependencies

### Core Dependencies
- **python-telegram-bot**: Primary Telegram bot framework for user interactions
- **Telethon**: Secondary Telegram client for file operations and large file support
- **yt-dlp**: Video extraction engine supporting 1500+ platforms
- **asyncio**: Python's built-in asynchronous programming framework

### Database and Caching
- **PostgreSQL**: Primary database for persistent data storage with asyncpg driver
- **Redis**: High-performance caching and session management
- **SQLAlchemy**: ORM with async support for database operations
- **aioredis**: Async Redis client for optimal performance

### Utilities and Support
- **psutil**: System monitoring and resource tracking
- **pathlib**: Modern file path handling
- **mimetypes**: File type detection and validation
- **hashlib**: File integrity verification and caching keys

### Development and Deployment
- **logging**: Comprehensive logging throughout the application
- **dataclasses**: Type-safe data structures for configuration and models
- **typing**: Type hints for better code maintainability
- **json**: Data serialization for caching and API responses

### Platform-Specific Integrations
- **YouTube API**: Enhanced metadata extraction (optional)
- **Platform-specific extractors**: Specialized handlers for different video platforms
- **Cookie support**: For platforms requiring authentication
- **Proxy support**: For geo-restricted content access

### Performance Libraries
- **concurrent.futures**: Thread pool execution for CPU-bound tasks
- **multiprocessing**: Process-based parallelism for intensive operations
- **FastTelethon**: Optional performance enhancement for Telethon uploads
- **uvloop**: Optional event loop optimization for better performance