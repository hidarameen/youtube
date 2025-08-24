"""
Utility helper functions for the video downloader bot
Common functions used across the application
"""

import asyncio
import hashlib
import logging
import os
import psutil
import re
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import json

logger = logging.getLogger(__name__)

def generate_task_id() -> str:
    """Generate unique task ID for tracking downloads/uploads"""
    timestamp = str(int(time.time() * 1000))
    random_part = str(uuid.uuid4())[:8]
    return f"task_{timestamp}_{random_part}"

def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024.0 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    if i == 0:
        return f"{int(size_bytes)} {size_names[i]}"
    else:
        return f"{size_bytes:.1f} {size_names[i]}"

def calculate_upload_speed(current: int, total_size: int, start_time: float = None) -> float:
    """Calculate upload/download speed in bytes per second"""
    if start_time is None:
        start_time = time.time()
    
    elapsed_time = time.time() - start_time
    if elapsed_time <= 0:
        return 0
    
    return current / elapsed_time

def calculate_eta(current: int, total: int, speed: float) -> int:
    """Calculate estimated time to completion in seconds"""
    if speed <= 0 or current >= total:
        return 0
    
    remaining_bytes = total - current
    return int(remaining_bytes / speed)

def sanitize_filename(filename: str, max_length: int = 100) -> str:
    """Sanitize filename for safe file system usage"""
    # Remove/replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = re.sub(r'[\x00-\x1f]', '', filename)  # Remove control characters
    
    # Remove multiple spaces and underscores
    filename = re.sub(r'[_\s]+', '_', filename)
    
    # Trim and remove leading/trailing periods and spaces
    filename = filename.strip('. ')
    
    # Truncate if too long
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        if ext:
            filename = name[:max_length-len(ext)] + ext
        else:
            filename = filename[:max_length]
    
    # Ensure filename is not empty
    if not filename:
        filename = f"untitled_{int(time.time())}"
    
    return filename

def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to specified length with suffix"""
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

def get_file_hash(file_path: str, algorithm: str = 'md5') -> str:
    """Get file hash for deduplication"""
    try:
        hash_obj = hashlib.new(algorithm)
        
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hash_obj.update(chunk)
        
        return hash_obj.hexdigest()
        
    except Exception as e:
        logger.error(f"Failed to calculate hash for {file_path}: {e}")
        return ""

def serialize_for_cache(data: Any) -> str:
    """Serialize data for Redis cache storage"""
    try:
        if isinstance(data, (str, int, float, bool)):
            return str(data)
        else:
            return json.dumps(data, default=str, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to serialize data for cache: {e}")
        return str(data)

def deserialize_from_cache(data: str) -> Any:
    """Deserialize data from Redis cache"""
    try:
        # Try to parse as JSON first
        return json.loads(data)
    except (json.JSONDecodeError, TypeError):
        # Return as string if JSON parsing fails
        return data

def get_system_stats() -> Dict[str, Any]:
    """Get current system statistics"""
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        available_memory = memory.available
        
        # Disk usage
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        
        # System uptime
        boot_time = psutil.boot_time()
        uptime = time.time() - boot_time
        
        return {
            'cpu_percent': cpu_percent,
            'memory_percent': memory_percent,
            'available_memory': available_memory,
            'disk_percent': disk_percent,
            'uptime': uptime
        }
        
    except Exception as e:
        logger.error(f"Failed to get system stats: {e}")
        return {}

def create_welcome_message(first_name: str = None) -> str:
    """Create personalized welcome message"""
    from static.icons import Icons
    
    name = first_name if first_name else "there"
    
    return f"""
{Icons.ROBOT} <b>Welcome to Ultra Video Downloader Bot{f', {name}' if first_name else ''}!</b>

{Icons.ROCKET} <b>The fastest and most powerful video downloader on Telegram!</b>

{Icons.FEATURES} <b>What I can do:</b>
• {Icons.DOWNLOAD} Download from 1500+ platforms
• {Icons.SPEED} Lightning-fast processing
• {Icons.QUALITY} Multiple quality options
• {Icons.LARGE_FILE} Up to 2GB file support
• {Icons.AUDIO} Audio extraction (MP3)
• {Icons.PROGRESS} Real-time progress tracking

{Icons.SIMPLE} <b>Getting Started:</b>
Just send me any video URL and I'll handle the rest!

{Icons.PLATFORMS} <b>Supported:</b> YouTube, TikTok, Instagram, Facebook, Twitter, and many more!

{Icons.TIP} <b>Pro Tip:</b> Use /help to see all features and commands.
    """

def create_error_message(error: Exception) -> str:
    """Create user-friendly error message"""
    from static.icons import Icons
    
    error_type = type(error).__name__
    error_str = str(error)
    
    # Map common errors to user-friendly messages
    error_messages = {
        'ValidationError': f"{Icons.WARNING} Invalid input. Please check your request and try again.",
        'FileNotFoundError': f"{Icons.ERROR} File not found. The requested content may have been removed.",
        'PermissionError': f"{Icons.LOCK} Access denied. The content may be private or restricted.",
        'TimeoutError': f"{Icons.TIME} Request timed out. Please try again in a few moments.",
        'ConnectionError': f"{Icons.NETWORK} Network connection issue. Please check your connection and retry.",
        'ValueError': f"{Icons.WARNING} Invalid value provided. Please check your input.",
    }
    
    if error_type in error_messages:
        return error_messages[error_type]
    elif 'private' in error_str.lower() or 'unavailable' in error_str.lower():
        return f"{Icons.LOCK} This content is private or unavailable."
    elif 'copyright' in error_str.lower() or 'blocked' in error_str.lower():
        return f"{Icons.COPYRIGHT} This content is protected by copyright."
    elif 'age' in error_str.lower() or 'restricted' in error_str.lower():
        return f"{Icons.RESTRICTED} This content has age restrictions."
    else:
        return f"{Icons.ERROR} An unexpected error occurred. Please try again or contact support."

def create_format_selection_keyboard(video_info: Dict, video_id: str):
    """Create inline keyboard for format selection"""
    from telegram import InlineKeyboardButton
    
    keyboard = []
    
    # Video formats
    formats = video_info.get('formats', [])
    if formats:
        for fmt in formats[:6]:  # Limit to 6 formats
            button_text = f"{fmt['quality']} ({fmt['ext'].upper()}) - {fmt['file_size_str']}"
            callback_data = f"format_{video_id}_video_{fmt['format_id']}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    # Audio formats
    audio_formats = video_info.get('audio_formats', [])
    if audio_formats:
        for fmt in audio_formats[:3]:  # Limit to 3 audio formats
            button_text = f"MP3 {fmt['quality']} - {fmt['file_size_str']}"
            callback_data = f"format_{video_id}_audio_{fmt['format_id']}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    return keyboard

def create_download_progress_message(progress: Dict, video_info: Dict) -> str:
    """Create animated formatted download progress message"""
    from static.icons import Icons
    import time
    
    title = truncate_text(video_info.get('title', 'Unknown'), 45)
    current_str = progress.get('current_str', '0 B')
    total_str = progress.get('total_str', '0 B')
    percentage = progress.get('percentage', 0)
    speed_str = progress.get('speed_str', '0 B/s')
    eta_str = progress.get('eta_str', 'Unknown')
    progress_bar = progress.get('progress_bar', '[░░░░░░░░░░] 0.0%')
    status = progress.get('status', 'unknown')
    task_id = progress.get('task_id', '')
    
    # Animated status icons based on current status
    status_configs = {
        'downloading': {
            'icon': Icons.DOWNLOAD_ANIMATION[int(time.time()) % len(Icons.DOWNLOAD_ANIMATION)],
            'title': 'تحميل جاري',
            'color': '🟦'
        },
        'uploading': {
            'icon': Icons.UPLOAD_ANIMATION[int(time.time()) % len(Icons.UPLOAD_ANIMATION)],
            'title': 'رفع جاري',
            'color': '🟨'
        },
        'completed': {
            'icon': Icons.PARTY,
            'title': 'تم بنجاح!',
            'color': '🟩'
        },
        'failed': {
            'icon': Icons.ERROR,
            'title': 'فشل',
            'color': '🟥'
        },
        'cancelled': {
            'icon': Icons.STOP,
            'title': 'ملغي',
            'color': '⬜'
        }
    }
    
    config = status_configs.get(status, {
        'icon': Icons.PROGRESS,
        'title': status.title(),
        'color': '⬜'
    })
    
    # Add motivational messages for different percentages
    motivational = ""
    if status == 'downloading' and percentage > 0:
        if percentage < 25:
            motivational = f"{Icons.ROCKET} البداية دائماً صعبة!"
        elif percentage < 50:
            motivational = f"{Icons.MUSCLE} نصف الطريق! استمر!"
        elif percentage < 75:
            motivational = f"{Icons.FIRE} الأمور تسير بشكل رائع!"
        elif percentage < 95:
            motivational = f"{Icons.LIGHTNING} تقريباً انتهينا!"
        else:
            motivational = f"{Icons.MAGIC} اللمسة الأخيرة..."
    
    return f"""
{config['color']} <b>{config['icon']} {config['title']}</b>

{Icons.VIDEO} <b>العنوان:</b> {title}
{Icons.MAGIC} <b>التقدم:</b> {current_str} / {total_str}

{progress_bar}

{Icons.TURBO} <b>السرعة:</b> {speed_str}
{Icons.CLOCK} <b>الوقت المتبقي:</b> {eta_str}

{motivational}
    """

def setup_logging():
    """Setup logging configuration"""
    from config.settings import settings
    
    # Create logs directory
    os.makedirs(os.path.dirname(settings.LOG_FILE), exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(settings.LOG_FILE, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # Set specific log levels for noisy modules
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)

async def cleanup_temp_files():
    """Clean up temporary files on startup"""
    try:
        from config.settings import settings
        
        temp_dir = Path(settings.TEMP_DIR)
        if temp_dir.exists():
            current_time = time.time()
            max_age = settings.MAX_TEMP_AGE
            
            cleaned_count = 0
            for file_path in temp_dir.rglob('*'):
                if file_path.is_file():
                    try:
                        file_age = current_time - file_path.stat().st_ctime
                        if file_age > max_age:
                            file_path.unlink()
                            cleaned_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to clean up file {file_path}: {e}")
            
            if cleaned_count > 0:
                logger.info(f"🗑️ Cleaned up {cleaned_count} temporary files")
    
    except Exception as e:
        logger.error(f"Failed to cleanup temp files: {e}")

def validate_environment():
    """Validate required environment variables"""
    from config.settings import settings
    
    required_vars = [
        'BOT_TOKEN', 'API_ID', 'API_HASH', 'ALLOWED_CHAT_IDS', 'UPLOAD_CHAT_ID'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not getattr(settings, var, None):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        return False
    
    return True

def format_bytes_per_second(bytes_per_sec: float) -> str:
    """Format speed in human readable format"""
    return f"{format_file_size(int(bytes_per_sec))}/s"

def is_url_safe(url: str) -> bool:
    """Check if URL is safe to process"""
    if not url:
        return False
    
    # Check for malicious patterns
    malicious_patterns = [
        r'javascript:',
        r'data:',
        r'vbscript:',
        r'file://',
        r'ftp://',
    ]
    
    url_lower = url.lower()
    for pattern in malicious_patterns:
        if re.search(pattern, url_lower):
            return False
    
    return True

def get_platform_emoji(platform: str) -> str:
    """Get emoji for platform"""
    platform_emojis = {
        'youtube': '🔴',
        'tiktok': '⚫',
        'instagram': '📸',
        'facebook': '🔵',
        'twitter': '🐦',
        'x': '❌',
        'dailymotion': '🟠',
        'vimeo': '🔵',
        'twitch': '🟣'
    }
    
    return platform_emojis.get(platform.lower(), '🎬')

async def run_with_timeout(coro, timeout: float):
    """Run coroutine with timeout"""
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        raise TimeoutError(f"Operation timed out after {timeout} seconds")

def chunks(lst: List, n: int):
    """Yield successive n-sized chunks from list"""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to integer"""
    try:
        if value is None:
            return default
        return int(float(value))
    except (ValueError, TypeError):
        return default

def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float"""
    try:
        if value is None:
            return default
        return float(value)
    except (ValueError, TypeError):
        return default

def create_progress_bar(percentage: float, length: int = 20, filled: str = '█', empty: str = '░', animated: bool = True) -> str:
    """Create animated visual progress bar"""
    from static.icons import Icons
    import time
    
    filled_length = int(length * percentage / 100)
    
    if animated and percentage < 100:
        # Add animation to the progress edge
        spinner_frame = Icons.SPINNER_FRAMES[int(time.time() * 3) % len(Icons.SPINNER_FRAMES)]
        if filled_length > 0:
            bar = filled * (filled_length - 1) + spinner_frame + empty * (length - filled_length)
        else:
            bar = spinner_frame + empty * (length - 1)
    else:
        bar = filled * filled_length + empty * (length - filled_length)
    
    # Add percentage with special formatting
    if percentage >= 100:
        return f"[{bar}] {Icons.SUCCESS} 100%"
    else:
        return f"[{bar}] {percentage:.1f}%"

def get_mime_type(file_path: str) -> str:
    """Get MIME type of file"""
    import mimetypes
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type or 'application/octet-stream'

def is_video_file(file_path: str) -> bool:
    """Check if file is a video"""
    video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.webm', '.flv', '.wmv', '.m4v'}
    return Path(file_path).suffix.lower() in video_extensions

def is_audio_file(file_path: str) -> bool:
    """Check if file is audio"""
    audio_extensions = {'.mp3', '.wav', '.aac', '.ogg', '.m4a', '.flac', '.wma'}
    return Path(file_path).suffix.lower() in audio_extensions

def get_file_extension(url: str) -> str:
    """Extract file extension from URL"""
    try:
        from urllib.parse import urlparse
        path = urlparse(url).path
        return Path(path).suffix.lower()
    except:
        return ''

class RateLimiter:
    """Simple rate limiter for API calls"""
    
    def __init__(self, max_calls: int, time_window: int):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []
    
    async def acquire(self) -> bool:
        """Check if call is allowed"""
        now = time.time()
        
        # Remove old calls outside time window
        self.calls = [call_time for call_time in self.calls if now - call_time < self.time_window]
        
        # Check if we can make another call
        if len(self.calls) < self.max_calls:
            self.calls.append(now)
            return True
        
        return False
    
    def time_until_reset(self) -> float:
        """Get time until rate limit resets"""
        if not self.calls:
            return 0
        
        oldest_call = min(self.calls)
        return max(0, self.time_window - (time.time() - oldest_call))
