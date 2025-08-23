"""Utilities module for the video downloader bot"""

from .helpers import (
    generate_task_id, format_file_size, calculate_upload_speed, calculate_eta,
    sanitize_filename, truncate_text, get_file_hash, serialize_for_cache,
    deserialize_from_cache, get_system_stats, create_welcome_message,
    create_error_message, create_format_selection_keyboard,
    create_download_progress_message, setup_logging, cleanup_temp_files,
    validate_environment, format_bytes_per_second, is_url_safe,
    get_platform_emoji, run_with_timeout, chunks, safe_int, safe_float,
    create_progress_bar, get_mime_type, is_video_file, is_audio_file,
    get_file_extension, RateLimiter
)

from .validators import (
    is_valid_url, get_platform_from_url, get_platform_info, extract_video_id,
    normalize_url, is_playlist_url, validate_platform_support,
    get_supported_platforms, extract_url_from_text, validate_file_size_limit,
    is_live_stream_url, sanitize_url, get_platform_limitations,
    PlatformInfo, SUPPORTED_PLATFORMS
)

from .formatters import (
    format_file_size as format_file_size_alt, format_duration, format_speed,
    format_view_count, format_upload_time, format_uptime, format_percentage,
    format_timestamp, format_relative_time, format_quality_badge,
    format_platform_name, format_error_message, format_progress_bar,
    format_eta, format_number, truncate_text as truncate_text_alt,
    format_success_rate
)

__all__ = [
    # Helper functions
    'generate_task_id', 'format_file_size', 'calculate_upload_speed', 
    'calculate_eta', 'sanitize_filename', 'truncate_text', 'get_file_hash',
    'serialize_for_cache', 'deserialize_from_cache', 'get_system_stats',
    'create_welcome_message', 'create_error_message', 'create_format_selection_keyboard',
    'create_download_progress_message', 'setup_logging', 'cleanup_temp_files',
    'validate_environment', 'format_bytes_per_second', 'is_url_safe',
    'get_platform_emoji', 'run_with_timeout', 'chunks', 'safe_int', 'safe_float',
    'create_progress_bar', 'get_mime_type', 'is_video_file', 'is_audio_file',
    'get_file_extension', 'RateLimiter',
    
    # Validator functions
    'is_valid_url', 'get_platform_from_url', 'get_platform_info', 'extract_video_id',
    'normalize_url', 'is_playlist_url', 'validate_platform_support',
    'get_supported_platforms', 'extract_url_from_text', 'validate_file_size_limit',
    'is_live_stream_url', 'sanitize_url', 'get_platform_limitations',
    'PlatformInfo', 'SUPPORTED_PLATFORMS',
    
    # Formatter functions
    'format_duration', 'format_speed', 'format_view_count', 'format_upload_time',
    'format_uptime', 'format_percentage', 'format_timestamp', 'format_relative_time',
    'format_quality_badge', 'format_platform_name', 'format_error_message',
    'format_progress_bar', 'format_eta', 'format_number', 'format_success_rate'
]
