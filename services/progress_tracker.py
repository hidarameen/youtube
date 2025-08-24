"""
Real-time progress tracking system for downloads and uploads
Uses Redis for fast, distributed progress tracking with WebSocket-like updates
"""

import asyncio
import logging
import time
import json
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, asdict

from services.cache_manager import CacheManager
from utils.helpers import format_file_size, calculate_eta
from utils.formatters import format_duration, format_speed

logger = logging.getLogger(__name__)

@dataclass
class ProgressInfo:
    """Progress information data class"""
    task_id: str
    current_bytes: int
    total_bytes: int
    percentage: float
    speed: float
    eta: int
    status: str
    message: str
    start_time: float
    last_updated: float
    user_id: Optional[int] = None
    file_name: Optional[str] = None

class ProgressTracker:
    """Ultra high-performance progress tracking system"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        
        # Progress tracking
        self.download_progress: Dict[str, ProgressInfo] = {}
        self.upload_progress: Dict[str, ProgressInfo] = {}
        
        # Real-time performance optimization
        self.update_interval = 0.1  # Update every 100ms for ultra-smooth real-time animation
        self.last_updates: Dict[str, float] = {}
        
        # Real-time tracking data for precise calculations
        self.speed_history: Dict[str, List[Tuple[float, float]]] = {}  # task_id -> [(timestamp, speed)]
        self.progress_samples: Dict[str, List[Tuple[float, float, float]]] = {}  # task_id -> [(time, current, total)]
        self.instant_speeds: Dict[str, float] = {}  # Real-time speed calculation
        self.accurate_eta: Dict[str, float] = {}  # More accurate ETA calculation
        
        # Enhanced Animation tracking
        self.animation_frames: Dict[str, int] = {}  # Track animation frame for each task
        self.animation_styles: Dict[str, str] = {}  # Track animation style for each task
        self.user_preferences: Dict[int, Dict] = {}  # Store user animation preferences
        self.start_times: Dict[str, float] = {}     # Track start time for each task
        
        # Cleanup settings
        self.max_progress_age = 3600  # Keep progress for 1 hour
        
        # Progress persistence
        self.persist_progress = True
        
        # Performance monitoring
        self.performance_metrics: Dict[str, Any] = {
            'total_updates': 0,
            'average_update_time': 0,
            'peak_concurrent_tasks': 0
        }
        
        # Background tasks
        self.cleanup_task: Optional[asyncio.Task] = None
        
    async def initialize(self):
        """Initialize progress tracker"""
        try:
            logger.info("🔧 Initializing progress tracker...")
            
            # Start cleanup task
            self.cleanup_task = asyncio.create_task(self._cleanup_old_progress())
            
            logger.info("✅ Progress tracker initialized")
            
        except Exception as e:
            logger.error(f"❌ Progress tracker initialization failed: {e}")
            raise
    
    async def update_download_progress(
        self,
        task_id: str,
        current_bytes: int,
        total_bytes: int,
        message: str = "",
        user_id: Optional[int] = None,
        file_name: Optional[str] = None
    ):
        """Update download progress with throttling for performance"""
        try:
            current_time = time.time()
            
            # Throttle updates for performance
            if task_id in self.last_updates:
                if current_time - self.last_updates[task_id] < self.update_interval:
                    return
            
            self.last_updates[task_id] = current_time
            
            # Calculate progress metrics
            percentage = (current_bytes / total_bytes * 100) if total_bytes > 0 else 0
            
            # Real-time speed and ETA calculation with accuracy
            speed = 0
            eta = 0
            start_time = current_time
            
            if task_id in self.download_progress:
                existing = self.download_progress[task_id]
                start_time = existing.start_time
                elapsed_time = current_time - start_time
                
                # Calculate instant speed using samples
                speed = self._calculate_realtime_speed(task_id, current_bytes, current_time)
                
                # Calculate more accurate ETA using recent speed trends
                eta = self._calculate_accurate_eta(task_id, current_bytes, total_bytes, speed)
                
                # Store progress sample for better calculations
                self._store_progress_sample(task_id, current_time, current_bytes, total_bytes)
            
            # Create progress info
            progress = ProgressInfo(
                task_id=task_id,
                current_bytes=current_bytes,
                total_bytes=total_bytes,
                percentage=percentage,
                speed=speed,
                eta=int(eta),
                status="downloading" if current_bytes < total_bytes else "completed",
                message=message,
                start_time=start_time,
                last_updated=current_time,
                user_id=user_id,
                file_name=file_name
            )
            
            # Store in memory
            self.download_progress[task_id] = progress
            
            # Store in Redis for persistence and sharing
            await self._store_progress_in_cache("download", task_id, progress)
            
            # Log significant progress milestones
            if percentage > 0 and percentage % 25 == 0:
                logger.info(f"📥 Download {task_id}: {percentage:.1f}% completed "
                          f"({format_file_size(int(current_bytes))}/{format_file_size(int(total_bytes))}) "
                          f"Speed: {format_file_size(int(speed))}/s")
            
        except Exception as e:
            logger.error(f"❌ Failed to update download progress for {task_id}: {e}")
    
    async def update_upload_progress(
        self,
        task_id: str,
        current_bytes: int,
        total_bytes: int,
        message: str = "",
        user_id: Optional[int] = None,
        file_name: Optional[str] = None
    ):
        """Update upload progress with throttling for performance"""
        try:
            current_time = time.time()
            
            # Throttle updates for performance
            if task_id in self.last_updates:
                if current_time - self.last_updates[task_id] < self.update_interval:
                    return
            
            self.last_updates[task_id] = current_time
            
            # Calculate progress metrics
            percentage = (current_bytes / total_bytes * 100) if total_bytes > 0 else 0
            
            # Real-time speed and ETA calculation for uploads
            speed = 0
            eta = 0
            start_time = current_time
            
            if task_id in self.upload_progress:
                existing = self.upload_progress[task_id]
                start_time = existing.start_time
                elapsed_time = current_time - start_time
                
                # Calculate instant upload speed using samples
                speed = self._calculate_realtime_speed(task_id, current_bytes, current_time)
                
                # Calculate more accurate ETA using recent speed trends
                eta = self._calculate_accurate_eta(task_id, current_bytes, total_bytes, speed)
                
                # Store progress sample for better calculations
                self._store_progress_sample(task_id, current_time, current_bytes, total_bytes)
            
            # Create progress info
            progress = ProgressInfo(
                task_id=task_id,
                current_bytes=current_bytes,
                total_bytes=total_bytes,
                percentage=percentage,
                speed=speed,
                eta=int(eta),
                status="uploading" if current_bytes < total_bytes else "completed",
                message=message,
                start_time=start_time,
                last_updated=current_time,
                user_id=user_id,
                file_name=file_name
            )
            
            # Store in memory
            self.upload_progress[task_id] = progress
            
            # Store in Redis for persistence and sharing
            await self._store_progress_in_cache("upload", task_id, progress)
            
            # Log significant progress milestones
            if percentage > 0 and percentage % 25 == 0:
                logger.info(f"📤 Upload {task_id}: {percentage:.1f}% completed "
                          f"({format_file_size(int(current_bytes))}/{format_file_size(int(total_bytes))}) "
                          f"Speed: {format_file_size(int(speed))}/s")
            
        except Exception as e:
            logger.error(f"❌ Failed to update upload progress for {task_id}: {e}")
    
    async def _store_progress_in_cache(self, operation_type: str, task_id: str, progress: ProgressInfo):
        """Store progress information in Redis cache"""
        try:
            cache_key = f"progress:{operation_type}:{task_id}"
            progress_data = asdict(progress)
            
            await self.cache_manager.set(
                cache_key,
                json.dumps(progress_data, default=str),
                expire=self.max_progress_age
            )
            
        except Exception as e:
            logger.warning(f"Failed to cache progress for {task_id}: {e}")
    
    async def get_download_progress(self, task_id: str) -> Dict[str, Any]:
        """Get current download progress"""
        try:
            # Check memory first
            if task_id in self.download_progress:
                progress = self.download_progress[task_id]
                return self._format_progress_response(progress)
            
            # Check Redis cache
            cache_key = f"progress:download:{task_id}"
            cached_data = await self.cache_manager.get(cache_key)
            
            if cached_data:
                progress_data = json.loads(cached_data)
                return self._format_progress_dict(progress_data)
            
            return {'task_id': task_id, 'status': 'not_found', 'message': 'Task not found'}
            
        except Exception as e:
            logger.error(f"Failed to get download progress for {task_id}: {e}")
            return {'task_id': task_id, 'status': 'error', 'message': str(e)}
    
    async def get_upload_progress(self, task_id: str) -> Dict[str, Any]:
        """Get current upload progress"""
        try:
            # Check memory first
            if task_id in self.upload_progress:
                progress = self.upload_progress[task_id]
                return self._format_progress_response(progress)
            
            # Check Redis cache
            cache_key = f"progress:upload:{task_id}"
            cached_data = await self.cache_manager.get(cache_key)
            
            if cached_data:
                progress_data = json.loads(cached_data)
                return self._format_progress_dict(progress_data)
            
            return {'task_id': task_id, 'status': 'not_found', 'message': 'Task not found'}
            
        except Exception as e:
            logger.error(f"Failed to get upload progress for {task_id}: {e}")
            return {'task_id': task_id, 'status': 'error', 'message': str(e)}
    
    def _format_progress_response(self, progress: ProgressInfo) -> Dict[str, Any]:
        """Format progress info for response"""
        elapsed_time = time.time() - progress.start_time
        
        return {
            'task_id': progress.task_id,
            'current_bytes': progress.current_bytes,
            'total_bytes': progress.total_bytes,
            'percentage': round(progress.percentage, 1),
            'speed': progress.speed,
            'eta': progress.eta,
            'status': progress.status,
            'message': progress.message,
            'elapsed_time': elapsed_time,
            'user_id': progress.user_id,
            'file_name': progress.file_name,
            
            # Formatted strings for display
            'current_str': format_file_size(progress.current_bytes),
            'total_str': format_file_size(progress.total_bytes),
            'speed_str': format_speed(progress.speed),
            'eta_str': format_duration(progress.eta),
            'elapsed_str': format_duration(elapsed_time),
            'progress_bar': self._create_progress_bar(progress.percentage, progress.task_id)
        }
    
    def _format_progress_dict(self, progress_data: Dict) -> Dict[str, Any]:
        """Format progress dictionary for response"""
        current_time = time.time()
        elapsed_time = current_time - progress_data.get('start_time', current_time)
        
        percentage = progress_data.get('percentage', 0)
        speed = progress_data.get('speed', 0)
        eta = progress_data.get('eta', 0)
        
        return {
            'task_id': progress_data.get('task_id', ''),
            'current_bytes': progress_data.get('current_bytes', 0),
            'total_bytes': progress_data.get('total_bytes', 0),
            'percentage': round(percentage, 1),
            'speed': speed,
            'eta': eta,
            'status': progress_data.get('status', 'unknown'),
            'message': progress_data.get('message', ''),
            'elapsed_time': elapsed_time,
            'user_id': progress_data.get('user_id'),
            'file_name': progress_data.get('file_name'),
            
            # Formatted strings for display
            'current_str': format_file_size(progress_data.get('current_bytes', 0)),
            'total_str': format_file_size(progress_data.get('total_bytes', 0)),
            'speed_str': format_speed(speed),
            'eta_str': format_duration(eta),
            'elapsed_str': format_duration(elapsed_time),
            'progress_bar': self._create_progress_bar(percentage)
        }
    
    def _create_progress_bar(self, percentage: float, task_id: str = "", length: int = 20) -> str:
        """Create an animated visual progress bar"""
        from static.icons import Icons
        
        filled = int(percentage / 100 * length)
        
        # Get current animation frame
        if task_id:
            if task_id not in self.animation_frames:
                self.animation_frames[task_id] = 0
            frame_index = self.animation_frames[task_id] % len(Icons.PROGRESS_FRAMES)
            self.animation_frames[task_id] += 1
            progress_char = Icons.PROGRESS_FRAMES[frame_index]
        else:
            progress_char = "█"
        
        # Create animated bar
        if percentage < 100:
            # Show animation at the progress edge
            if filled > 0:
                bar = '█' * (filled - 1) + progress_char + '░' * (length - filled)
            else:
                bar = progress_char + '░' * (length - 1)
        else:
            # Completed - show full bar with success animation
            bar = '█' * length
            
        return f"[{bar}] {percentage:.1f}%"
    
    async def get_user_progress(self, user_id: int) -> Dict[str, List[Dict[str, Any]]]:
        """Get all progress for a specific user"""
        user_downloads = []
        user_uploads = []
        
        # Check downloads
        for task_id, progress in self.download_progress.items():
            if progress.user_id == user_id:
                user_downloads.append(self._format_progress_response(progress))
        
        # Check uploads
        for task_id, progress in self.upload_progress.items():
            if progress.user_id == user_id:
                user_uploads.append(self._format_progress_response(progress))
        
        return {
            'downloads': user_downloads,
            'uploads': user_uploads,
            'total_active': len(user_downloads) + len(user_uploads)
        }
    
    async def get_all_active_progress(self) -> Dict[str, Any]:
        """Get all active progress for monitoring"""
        downloads = []
        uploads = []
        
        for progress in self.download_progress.values():
            downloads.append(self._format_progress_response(progress))
        
        for progress in self.upload_progress.values():
            uploads.append(self._format_progress_response(progress))
        
        return {
            'downloads': downloads,
            'uploads': uploads,
            'total_downloads': len(downloads),
            'total_uploads': len(uploads),
            'total_active': len(downloads) + len(uploads)
        }
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a task and update its progress"""
        try:
            cancelled = False
            
            # Cancel download
            if task_id in self.download_progress:
                progress = self.download_progress[task_id]
                progress.status = "cancelled"
                progress.message = "Cancelled by user"
                await self._store_progress_in_cache("download", task_id, progress)
                cancelled = True
            
            # Cancel upload
            if task_id in self.upload_progress:
                progress = self.upload_progress[task_id]
                progress.status = "cancelled"
                progress.message = "Cancelled by user"
                await self._store_progress_in_cache("upload", task_id, progress)
                cancelled = True
            
            if cancelled:
                logger.info(f"📝 Task {task_id} marked as cancelled")
            
            return cancelled
            
        except Exception as e:
            logger.error(f"Failed to cancel task {task_id}: {e}")
            return False
    
    async def remove_completed_tasks(self, max_age_seconds: int = 300):
        """Remove completed tasks older than specified age"""
        try:
            current_time = time.time()
            removed_count = 0
            
            # Remove old download progress
            to_remove = []
            for task_id, progress in self.download_progress.items():
                if (progress.status in ['completed', 'cancelled', 'failed'] and 
                    current_time - progress.last_updated > max_age_seconds):
                    to_remove.append(task_id)
            
            for task_id in to_remove:
                del self.download_progress[task_id]
                removed_count += 1
            
            # Remove old upload progress
            to_remove = []
            for task_id, progress in self.upload_progress.items():
                if (progress.status in ['completed', 'cancelled', 'failed'] and 
                    current_time - progress.last_updated > max_age_seconds):
                    to_remove.append(task_id)
            
            for task_id in to_remove:
                del self.upload_progress[task_id]
                removed_count += 1
            
            if removed_count > 0:
                logger.info(f"🗑️ Removed {removed_count} completed/old progress entries")
            
        except Exception as e:
            logger.error(f"Failed to remove completed tasks: {e}")
    
    async def _cleanup_old_progress(self):
        """Background task to clean up old progress entries"""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                await self.remove_completed_tasks()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Progress cleanup error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def get_performance_stats(self) -> Dict[str, Any]:
        """Get progress tracker performance statistics"""
        current_time = time.time()
        
        # Count active tasks
        active_downloads = sum(1 for p in self.download_progress.values() 
                             if p.status == 'downloading')
        active_uploads = sum(1 for p in self.upload_progress.values() 
                           if p.status == 'uploading')
        
        # Calculate average speeds
        download_speeds = [p.speed for p in self.download_progress.values() 
                          if p.status == 'downloading' and p.speed > 0]
        upload_speeds = [p.speed for p in self.upload_progress.values() 
                        if p.status == 'uploading' and p.speed > 0]
        
        avg_download_speed = sum(download_speeds) / len(download_speeds) if download_speeds else 0
        avg_upload_speed = sum(upload_speeds) / len(upload_speeds) if upload_speeds else 0
        
        return {
            'total_downloads_tracked': len(self.download_progress),
            'total_uploads_tracked': len(self.upload_progress),
            'active_downloads': active_downloads,
            'active_uploads': active_uploads,
            'avg_download_speed': avg_download_speed,
            'avg_upload_speed': avg_upload_speed,
            'avg_download_speed_str': format_speed(avg_download_speed),
            'avg_upload_speed_str': format_speed(avg_upload_speed),
            'update_interval': self.update_interval,
            'max_progress_age': self.max_progress_age
        }
    
    async def stop(self):
        """Stop the progress tracker and cleanup"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
    
    def _calculate_realtime_speed(self, task_id: str, current_bytes: int, current_time: float) -> float:
        """Calculate real-time speed using recent samples for accuracy"""
        try:
            # Get or create speed history
            if task_id not in self.speed_history:
                self.speed_history[task_id] = []
            
            speed_history = self.speed_history[task_id]
            
            # Add current sample
            speed_history.append((current_time, current_bytes))
            
            # Keep only recent samples (last 10 seconds)
            cutoff_time = current_time - 10
            speed_history[:] = [(t, b) for t, b in speed_history if t > cutoff_time]
            
            # Calculate speed based on recent samples
            if len(speed_history) < 2:
                return 0
            
            # Use linear regression for more accurate speed
            total_time_diff = 0
            total_bytes_diff = 0
            sample_count = min(len(speed_history), 5)  # Use last 5 samples
            
            for i in range(1, sample_count):
                time_diff = speed_history[i][0] - speed_history[i-1][0]
                bytes_diff = speed_history[i][1] - speed_history[i-1][1]
                
                if time_diff > 0:
                    total_time_diff += time_diff
                    total_bytes_diff += bytes_diff
            
            if total_time_diff > 0:
                instant_speed = total_bytes_diff / total_time_diff
                self.instant_speeds[task_id] = instant_speed
                return max(0, instant_speed)  # Ensure positive speed
            
            return self.instant_speeds.get(task_id, 0)
            
        except Exception as e:
            logger.warning(f"Speed calculation error for {task_id}: {e}")
            return 0
    
    def _calculate_accurate_eta(self, task_id: str, current_bytes: int, total_bytes: int, current_speed: float) -> float:
        """Calculate more accurate ETA using speed trends and adaptive algorithms"""
        try:
            if current_speed <= 0 or current_bytes >= total_bytes:
                return 0
            
            remaining_bytes = total_bytes - current_bytes
            
            # Simple ETA based on current speed
            basic_eta = remaining_bytes / current_speed
            
            # Get speed history for trend analysis
            if task_id in self.speed_history and len(self.speed_history[task_id]) > 3:
                speeds = []
                recent_samples = self.speed_history[task_id][-5:]  # Last 5 samples
                
                for i in range(1, len(recent_samples)):
                    time_diff = recent_samples[i][0] - recent_samples[i-1][0]
                    bytes_diff = recent_samples[i][1] - recent_samples[i-1][1]
                    if time_diff > 0:
                        speeds.append(bytes_diff / time_diff)
                
                if speeds:
                    # Calculate trend (is speed increasing/decreasing?)
                    if len(speeds) > 1:
                        trend = (speeds[-1] - speeds[0]) / len(speeds)
                        
                        # Adjust ETA based on trend
                        if trend > 0:  # Speed increasing
                            adjusted_speed = current_speed + (trend * 5)  # Project 5 seconds ahead
                            basic_eta = remaining_bytes / max(adjusted_speed, current_speed * 0.5)
                        elif trend < 0:  # Speed decreasing
                            adjusted_speed = current_speed + (trend * 5)
                            basic_eta = remaining_bytes / max(adjusted_speed, current_speed * 0.3)
            
            self.accurate_eta[task_id] = basic_eta
            return basic_eta
            
        except Exception as e:
            logger.warning(f"ETA calculation error for {task_id}: {e}")
            return 0
    
    def _store_progress_sample(self, task_id: str, timestamp: float, current_bytes: int, total_bytes: int):
        """Store progress sample for trend analysis"""
        try:
            if task_id not in self.progress_samples:
                self.progress_samples[task_id] = []
            
            samples = self.progress_samples[task_id]
            samples.append((timestamp, current_bytes, total_bytes))
            
            # Keep only recent samples (last 30 seconds)
            cutoff_time = timestamp - 30
            samples[:] = [(t, c, tot) for t, c, tot in samples if t > cutoff_time]
            
        except Exception as e:
            logger.warning(f"Failed to store progress sample for {task_id}: {e}")
    
    def get_realtime_stats(self, task_id: str) -> Dict[str, Any]:
        """Get real-time statistics for a task"""
        try:
            stats = {
                'instant_speed': self.instant_speeds.get(task_id, 0),
                'instant_speed_str': format_speed(self.instant_speeds.get(task_id, 0)),
                'accurate_eta': self.accurate_eta.get(task_id, 0),
                'accurate_eta_str': format_duration(self.accurate_eta.get(task_id, 0)),
                'sample_count': len(self.speed_history.get(task_id, [])),
                'trend_available': len(self.speed_history.get(task_id, [])) > 3
            }
            
            # Calculate speed trend if available
            if task_id in self.speed_history and len(self.speed_history[task_id]) > 3:
                recent_speeds = []
                samples = self.speed_history[task_id][-5:]
                
                for i in range(1, len(samples)):
                    time_diff = samples[i][0] - samples[i-1][0]
                    bytes_diff = samples[i][1] - samples[i-1][1]
                    if time_diff > 0:
                        recent_speeds.append(bytes_diff / time_diff)
                
                if len(recent_speeds) > 1:
                    trend = (recent_speeds[-1] - recent_speeds[0]) / len(recent_speeds)
                    stats['speed_trend'] = 'increasing' if trend > 0 else 'decreasing' if trend < 0 else 'stable'
                    stats['speed_trend_value'] = trend
                else:
                    stats['speed_trend'] = 'stable'
                    stats['speed_trend_value'] = 0
            else:
                stats['speed_trend'] = 'unknown'
                stats['speed_trend_value'] = 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get real-time stats for {task_id}: {e}")
            return {}
    
    async def cleanup_task_data(self, task_id: str):
        """Clean up all tracking data for a completed/cancelled task"""
        try:
            # Clean up speed history
            if task_id in self.speed_history:
                del self.speed_history[task_id]
            
            # Clean up progress samples
            if task_id in self.progress_samples:
                del self.progress_samples[task_id]
            
            # Clean up instant data
            if task_id in self.instant_speeds:
                del self.instant_speeds[task_id]
            
            if task_id in self.accurate_eta:
                del self.accurate_eta[task_id]
            
            # Clean up animation data
            if task_id in self.animation_frames:
                del self.animation_frames[task_id]
            
            if task_id in self.animation_styles:
                del self.animation_styles[task_id]
            
            logger.debug(f"🗑️ Cleaned up tracking data for task: {task_id}")
            
        except Exception as e:
            logger.warning(f"Failed to cleanup task data for {task_id}: {e}")
        
        logger.info("🛑 Progress tracker stopped")
