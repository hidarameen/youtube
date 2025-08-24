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
        """Ultra-modern animated progress bar with smooth movement"""
        length = 25
        filled = int(percentage / 100 * length)
        
        # Advanced animation characters with smooth movement
        moving_chars = ['▰', '▱', '▲', '►', '●', '◆', '★', '⚡']
        glow_chars = ['✨', '💫', '⭐', '🌟', '💎', '🔥', '⚡', '🚀']
        
        # Moving animation character
        moving_char = moving_chars[frame % len(moving_chars)]
        glow_char = glow_chars[frame % len(glow_chars)]
        
        if percentage >= 100:
            # Celebration animation for completion
            celebration = ['🎉', '🎊', '✨', '🏆', '🎯', '💯'][frame % 6]
            full_bar = ''.join(['█'] * length)
            return f"╭{'─' * (length + 2)}╮\n│ {full_bar} │ {celebration} 100%\n╰{'─' * (length + 2)}╯"
        
        elif filled > 0:
            # Create smooth animated progress with glow effect
            if filled >= length:
                filled = length - 1
            
            # Add glow effect around the moving character
            bar_parts = []
            for i in range(length):
                if i < filled - 1:
                    bar_parts.append('█')
                elif i == filled - 1:
                    # Moving character with glow
                    bar_parts.append(moving_char)
                elif i == filled and frame % 3 == 0:
                    # Occasional glow ahead
                    bar_parts.append(glow_char)
                else:
                    bar_parts.append('░')
            
            bar = ''.join(bar_parts)
        else:
            # Starting animation
            bar = moving_char + '░' * (length - 1)
        
        # Create beautiful bordered progress bar
        progress_text = f"╭{'─' * (length + 2)}╮\n│ {bar} │ {glow_char} {percentage:.1f}%\n╰{'─' * (length + 2)}╯"
        
        return progress_text
    
    def _create_rainbow_progress(self, percentage: float, frame: int) -> str:
        """Ultra-vibrant rainbow progress bar with flowing colors"""
        length = 25
        filled = int(percentage / 100 * length)
        
        # Rainbow colors that flow and change
        rainbow_sequence = ['🔴', '🟠', '🟡', '🟢', '🔵', '🟣', '🟤', '⚫', '⚪']
        rainbow_effects = ['🌈', '💫', '✨', '🎨', '🎪', '🎭', '🎊', '🎉']
        
        if percentage >= 100:
            # Epic rainbow completion
            rainbow_bar = ''.join(rainbow_sequence[i % len(rainbow_sequence)] for i in range(8))
            celebration = rainbow_effects[frame % len(rainbow_effects)]
            return f"""
╔═══════════════════════════════╗
║ {rainbow_bar} ║ {celebration} 100%
║    🌈 RAINBOW COMPLETE! 🌈    ║
╚═══════════════════════════════╝"""
        
        # Create flowing rainbow effect
        rainbow_char = rainbow_sequence[(frame + filled) % len(rainbow_sequence)]
        effect_char = rainbow_effects[frame % len(rainbow_effects)]
        
        if filled > 0:
            # Create gradient rainbow bar
            bar_parts = []
            for i in range(length):
                if i < filled - 1:
                    bar_parts.append(rainbow_sequence[i % len(rainbow_sequence)])
                elif i == filled - 1:
                    bar_parts.append(rainbow_char)
                else:
                    bar_parts.append('░')
            bar = ''.join(bar_parts)
        else:
            bar = rainbow_char + '░' * (length - 1)
        
        return f"""
╔═══════════════════════════════╗
║ {bar} ║ {effect_char} {percentage:.1f}%
╚═══════════════════════════════╝"""
    
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
        """Ultra-modern animated welcome message"""
        user_part = f" {username}" if username else ""
        frame_time = int(time.time() * 2) % 4
        
        # Animated title with changing effects
        title_effects = ['🚀', '⚡', '🔥', '💫']
        current_effect = title_effects[frame_time]
        
        return f"""
╔══════════════════════════════════════╗
║  {current_effect} <b>WELCOME{user_part}!</b> {current_effect}
║                                      ║
║   🎬 <b>ULTRA VIDEO DOWNLOADER BOT</b>   ║
║         💎 <i>Premium Experience</i> 💎        ║
╚══════════════════════════════════════╝

🌟 <b>SUPPORTED PLATFORMS:</b>
┌─────────────────────────────────────┐
│ 📺 YouTube        │ 📸 Instagram     │
│ 🎵 TikTok         │ 📘 Facebook      │
│ 🐦 Twitter/X      │ 🌐 1500+ Sites   │
└─────────────────────────────────────┘

⚡ <b>ULTRA FEATURES:</b>
▪️ Lightning-fast downloads up to 2GB
▪️ 4K/HD quality with multiple formats
▪️ Batch processing & queue management
▪️ Real-time progress with animations
▪️ Smart compression & optimization
▪️ Instagram cookies & private access

🎯 <b>READY TO START?</b>
Just send any video link and watch the magic happen!

✨ <i>Experience the future of video downloading...</i> ✨
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
{Icons.PROCESSING} <b>Processing...</b>

{platform_icon} <b>Platform:</b> {platform.title()}
{Icons.LIGHTNING} <b>Status:</b> Extracting video information

{animated_progress}

{Icons.MAGIC} <i>Preparing high-quality video for you...</i>
        """
    
    @staticmethod
    def get_download_message(video_title: str, progress_bar: str, speed: str, eta: str, 
                           percentage: float = 0, current_size: str = "", total_size: str = "",
                           instant_speed: str = "", speed_trend: str = "stable") -> str:
        """Ultra-modern real-time animated download progress message"""
        frame = int(time.time() * 4) % 8  # Faster animation
        
        # Dynamic downloading animation based on real percentage
        download_states = [
            "⬇️ INITIALIZING", "📡 CONNECTING", "🔄 BUFFERING", "📥 DOWNLOADING",
            "⚡ ACCELERATING", "🚀 TURBO MODE", "💨 ULTRA SPEED", "🔥 MAX POWER"
        ]
        
        # Status based on real-time percentage
        if percentage < 5:
            status = download_states[0]
        elif percentage < 15:
            status = download_states[1]
        elif percentage < 30:
            status = download_states[2]
        elif percentage < 50:
            status = download_states[3]
        elif percentage < 70:
            status = download_states[4]
        elif percentage < 85:
            status = download_states[5]
        elif percentage < 95:
            status = download_states[6]
        else:
            status = download_states[7]
        
        # Real-time speed indicators with trend
        speed_indicators = {
            'increasing': ['📈', '🚀', '⚡', '💫'],
            'decreasing': ['📉', '🐌', '⏳', '😴'],
            'stable': ['📊', '⚡', '🔄', '💨'],
            'unknown': ['❓', '🔍', '📊', '⚡']
        }
        
        current_indicators = speed_indicators.get(speed_trend, speed_indicators['stable'])
        speed_icon = current_indicators[frame % len(current_indicators)]
        
        # Progress percentage with visual feedback
        progress_visual = "▰" * int(percentage / 5) + "▱" * (20 - int(percentage / 5))
        
        # Real-time counters
        size_info = f"({current_size}/{total_size})" if current_size and total_size else ""
        instant_info = f"📶 <b>NOW:</b> {instant_speed}" if instant_speed else ""
        
        return f"""
╔═════════════════════════════════════════════════╗
║                  {status}                  ║
╠═════════════════════════════════════════════════╣
║                                                 ║
║ 🎬 <b>VIDEO:</b> {video_title[:40]}{'...' if len(video_title) > 40 else ''}
║                                                 ║
║ {progress_bar}
║ 📏 {progress_visual} {percentage:.1f}%
║                                                 ║
║ {speed_icon} <b>AVG SPEED:</b> {speed}
║ {instant_info}
║ ⏱️ <b>TIME LEFT:</b> {eta}
║ 📊 <b>SIZE:</b> {size_info}
║ 📈 <b>TREND:</b> {speed_trend.title()}
║                                                 ║
╚═════════════════════════════════════════════════╝

💡 <i>Real-time optimization in progress...</i>
⚡ <i>Ultra-fast parallel downloading active...</i>
🎯 <i>ETA calculated using smart algorithms...</i>
        """
    
    @staticmethod
    def get_upload_message(video_title: str, progress_bar: str, speed: str, 
                         percentage: float = 0, current_size: str = "", total_size: str = "",
                         eta: str = "", instant_speed: str = "", speed_trend: str = "stable") -> str:
        """Ultra-modern real-time animated upload progress message"""
        frame = int(time.time() * 4) % 8  # Faster animation for uploads
        
        # Dynamic upload states based on real percentage
        upload_states = [
            "📤 PREPARING", "🔗 CONNECTING", "📡 HANDSHAKE", "📤 UPLOADING",
            "🚀 ACCELERATING", "⚡ TURBO UPLOAD", "💨 BLAZING FAST", "🔥 MAXIMUM SPEED"
        ]
        
        # Real-time status
        if percentage < 5:
            status = upload_states[0]
        elif percentage < 15:
            status = upload_states[1]
        elif percentage < 25:
            status = upload_states[2]
        elif percentage < 50:
            status = upload_states[3]
        elif percentage < 70:
            status = upload_states[4]
        elif percentage < 85:
            status = upload_states[5]
        elif percentage < 95:
            status = upload_states[6]
        else:
            status = upload_states[7]
        
        # Upload-specific animations
        upload_indicators = {
            'increasing': ['🚀', '📈', '⚡', '💫'],
            'decreasing': ['🐌', '📉', '⏳', '😅'],
            'stable': ['📤', '💨', '🔄', '⚡'],
            'unknown': ['❓', '📡', '🔍', '📤']
        }
        
        current_indicators = upload_indicators.get(speed_trend, upload_indicators['stable'])
        upload_icon = current_indicators[frame % len(current_indicators)]
        
        # Progress visualization for uploads
        upload_visual = "🟦" * int(percentage / 5) + "⬜" * (20 - int(percentage / 5))
        
        # Size and time info
        size_info = f"({current_size}/{total_size})" if current_size and total_size else ""
        instant_info = f"📶 <b>NOW:</b> {instant_speed}" if instant_speed else ""
        eta_info = f"⏱️ <b>TIME LEFT:</b> {eta}" if eta else ""
        
        return f"""
╔═════════════════════════════════════════════════╗
║                  {status}                  ║
╠═════════════════════════════════════════════════╣
║                                                 ║
║ 🎬 <b>VIDEO:</b> {video_title[:40]}{'...' if len(video_title) > 40 else ''}
║                                                 ║
║ {progress_bar}
║ 📤 {upload_visual} {percentage:.1f}%
║                                                 ║
║ {upload_icon} <b>AVG SPEED:</b> {speed}
║ {instant_info}
║ {eta_info}
║ 📊 <b>SIZE:</b> {size_info}
║ 📈 <b>TREND:</b> {speed_trend.title()}
║                                                 ║
╚═════════════════════════════════════════════════╝

🚀 <i>Ultra-fast Telethon upload technology...</i>
⚡ <i>Optimized chunking for maximum speed...</i>
🎯 <i>Smart ETA calculation in real-time...</i>
        """
    
    @staticmethod
    def get_success_message(video_title: str, file_size: str, total_time: str, avg_speed: str = "") -> str:
        """Epic animated success message with celebration"""
        frame = int(time.time() * 2) % 6
        
        # Celebration animations
        celebrations = ['🎉', '🎊', '✨', '🏆', '🎯', '💯']
        party_effects = ['🥳', '🎈', '🎁', '🌟', '💫', '🔥']
        
        celebration = celebrations[frame]
        party = party_effects[frame]
        
        return f"""
╔═══════════════════════════════════════════╗
║          {celebration} SUCCESS! {celebration}          ║
║                                           ║
║      🏆 DOWNLOAD COMPLETED! 🏆      ║
║           {party} PERFECT! {party}           ║
╚═══════════════════════════════════════════╝

📋 <b>DOWNLOAD SUMMARY:</b>
┌─────────────────────────────────────────┐
│ 🎬 <b>Video:</b> {video_title[:30]}{'...' if len(video_title) > 30 else ''}
│ 📁 <b>Size:</b> {file_size}
│ ⏱️ <b>Time:</b> {total_time}
{'│ ⚡ <b>Speed:</b> ' + avg_speed if avg_speed else ''}
│ ✅ <b>Status:</b> Ready to Watch!
└─────────────────────────────────────────┘

🎯 <b>WHAT'S NEXT?</b>
▫️ Your video is ready in the chat above
▫️ High quality and optimized for viewing
▫️ Send another link for more downloads

🌟 <b>RATE YOUR EXPERIENCE:</b>
Did we exceed your expectations? Share feedback!

🚀 <i>Thanks for choosing Ultra Video Downloader!</i>
💫 <i>Send another link to continue the magic...</i>
        """
    
    @staticmethod
    def get_error_message(error_type: str, suggestion: str = "") -> str:
        """Animated error message with helpful suggestions"""
        return f"""
{Icons.ERROR} <b>Download Error Occurred</b>

{Icons.WARNING} <b>Error Type:</b> {error_type}

{Icons.INFO} <b>Suggested Solutions:</b>
• {Icons.REFRESH} Try again
• {Icons.CHECK} Make sure the link is correct
• {Icons.NETWORK} Check internet connection

{suggestion}

{Icons.HEART} <b>We're here to help!</b>
        """

# Global animator instance
progress_animator = ProgressAnimator()