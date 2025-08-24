"""
Enhanced progress animations and interactive messages
Beautiful progress bars with animations and dynamic content
"""

import time
import asyncio
from typing import Dict, List, Optional
from static.icons import Icons

class ProgressAnimator:
    """Advanced progress animations with beautiful effects"""
    
    def __init__(self):
        self.animation_states: Dict[str, int] = {}
        self.last_update: Dict[str, float] = {}
        
    def get_animated_progress_bar(self, percentage: float, task_id: str = "", style: str = "default") -> str:
        """Create beautiful animated progress bar"""
        current_time = time.time()
        
        # Update animation frame
        if task_id not in self.animation_states:
            self.animation_states[task_id] = 0
        if task_id not in self.last_update:
            self.last_update[task_id] = current_time
            
        # Update every 0.5 seconds for smooth animation
        if current_time - self.last_update[task_id] > 0.5:
            self.animation_states[task_id] = (self.animation_states[task_id] + 1) % 10
            self.last_update[task_id] = current_time
            
        frame = self.animation_states[task_id]
        
        if style == "rainbow":
            return self._create_rainbow_progress(percentage, frame)
        elif style == "fire":
            return self._create_fire_progress(percentage, frame)
        elif style == "pulse":
            return self._create_pulse_progress(percentage, frame)
        else:
            return self._create_default_progress(percentage, frame)
    
    def _create_default_progress(self, percentage: float, frame: int) -> str:
        """Default animated progress bar"""
        length = 20
        filled = int(percentage / 100 * length)
        
        # Animation character
        spinner = Icons.PROGRESS_FRAMES[frame % len(Icons.PROGRESS_FRAMES)]
        
        if percentage >= 100:
            success_icon = Icons.SUCCESS_FRAMES[frame % len(Icons.SUCCESS_FRAMES)]
            return f"[{'█' * length}] {success_icon} 100%"
        elif filled > 0:
            bar = '█' * (filled - 1) + spinner + '░' * (length - filled)
        else:
            bar = spinner + '░' * (length - 1)
            
        return f"[{bar}] {percentage:.1f}%"
    
    def _create_rainbow_progress(self, percentage: float, frame: int) -> str:
        """Rainbow colored progress bar"""
        length = 20
        filled = int(percentage / 100 * length)
        
        if percentage >= 100:
            rainbow_bar = ''.join(Icons.RAINBOW_PROGRESS[i % len(Icons.RAINBOW_PROGRESS)] for i in range(6))
            return f"[{rainbow_bar}] {Icons.PARTY} 100%"
        
        rainbow_char = Icons.RAINBOW_PROGRESS[frame % len(Icons.RAINBOW_PROGRESS)]
        
        if filled > 0:
            bar = '█' * (filled - 1) + rainbow_char + '░' * (length - filled)
        else:
            bar = rainbow_char + '░' * (length - 1)
            
        return f"[{bar}] {rainbow_char} {percentage:.1f}%"
    
    def _create_fire_progress(self, percentage: float, frame: int) -> str:
        """Fire themed progress bar"""
        length = 20
        filled = int(percentage / 100 * length)
        
        fire_char = Icons.FIRE_FRAMES[frame % len(Icons.FIRE_FRAMES)]
        
        if percentage >= 100:
            return f"[{'🔥' * 6}] {Icons.ROCKET} 100%"
        elif filled > 0:
            bar = '█' * (filled - 1) + fire_char + '░' * (length - filled)
        else:
            bar = fire_char + '░' * (length - 1)
            
        return f"[{bar}] {fire_char} {percentage:.1f}%"
    
    def _create_pulse_progress(self, percentage: float, frame: int) -> str:
        """Pulsing stars progress bar"""
        length = 20
        filled = int(percentage / 100 * length)
        
        pulse_char = Icons.PULSE_FRAMES[frame % len(Icons.PULSE_FRAMES)]
        
        if percentage >= 100:
            return f"[{'⭐' * 6}] {Icons.MAGIC} 100%"
        elif filled > 0:
            bar = '█' * (filled - 1) + pulse_char + '░' * (length - filled)
        else:
            bar = pulse_char + '░' * (length - 1)
            
        return f"[{bar}] {pulse_char} {percentage:.1f}%"

class InteractiveMessages:
    """Beautiful interactive messages with animations"""
    
    @staticmethod
    def get_welcome_message(username: str = "") -> str:
        """Animated welcome message"""
        user_part = f" {username}" if username else ""
        return f"""
{Icons.WELCOME} <b>أهلاً وسهلاً{user_part}!</b>

{Icons.ROCKET} <b>مرحباً بك في Ultra Video Downloader Bot!</b>

{Icons.SPARKLES} <b>المميزات:</b>
• {Icons.YOUTUBE} تحميل من YouTube، Instagram، TikTok
• {Icons.FACEBOOK} دعم Facebook، Twitter، والمئات من المواقع
• {Icons.LIGHTNING} سرعة فائقة وملفات تصل لـ 2GB
• {Icons.MAGIC} جودة عالية وتحميل متزامن

{Icons.FIRE} <b>أرسل رابط الفيديو الآن وابدأ التحميل!</b>
        """
    
    @staticmethod
    def get_processing_message(platform: str, animated_progress: str) -> str:
        """Animated processing message"""
        platform_icon = {
            'youtube': Icons.YOUTUBE,
            'instagram': Icons.INSTAGRAM,
            'facebook': Icons.FACEBOOK,
            'tiktok': Icons.TIKTOK,
            'twitter': Icons.TWITTER
        }.get(platform, Icons.VIDEO)
        
        return f"""
{Icons.PROCESSING} <b>جارٍ المعالجة...</b>

{platform_icon} <b>المنصة:</b> {platform.title()}
{Icons.LIGHTNING} <b>حالة التحليل:</b> جارٍ استخراج معلومات الفيديو

{animated_progress}

{Icons.MAGIC} <i>يتم تحضير الفيديو بجودة عالية لك...</i>
        """
    
    @staticmethod
    def get_download_message(video_title: str, progress_bar: str, speed: str, eta: str) -> str:
        """Animated download progress message"""
        downloading_icon = Icons.DOWNLOADING_FRAMES[int(time.time() * 2) % len(Icons.DOWNLOADING_FRAMES)]
        
        return f"""
{downloading_icon} <b>جارٍ التحميل...</b>

{Icons.VIDEO} <b>الفيديو:</b> {video_title}

{progress_bar}

{Icons.LIGHTNING} <b>السرعة:</b> {speed}
{Icons.PROCESSING} <b>الوقت المتبقي:</b> {eta}

{Icons.SPARKLES} <i>التحميل جارٍ بأقصى سرعة...</i>
        """
    
    @staticmethod
    def get_upload_message(video_title: str, progress_bar: str, speed: str) -> str:
        """Animated upload progress message"""
        uploading_icon = Icons.UPLOADING_FRAMES[int(time.time() * 2) % len(Icons.UPLOADING_FRAMES)]
        
        return f"""
{uploading_icon} <b>جارٍ الرفع...</b>

{Icons.VIDEO} <b>الفيديو:</b> {video_title}

{progress_bar}

{Icons.ROCKET} <b>سرعة الرفع:</b> {speed}

{Icons.FIRE} <i>يتم رفع الفيديو بتقنية فائقة السرعة...</i>
        """
    
    @staticmethod
    def get_success_message(video_title: str, file_size: str, total_time: str) -> str:
        """Animated success message"""
        success_icon = Icons.SUCCESS_FRAMES[int(time.time()) % len(Icons.SUCCESS_FRAMES)]
        
        return f"""
{success_icon} <b>تم التحميل بنجاح!</b>

{Icons.VIDEO} <b>الفيديو:</b> {video_title}
{Icons.FILE} <b>حجم الملف:</b> {file_size}
{Icons.PROCESSING} <b>وقت التحميل:</b> {total_time}

{Icons.PARTY} <b>الفيديو جاهز للمشاهدة!</b>
{Icons.THUMBS_UP} <b>شكراً لاستخدام البوت!</b>

{Icons.MAGIC} <i>أرسل رابطاً آخر لتحميل المزيد...</i>
        """
    
    @staticmethod
    def get_error_message(error_type: str, suggestion: str = "") -> str:
        """Animated error message with helpful suggestions"""
        return f"""
{Icons.ERROR} <b>حدث خطأ في التحميل</b>

{Icons.WARNING} <b>نوع الخطأ:</b> {error_type}

{Icons.INFO} <b>الحلول المقترحة:</b>
• {Icons.REFRESH} جرب مرة أخرى
• {Icons.CHECKMARK} تأكد من صحة الرابط
• {Icons.NETWORK} تحقق من الاتصال بالإنترنت

{suggestion}

{Icons.HEART} <b>نحن هنا لمساعدتك!</b>
        """

# Global animator instance
progress_animator = ProgressAnimator()