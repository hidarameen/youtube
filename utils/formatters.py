"""
Formatting utilities for displaying data in user-friendly formats
Handles file sizes, durations, speeds, dates, and other data formatting
"""

import logging
from datetime import datetime, timedelta
from typing import Union, Optional, Any
import re

logger = logging.getLogger(__name__)

def format_file_size(size_bytes: Union[int, float]) -> str:
    """
    Format file size in human readable format
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        str: Formatted file size (e.g., "1.5 GB", "512 MB")
    """
    try:
        if not size_bytes or size_bytes < 0:
            return "0 B"
        
        # Convert to int if float
        size_bytes = int(size_bytes)
        
        # Size units
        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        unit_index = 0
        size = float(size_bytes)
        
        # Convert to appropriate unit
        while size >= 1024.0 and unit_index < len(units) - 1:
            size /= 1024.0
            unit_index += 1
        
        # Format based on size
        if unit_index == 0:  # Bytes
            return f"{int(size)} {units[unit_index]}"
        elif size >= 100:  # No decimal for large numbers
            return f"{int(size)} {units[unit_index]}"
        elif size >= 10:   # One decimal place
            return f"{size:.1f} {units[unit_index]}"
        else:              # Two decimal places for small numbers
            return f"{size:.2f} {units[unit_index]}"
        
    except Exception as e:
        logger.error(f"File size formatting error: {e}")
        return "Unknown"

def format_duration(seconds: Union[int, float, None]) -> str:
    """
    Format duration in human readable format
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        str: Formatted duration (e.g., "1:23:45", "5:30", "0:45")
    """
    try:
        if not seconds or seconds < 0:
            return "0:00"
        
        seconds = int(seconds)
        
        # Calculate hours, minutes, seconds
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        # Format based on duration
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
        
    except Exception as e:
        logger.error(f"Duration formatting error: {e}")
        return "Unknown"

def format_speed(bytes_per_second: Union[int, float, None]) -> str:
    """
    Format speed in human readable format
    
    Args:
        bytes_per_second: Speed in bytes per second
        
    Returns:
        str: Formatted speed (e.g., "5.2 MB/s", "1.8 GB/s")
    """
    try:
        if not bytes_per_second or bytes_per_second <= 0:
            return "0 B/s"
        
        # Use file size formatter and add /s
        size_str = format_file_size(bytes_per_second)
        return f"{size_str}/s"
        
    except Exception as e:
        logger.error(f"Speed formatting error: {e}")
        return "Unknown"

def format_view_count(view_count: Union[int, None]) -> str:
    """
    Format view count in human readable format
    
    Args:
        view_count: Number of views
        
    Returns:
        str: Formatted view count (e.g., "1.2M", "5.6K", "1,234")
    """
    try:
        if not view_count or view_count < 0:
            return "0"
        
        view_count = int(view_count)
        
        if view_count >= 1_000_000_000:
            return f"{view_count / 1_000_000_000:.1f}B"
        elif view_count >= 1_000_000:
            return f"{view_count / 1_000_000:.1f}M"
        elif view_count >= 1_000:
            return f"{view_count / 1_000:.1f}K"
        else:
            return f"{view_count:,}"
        
    except Exception as e:
        logger.error(f"View count formatting error: {e}")
        return "Unknown"

def format_upload_time(seconds: Union[int, float, None]) -> str:
    """
    Format upload/processing time in human readable format
    
    Args:
        seconds: Time in seconds
        
    Returns:
        str: Formatted time (e.g., "2m 30s", "1h 15m", "45s")
    """
    try:
        if not seconds or seconds < 0:
            return "0s"
        
        seconds = int(seconds)
        
        # Calculate time components
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        # Format based on duration
        if hours > 0:
            if minutes > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{hours}h"
        elif minutes > 0:
            if secs > 0:
                return f"{minutes}m {secs}s"
            else:
                return f"{minutes}m"
        else:
            return f"{secs}s"
        
    except Exception as e:
        logger.error(f"Upload time formatting error: {e}")
        return "Unknown"

def format_uptime(seconds: Union[int, float, None]) -> str:
    """
    Format system uptime in human readable format
    
    Args:
        seconds: Uptime in seconds
        
    Returns:
        str: Formatted uptime (e.g., "2 days, 5 hours", "3 hours, 20 minutes")
    """
    try:
        if not seconds or seconds < 0:
            return "Unknown"
        
        seconds = int(seconds)
        
        # Calculate time components
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        
        # Format based on duration
        parts = []
        
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        
        if minutes > 0 and days == 0:  # Don't show minutes if showing days
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        
        if not parts:  # Less than a minute
            return "Less than a minute"
        
        return ", ".join(parts)
        
    except Exception as e:
        logger.error(f"Uptime formatting error: {e}")
        return "Unknown"

def format_percentage(value: Union[int, float, None], decimal_places: int = 1) -> str:
    """
    Format percentage value
    
    Args:
        value: Percentage value (0-100)
        decimal_places: Number of decimal places
        
    Returns:
        str: Formatted percentage (e.g., "85.5%", "100%")
    """
    try:
        if value is None:
            return "0%"
        
        value = float(value)
        
        if decimal_places == 0:
            return f"{int(value)}%"
        else:
            return f"{value:.{decimal_places}f}%"
        
    except Exception as e:
        logger.error(f"Percentage formatting error: {e}")
        return "0%"

def format_timestamp(timestamp: Union[datetime, float, int, str, None], format_type: str = 'relative') -> str:
    """
    Format timestamp in various formats
    
    Args:
        timestamp: Timestamp to format
        format_type: Type of formatting ('relative', 'absolute', 'date', 'time')
        
    Returns:
        str: Formatted timestamp
    """
    try:
        if not timestamp:
            return "Unknown"
        
        # Convert to datetime if needed
        if isinstance(timestamp, (int, float)):
            dt = datetime.fromtimestamp(timestamp)
        elif isinstance(timestamp, str):
            # Try parsing ISO format
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except:
                return timestamp
        elif isinstance(timestamp, datetime):
            dt = timestamp
        else:
            return "Unknown"
        
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        
        if format_type == 'relative':
            return format_relative_time(dt, now)
        elif format_type == 'absolute':
            return dt.strftime('%B %d, %Y at %I:%M %p')
        elif format_type == 'date':
            return dt.strftime('%B %d, %Y')
        elif format_type == 'time':
            return dt.strftime('%I:%M %p')
        else:
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        
    except Exception as e:
        logger.error(f"Timestamp formatting error: {e}")
        return "Unknown"

def format_relative_time(dt: datetime, now: datetime = None) -> str:
    """
    Format relative time (e.g., "2 hours ago", "in 5 minutes")
    
    Args:
        dt: Datetime to format
        now: Current datetime (defaults to now)
        
    Returns:
        str: Relative time string
    """
    try:
        if now is None:
            now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        
        diff = now - dt
        future = diff.total_seconds() < 0
        
        if future:
            diff = dt - now
            prefix = "in "
            suffix = ""
        else:
            prefix = ""
            suffix = " ago"
        
        seconds = abs(diff.total_seconds())
        
        # Format based on time difference
        if seconds < 60:
            return f"{prefix}just now{suffix}" if not future else "in a moment"
        elif seconds < 3600:  # Less than 1 hour
            minutes = int(seconds // 60)
            unit = "minute" if minutes == 1 else "minutes"
            return f"{prefix}{minutes} {unit}{suffix}"
        elif seconds < 86400:  # Less than 1 day
            hours = int(seconds // 3600)
            unit = "hour" if hours == 1 else "hours"
            return f"{prefix}{hours} {unit}{suffix}"
        elif seconds < 2592000:  # Less than 30 days
            days = int(seconds // 86400)
            unit = "day" if days == 1 else "days"
            return f"{prefix}{days} {unit}{suffix}"
        elif seconds < 31536000:  # Less than 1 year
            months = int(seconds // 2592000)
            unit = "month" if months == 1 else "months"
            return f"{prefix}{months} {unit}{suffix}"
        else:
            years = int(seconds // 31536000)
            unit = "year" if years == 1 else "years"
            return f"{prefix}{years} {unit}{suffix}"
        
    except Exception as e:
        logger.error(f"Relative time formatting error: {e}")
        return "Unknown"

def format_quality_badge(quality: str) -> str:
    """
    Format quality with appropriate badge/emoji
    
    Args:
        quality: Quality string (e.g., "1080p", "720p")
        
    Returns:
        str: Formatted quality with badge
    """
    try:
        if not quality:
            return "Unknown"
        
        quality_lower = quality.lower()
        
        # Quality badges
        if '4k' in quality_lower or '2160p' in quality_lower:
            return f"🏆 {quality}"
        elif '1440p' in quality_lower or '2k' in quality_lower:
            return f"💎 {quality}"
        elif '1080p' in quality_lower or 'fhd' in quality_lower:
            return f"🔥 {quality}"
        elif '720p' in quality_lower or 'hd' in quality_lower:
            return f"✨ {quality}"
        elif '480p' in quality_lower:
            return f"📱 {quality}"
        elif '360p' in quality_lower or '240p' in quality_lower:
            return f"📶 {quality}"
        else:
            return quality
        
    except Exception as e:
        logger.error(f"Quality badge formatting error: {e}")
        return quality or "Unknown"

def format_platform_name(platform: str) -> str:
    """
    Format platform name with proper capitalization and emoji
    
    Args:
        platform: Platform name
        
    Returns:
        str: Formatted platform name
    """
    try:
        if not platform:
            return "Unknown"
        
        platform_lower = platform.lower()
        
        # Platform formatting with emojis
        platform_map = {
            'youtube': '🔴 YouTube',
            'tiktok': '⚫ TikTok',
            'instagram': '📸 Instagram',
            'facebook': '🔵 Facebook',
            'twitter': '🐦 Twitter',
            'x': '❌ X (Twitter)',
            'dailymotion': '🟠 Dailymotion',
            'vimeo': '🔵 Vimeo',
            'twitch': '🟣 Twitch',
            'reddit': '🔸 Reddit',
            'streamable': '🎬 Streamable'
        }
        
        return platform_map.get(platform_lower, f"🎬 {platform.title()}")
        
    except Exception as e:
        logger.error(f"Platform name formatting error: {e}")
        return platform or "Unknown"

def format_error_message(error: str, max_length: int = 100) -> str:
    """
    Format error message for user display
    
    Args:
        error: Error message
        max_length: Maximum length of formatted message
        
    Returns:
        str: Formatted error message
    """
    try:
        if not error:
            return "Unknown error"
        
        # Clean up technical error messages
        error = str(error)
        
        # Remove common technical prefixes
        technical_prefixes = [
            'ERROR: ',
            'Exception: ',
            'RuntimeError: ',
            'ValueError: ',
            'HTTPError: ',
            'URLError: '
        ]
        
        for prefix in technical_prefixes:
            if error.startswith(prefix):
                error = error[len(prefix):]
                break
        
        # Truncate if too long
        if len(error) > max_length:
            error = error[:max_length - 3] + "..."
        
        # Capitalize first letter
        error = error[0].upper() + error[1:] if error else ""
        
        return error
        
    except Exception as e:
        logger.error(f"Error message formatting error: {e}")
        return "An error occurred"

def format_progress_bar(
    current: int, 
    total: int, 
    length: int = 20, 
    filled_char: str = '█', 
    empty_char: str = '░'
) -> str:
    """
    Create a visual progress bar
    
    Args:
        current: Current progress value
        total: Total value
        length: Length of progress bar in characters
        filled_char: Character for filled portion
        empty_char: Character for empty portion
        
    Returns:
        str: Formatted progress bar
    """
    try:
        if total <= 0:
            percentage = 0
        else:
            percentage = min(100, max(0, (current / total) * 100))
        
        filled_length = int(length * percentage / 100)
        empty_length = length - filled_length
        
        bar = filled_char * filled_length + empty_char * empty_length
        
        return f"[{bar}] {percentage:.1f}%"
        
    except Exception as e:
        logger.error(f"Progress bar formatting error: {e}")
        return f"[{'░' * length}] 0.0%"

def format_eta(seconds: Union[int, float, None]) -> str:
    """
    Format estimated time of arrival
    
    Args:
        seconds: ETA in seconds
        
    Returns:
        str: Formatted ETA (e.g., "5m 30s", "2h 15m")
    """
    try:
        if not seconds or seconds <= 0:
            return "Unknown"
        
        return format_upload_time(seconds)
        
    except Exception as e:
        logger.error(f"ETA formatting error: {e}")
        return "Unknown"

def format_number(number: Union[int, float, None], abbreviate: bool = False) -> str:
    """
    Format numbers with thousand separators or abbreviations
    
    Args:
        number: Number to format
        abbreviate: Whether to abbreviate large numbers
        
    Returns:
        str: Formatted number
    """
    try:
        if number is None:
            return "0"
        
        number = float(number)
        
        if abbreviate:
            if number >= 1_000_000_000:
                return f"{number / 1_000_000_000:.1f}B"
            elif number >= 1_000_000:
                return f"{number / 1_000_000:.1f}M"
            elif number >= 1_000:
                return f"{number / 1_000:.1f}K"
            else:
                return f"{int(number)}"
        else:
            return f"{int(number):,}"
        
    except Exception as e:
        logger.error(f"Number formatting error: {e}")
        return "0"

def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to specified length with suffix
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add when truncating
        
    Returns:
        str: Truncated text
    """
    try:
        if not text:
            return ""
        
        if len(text) <= max_length:
            return text
        
        return text[:max_length - len(suffix)] + suffix
        
    except Exception as e:
        logger.error(f"Text truncation error: {e}")
        return text or ""

def format_success_rate(successful: int, total: int) -> str:
    """
    Format success rate percentage
    
    Args:
        successful: Number of successful operations
        total: Total number of operations
        
    Returns:
        str: Formatted success rate with color emoji
    """
    try:
        if total == 0:
            return "N/A"
        
        rate = (successful / total) * 100
        
        # Add color indicators
        if rate >= 95:
            emoji = "🟢"
        elif rate >= 85:
            emoji = "🟡"
        elif rate >= 70:
            emoji = "🟠"
        else:
            emoji = "🔴"
        
        return f"{emoji} {rate:.1f}%"
        
    except Exception as e:
        logger.error(f"Success rate formatting error: {e}")
        return "N/A"
