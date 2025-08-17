"""
YTDlp Wrapper - غلاف yt-dlp المتطور
"""

import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass

import yt_dlp
from yt_dlp.utils import DownloadError

from .progress import ProgressTracker

logger = logging.getLogger(__name__)


@dataclass
class VideoInfo:
    """معلومات الفيديو"""
    title: str
    duration: int
    file_size: int
    format: str
    quality: str
    thumbnail_url: str
    description: str


class YTDlpWrapper:
    """غلاف yt-dlp المتطور"""
    
    def __init__(self):
        self.progress_tracker = ProgressTracker()
    
    def download_video(self, url: str, ydl_opts: Dict[str, Any], progress_hook: Optional[Any] = None) -> 'DownloadResult':
        """تحميل الفيديو"""
        try:
            # إضافة progress hook
            if progress_hook is not None:
                ydl_opts['progress_hooks'] = [progress_hook]
            else:
                ydl_opts['progress_hooks'] = [self.progress_tracker.update_progress]
            
            # إنشاء كائن yt-dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # استخراج معلومات الفيديو
                info = ydl.extract_info(url, download=False)
                if not info:
                    raise DownloadError("فشل في استخراج معلومات الفيديو")
                
                # تحميل الفيديو
                ydl.download([url])
                
                # العثور على الملف المحمل
                file_path = self._find_downloaded_file(info, ydl_opts['outtmpl'])
                
                if not file_path or not file_path.exists():
                    raise DownloadError("لم يتم العثور على الملف المحمل")
                
                # إنشاء نتيجة التحميل
                result = DownloadResult(
                    success=True,
                    file_path=file_path,
                    file_size=file_path.stat().st_size,
                    duration=info.get('duration'),
                    title=info.get('title'),
                    metadata={
                        'video_id': info.get('id'),
                        'uploader': info.get('uploader'),
                        'upload_date': info.get('upload_date'),
                        'view_count': info.get('view_count'),
                        'like_count': info.get('like_count'),
                        'description': info.get('description'),
                        'thumbnail_url': info.get('thumbnail'),
                        'format': info.get('format'),
                        'quality': info.get('height'),
                    }
                )
                
                logger.info(f"✅ تم تحميل الفيديو بنجاح: {file_path}")
                return result
                
        except DownloadError as e:
            logger.error(f"❌ خطأ في تحميل yt-dlp: {e}")
            return DownloadResult(
                success=False,
                error_message=str(e)
            )
        except Exception as e:
            logger.error(f"❌ خطأ غير متوقع في yt-dlp: {e}")
            return DownloadResult(
                success=False,
                error_message=f"خطأ غير متوقع: {str(e)}"
            )
    
    def _find_downloaded_file(self, info: Dict[str, Any], output_template: str) -> Optional[Path]:
        """العثور على الملف المحمل"""
        try:
            # إنشاء اسم الملف المتوقع
            filename = yt_dlp.utils.sanitize_filename(
                output_template.replace('%(title)s', info.get('title', 'video'))
                .replace('%(id)s', info.get('id', 'unknown'))
                .replace('%(ext)s', info.get('ext', 'mp4'))
            )
            
            # البحث في مجلد التحميل
            download_dir = Path(output_template).parent
            for file_path in download_dir.glob(f"*{info.get('id')}*"):
                if file_path.is_file():
                    return file_path
            
            return None
            
        except Exception as e:
            logger.error(f"❌ خطأ في العثور على الملف: {e}")
            return None
    
    def get_video_info(self, url: str) -> Optional[VideoInfo]:
        """الحصول على معلومات الفيديو"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return None
                
                return VideoInfo(
                    title=info.get('title', 'Unknown'),
                    duration=info.get('duration', 0),
                    file_size=info.get('filesize', 0),
                    format=info.get('ext', 'mp4'),
                    quality=info.get('height', 'unknown'),
                    thumbnail_url=info.get('thumbnail', ''),
                    description=info.get('description', '')
                )
                
        except Exception as e:
            logger.error(f"❌ خطأ في الحصول على معلومات الفيديو: {e}")
            return None
    
    def get_available_formats(self, url: str) -> Dict[str, Any]:
        """الحصول على التنسيقات المتاحة"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'listformats': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return {}
                
                formats = info.get('formats', [])
                available_formats = {
                    'video': [],
                    'audio': [],
                    'best': None,
                    'worst': None
                }
                
                for fmt in formats:
                    format_info = {
                        'format_id': fmt.get('format_id'),
                        'ext': fmt.get('ext'),
                        'filesize': fmt.get('filesize'),
                        'height': fmt.get('height'),
                        'width': fmt.get('width'),
                        'fps': fmt.get('fps'),
                        'vcodec': fmt.get('vcodec'),
                        'acodec': fmt.get('acodec'),
                    }
                    
                    if fmt.get('vcodec') != 'none':
                        available_formats['video'].append(format_info)
                    elif fmt.get('acodec') != 'none':
                        available_formats['audio'].append(format_info)
                
                # تحديد أفضل وأسوأ تنسيق
                if available_formats['video']:
                    available_formats['best'] = max(
                        available_formats['video'], 
                        key=lambda x: x.get('height', 0) or 0
                    )
                    available_formats['worst'] = min(
                        available_formats['video'], 
                        key=lambda x: x.get('height', 0) or 0
                    )
                
                return available_formats
                
        except Exception as e:
            logger.error(f"❌ خطأ في الحصول على التنسيقات: {e}")
            return {}


# إضافة DownloadResult هنا لتجنب الاستيراد الدائري
@dataclass
class DownloadResult:
    """نتيجة التحميل"""
    success: bool
    file_path: Optional[Path] = None
    file_size: Optional[int] = None
    duration: Optional[int] = None
    title: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None