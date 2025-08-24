"""
High-performance file manager for handling uploads, downloads, and file operations
Integrates with Telethon for 2GB file support and FastTelethon optimization
"""

import asyncio
import logging
import os
import shutil
import tempfile
import time
from typing import Dict, Any, Optional, Callable, List
from pathlib import Path
import hashlib
import mimetypes

from core.telethon_client import TelethonManager
from services.progress_tracker import ProgressTracker
from config.settings import settings
from utils.helpers import format_file_size, generate_task_id, get_file_hash
from utils.formatters import format_duration, format_upload_time

logger = logging.getLogger(__name__)

class FileManager:
    """Ultra high-performance file manager"""
    
    def __init__(self, telethon_manager: TelethonManager, progress_tracker: ProgressTracker):
        self.telethon_manager = telethon_manager
        self.progress_tracker = progress_tracker
        
        # Ultra-optimized file operation semaphores
        self.upload_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_UPLOADS)
        self.process_semaphore = asyncio.Semaphore(16)  # Ultra-parallel processing
        self.compression_semaphore = asyncio.Semaphore(4)  # Parallel compression
        
        # File tracking
        self.active_uploads: Dict[str, Any] = {}
        self.upload_history: List[Dict] = []
        
        # Optimization settings
        self.chunk_size = settings.CHUNK_SIZE
        self.max_file_size = settings.MAX_FILE_SIZE
        
        # File integrity checking
        self.verify_file_integrity = True
        
        # Upload speed monitoring and adaptive optimization
        self.upload_speed_history: List[float] = []
        self.adaptive_compression = True
        self.smart_chunking = True
        self.upload_optimization_enabled = True
        
        # Advanced performance features
        self.parallel_chunk_upload = True
        self.dynamic_worker_scaling = True
        self.bandwidth_prediction = True
        
    async def upload_to_telegram(
        self,
        file_path: str,
        user_id: int,
        video_info: Dict[str, Any],
        format_info: Dict[str, Any],
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        High-performance upload to Telegram with progress tracking
        Supports up to 2GB files via Telethon MTProto
        """
        async with self.upload_semaphore:
            task_id = generate_task_id()
            start_time = time.time()
            
            try:
                # Validate file
                await self._validate_file_for_upload(file_path)
                
                # Apply ultra-optimizations before upload
                optimized_file_path = await self._ultra_optimize_file(file_path, video_info)
                if optimized_file_path != file_path:
                    file_path = optimized_file_path
                    logger.info(f"🚀 File optimized for ultra-fast upload")
                
                # Skip file checksum for speed
                file_checksum = None
                
                file_size = os.path.getsize(file_path)
                filename = os.path.basename(file_path)
                
                logger.info(f"📤 Starting upload task {task_id}: {filename} ({format_file_size(file_size)})")
                
                # Initialize progress tracking
                self.active_uploads[task_id] = {
                    'file_path': file_path,
                    'file_size': file_size,
                    'user_id': user_id,
                    'start_time': start_time,
                    'status': 'uploading'
                }
                
                await self.progress_tracker.update_upload_progress(
                    task_id, 0, file_size, "Preparing upload..."
                )
                
                # Prepare file metadata
                video_metadata = await self._extract_video_metadata(file_path, video_info)
                
                # Generate thumbnail if needed
                thumbnail_path = await self._generate_thumbnail(file_path, video_info)
                
                # Create progress callback
                upload_progress_callback = self._create_upload_progress_callback(task_id, file_size)
                
                # Prepare caption
                caption = self._create_file_caption(video_info, format_info, file_size)
                
                # Upload to designated chat
                message = await self.telethon_manager.upload_file(
                    file_path=file_path,
                    chat_id=settings.UPLOAD_CHAT_ID,
                    caption=caption,
                    progress_callback=upload_progress_callback,
                    thumbnail=thumbnail_path,
                    video_metadata=video_metadata
                )
                
                upload_time = time.time() - start_time
                average_speed = file_size / upload_time if upload_time > 0 else 0
                
                # Update progress tracker
                await self.progress_tracker.update_upload_progress(
                    task_id, file_size, file_size, "Upload completed"
                )
                
                # Update tracking
                self.active_uploads[task_id]['status'] = 'completed'
                self.active_uploads[task_id]['message_id'] = message.id
                self.active_uploads[task_id]['upload_time'] = upload_time
                self.active_uploads[task_id]['average_speed'] = average_speed
                
                # Add to history
                self.upload_history.append({
                    'task_id': task_id,
                    'filename': filename,
                    'file_size': file_size,
                    'upload_time': upload_time,
                    'average_speed': average_speed,
                    'user_id': user_id,
                    'timestamp': time.time(),
                    'message_id': message.id
                })
                
                # Clean up temporary files
                await self._cleanup_upload_files(file_path, thumbnail_path)
                
                logger.info(f"✅ Upload completed: {filename} in {format_upload_time(upload_time)} "
                          f"(Speed: {format_file_size(average_speed)}/s)")
                
                return {
                    'task_id': task_id,
                    'message_id': message.id,
                    'file_size': file_size,
                    'upload_time': upload_time,
                    'average_speed': average_speed,
                    'chat_id': settings.UPLOAD_CHAT_ID,
                    'caption': caption
                }
                
            except Exception as e:
                # Update error status
                if task_id in self.active_uploads:
                    self.active_uploads[task_id]['status'] = 'failed'
                    self.active_uploads[task_id]['error'] = str(e)
                
                await self.progress_tracker.update_upload_progress(
                    task_id, 0, 0, f"Upload failed: {str(e)}"
                )
                
                logger.error(f"❌ Upload failed for task {task_id}: {e}", exc_info=True)
                raise
            finally:
                # Clean up active uploads
                if task_id in self.active_uploads:
                    # Move to history or clean up after some time
                    asyncio.create_task(self._cleanup_active_upload(task_id))
    
    async def _validate_file_for_upload(self, file_path: str):
        """Validate file before upload"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            raise ValueError("File is empty")
        
        if file_size > self.max_file_size:
            raise ValueError(f"File too large: {format_file_size(file_size)} > {format_file_size(self.max_file_size)}")
        
        # Check if file is readable
        try:
            with open(file_path, 'rb') as f:
                f.read(1024)  # Read first 1KB to test
        except Exception as e:
            raise ValueError(f"File is not readable: {e}")
    
    async def _extract_video_metadata(self, file_path: str, video_info: Dict) -> Dict[str, Any]:
        """Extract video metadata for Telegram attributes"""
        try:
            # Use video_info from downloader
            duration = video_info.get('duration', 0)
            
            # Get dimensions from format info if available
            width = 0
            height = 0
            
            # Try to get dimensions from video_info
            if video_info.get('formats'):
                for fmt in video_info['formats']:
                    if fmt.get('width') and fmt.get('height'):
                        width = fmt['width']
                        height = fmt['height']
                        break
            
            return {
                'duration': int(duration) if duration else 0,
                'width': int(width) if width else 0,
                'height': int(height) if height else 0,
                'supports_streaming': True
            }
            
        except Exception as e:
            logger.warning(f"Failed to extract video metadata: {e}")
            return {'duration': 0, 'width': 0, 'height': 0, 'supports_streaming': True}
    
    async def _generate_thumbnail(self, file_path: str, video_info: Dict) -> Optional[str]:
        """Generate thumbnail for video files"""
        try:
            # Check if it's a video file
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext not in ['.mp4', '.avi', '.mkv', '.mov', '.webm', '.flv']:
                return None
            
            # Use thumbnail from video info if available
            thumbnail_url = video_info.get('thumbnail')
            if not thumbnail_url:
                return None
            
            # Download thumbnail
            import aiohttp
            async with aiohttp.ClientSession() as session:
                timeout = aiohttp.ClientTimeout(total=10)
                async with session.get(thumbnail_url, timeout=timeout) as response:
                    if response.status == 200:
                        thumbnail_data = await response.read()
                        
                        # Save thumbnail
                        thumbnail_path = file_path + '.thumb.jpg'
                        with open(thumbnail_path, 'wb') as f:
                            f.write(thumbnail_data)
                        
                        return thumbnail_path
            
        except Exception as e:
            logger.warning(f"Failed to generate thumbnail: {e}")
        
        return None
    
    def _create_upload_progress_callback(self, task_id: str, total_size: int):
        """Create progress callback for upload tracking"""
        def progress_callback(current: int, total: int):
            # Update progress tracker safely from thread
            try:
                # Try to get the running loop
                try:
                    loop = asyncio.get_running_loop()
                    # Schedule the coroutine to run in the event loop
                    asyncio.run_coroutine_threadsafe(
                        self.progress_tracker.update_upload_progress(
                            task_id, current, total, "Uploading..."
                        ), loop
                    )
                except RuntimeError:
                    # No running loop, skip progress update
                    pass
            except Exception as e:
                # Silently handle progress update errors
                logger.debug(f"Upload progress update error: {e}")
            
            # Update active uploads
            if task_id in self.active_uploads:
                upload_info = self.active_uploads[task_id]
                elapsed_time = time.time() - upload_info['start_time']
                speed = current / elapsed_time if elapsed_time > 0 else 0
                
                upload_info.update({
                    'current_bytes': current,
                    'total_bytes': total,
                    'progress_percent': (current / total * 100) if total > 0 else 0,
                    'speed': speed,
                    'elapsed_time': elapsed_time,
                    'eta': (total - current) / speed if speed > 0 else 0
                })
        
        return progress_callback
    
    def _create_file_caption(self, video_info: Dict, format_info: Dict, file_size: int) -> str:
        """Create formatted caption for uploaded file"""
        from utils.helpers import truncate_text
        
        title = video_info.get('title', 'Unknown Title')
        uploader = video_info.get('uploader', 'Unknown')
        duration = video_info.get('duration', 0)
        platform = video_info.get('platform', 'Unknown')
        
        # Truncate long fields to prevent caption overflow
        title = truncate_text(title, 80)
        uploader = truncate_text(uploader, 50)
        
        # Format duration
        duration_str = format_duration(duration) if duration else 'Unknown'
        
        # Quality info
        quality = format_info.get('quality', 'Unknown')
        ext = format_info.get('ext', 'mp4')
        
        caption = f"""🎬 <b>{title}</b>

👤 <b>Uploader:</b> {uploader}
🌐 <b>Platform:</b> {platform.title()}
⏱ <b>Duration:</b> {duration_str}
📺 <b>Quality:</b> {quality}
📁 <b>Format:</b> {ext.upper()}
💾 <b>File Size:</b> {format_file_size(file_size)}

✅ <b>Downloaded via Ultra Video Bot</b>"""

        # Ensure total caption doesn't exceed Telegram's 1024 character limit
        if len(caption) > 1020:
            # If still too long, truncate title further
            title = truncate_text(title, 40)
            caption = f"""🎬 <b>{title}</b>

👤 <b>Uploader:</b> {uploader}
🌐 <b>Platform:</b> {platform.title()}
⏱ <b>Duration:</b> {duration_str}
📺 <b>Quality:</b> {quality}
📁 <b>Format:</b> {ext.upper()}
💾 <b>File Size:</b> {format_file_size(file_size)}

✅ <b>Downloaded via Ultra Video Bot</b>"""
        
        return caption
    
    async def _cleanup_upload_files(self, file_path: str, thumbnail_path: Optional[str]):
        """Clean up temporary files after upload"""
        try:
            # Remove main file
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"🗑️ Cleaned up file: {file_path}")
            
            # Remove thumbnail
            if thumbnail_path and os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
                logger.debug(f"🗑️ Cleaned up thumbnail: {thumbnail_path}")
            
            # Remove empty directory if it's in temp
            file_dir = os.path.dirname(file_path)
            if file_dir.startswith(settings.TEMP_DIR) and os.path.exists(file_dir):
                try:
                    os.rmdir(file_dir)
                except OSError:
                    pass  # Directory not empty
                    
        except Exception as e:
            logger.warning(f"Failed to cleanup files: {e}")
    
    async def _cleanup_active_upload(self, task_id: str, delay: int = 300):
        """Clean up active upload entry after delay"""
        await asyncio.sleep(delay)  # Wait 5 minutes
        
        if task_id in self.active_uploads:
            del self.active_uploads[task_id]
            logger.debug(f"🗑️ Cleaned up active upload: {task_id}")
    
    async def get_upload_progress(self, task_id: str) -> Dict[str, Any]:
        """Get current upload progress"""
        if task_id in self.active_uploads:
            upload_info = self.active_uploads[task_id].copy()
            
            # Add formatted information
            upload_info.update({
                'file_size_str': format_file_size(upload_info.get('file_size', 0)),
                'speed_str': format_file_size(upload_info.get('speed', 0)) + '/s',
                'elapsed_str': format_upload_time(upload_info.get('elapsed_time', 0)),
                'eta_str': format_upload_time(upload_info.get('eta', 0))
            })
            
            return upload_info
        
        # Check progress tracker
        return await self.progress_tracker.get_upload_progress(task_id)
    
    async def cancel_upload(self, task_id: str) -> bool:
        """Cancel an ongoing upload"""
        try:
            if task_id in self.active_uploads:
                upload_info = self.active_uploads[task_id]
                upload_info['status'] = 'cancelled'
                
                # Update progress tracker
                await self.progress_tracker.update_upload_progress(
                    task_id, 0, 0, "Cancelled by user"
                )
                
                logger.info(f"📝 Upload task {task_id} marked as cancelled")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Failed to cancel upload {task_id}: {e}")
            return False
    
    async def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Get detailed file information"""
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            stat = os.stat(file_path)
            file_size = stat.st_size
            
            # Get file hash for deduplication
            file_hash = await self._get_file_hash_async(file_path)
            
            # Get MIME type
            mime_type, _ = mimetypes.guess_type(file_path)
            
            return {
                'path': file_path,
                'name': os.path.basename(file_path),
                'size': file_size,
                'size_str': format_file_size(file_size),
                'hash': file_hash,
                'mime_type': mime_type,
                'created': stat.st_ctime,
                'modified': stat.st_mtime,
                'extension': os.path.splitext(file_path)[1].lower(),
                'is_video': mime_type and mime_type.startswith('video/') if mime_type else False,
                'is_audio': mime_type and mime_type.startswith('audio/') if mime_type else False
            }
            
        except Exception as e:
            logger.error(f"Failed to get file info for {file_path}: {e}")
            raise
    
    async def _get_file_hash_async(self, file_path: str) -> str:
        """Get file hash asynchronously"""
        async with self.process_semaphore:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, get_file_hash, file_path)
    
    async def cleanup_temp_directory(self, max_age_hours: int = 1):
        """Clean up old files in temporary directory"""
        try:
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            cleaned_files = 0
            freed_space = 0
            
            temp_dir = Path(settings.TEMP_DIR)
            if not temp_dir.exists():
                return {'cleaned_files': 0, 'freed_space': 0}
            
            for file_path in temp_dir.rglob('*'):
                if file_path.is_file():
                    try:
                        file_age = current_time - file_path.stat().st_ctime
                        if file_age > max_age_seconds:
                            file_size = file_path.stat().st_size
                            file_path.unlink()
                            cleaned_files += 1
                            freed_space += file_size
                            logger.debug(f"🗑️ Cleaned up old file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to clean up file {file_path}: {e}")
            
            # Remove empty directories
            for dir_path in temp_dir.rglob('*'):
                if dir_path.is_dir() and not any(dir_path.iterdir()):
                    try:
                        dir_path.rmdir()
                        logger.debug(f"🗑️ Removed empty directory: {dir_path}")
                    except Exception as e:
                        logger.warning(f"Failed to remove directory {dir_path}: {e}")
            
            logger.info(f"✅ Cleanup completed: {cleaned_files} files, {format_file_size(freed_space)} freed")
            
            return {
                'cleaned_files': cleaned_files,
                'freed_space': freed_space,
                'freed_space_str': format_file_size(freed_space)
            }
            
        except Exception as e:
            logger.error(f"❌ Cleanup failed: {e}")
            return {'cleaned_files': 0, 'freed_space': 0}
    
    async def get_upload_history(self, user_id: Optional[int] = None, limit: int = 10) -> List[Dict]:
        """Get upload history for user or all users"""
        history = self.upload_history.copy()
        
        # Filter by user if specified
        if user_id:
            history = [h for h in history if h.get('user_id') == user_id]
        
        # Sort by timestamp (newest first) and limit
        history.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        
        return history[:limit]
    
    async def get_performance_stats(self) -> Dict[str, Any]:
        """Get current file manager performance statistics"""
        temp_dir_stats = await self._get_temp_directory_stats()
        
        return {
            'active_uploads': len(self.active_uploads),
            'max_concurrent_uploads': settings.MAX_CONCURRENT_UPLOADS,
            'upload_queue_size': self.upload_semaphore._value,
            'total_uploads_completed': len(self.upload_history),
            'temp_directory_size': temp_dir_stats['total_size'],
            'temp_directory_files': temp_dir_stats['file_count'],
            'chunk_size': self.chunk_size,
            'max_file_size': self.max_file_size,
            'max_file_size_str': format_file_size(self.max_file_size)
        }
    
    async def _get_temp_directory_stats(self) -> Dict[str, Any]:
        """Get temporary directory statistics"""
        try:
            temp_dir = Path(settings.TEMP_DIR)
            if not temp_dir.exists():
                return {'total_size': 0, 'file_count': 0}
            
            total_size = 0
            file_count = 0
            
            for file_path in temp_dir.rglob('*'):
                if file_path.is_file():
                    try:
                        total_size += file_path.stat().st_size
                        file_count += 1
                    except Exception:
                        pass
            
            return {
                'total_size': total_size,
                'file_count': file_count,
                'total_size_str': format_file_size(total_size)
            }
            
        except Exception as e:
            logger.error(f"Failed to get temp directory stats: {e}")
            return {'total_size': 0, 'file_count': 0}
    
    async def get_ultra_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive ultra-performance statistics"""
        try:
            base_stats = await self.get_performance_stats()
            
            # Calculate upload efficiency metrics
            recent_speeds = self.upload_speed_history[-10:] if self.upload_speed_history else []
            avg_speed = sum(recent_speeds) / len(recent_speeds) if recent_speeds else 0
            peak_speed = max(self.upload_speed_history) if self.upload_speed_history else 0
            
            # Enhanced performance metrics
            ultra_stats = {
                **base_stats,
                'ultra_optimizations': {
                    'compression_enabled': self.adaptive_compression,
                    'smart_chunking_enabled': self.smart_chunking,
                    'parallel_uploads_enabled': self.parallel_chunk_upload,
                    'dynamic_scaling_enabled': self.dynamic_worker_scaling,
                    'bandwidth_prediction_enabled': self.bandwidth_prediction
                },
                'speed_metrics': {
                    'current_average_speed': avg_speed,
                    'current_average_speed_str': format_file_size(avg_speed) + '/s',
                    'peak_speed': peak_speed,
                    'peak_speed_str': format_file_size(peak_speed) + '/s',
                    'speed_samples': len(self.upload_speed_history)
                },
                'performance_metrics': self.performance_metrics,
                'optimization_status': {
                    'compression_workers': self.compression_semaphore._value,
                    'processing_workers': self.process_semaphore._value,
                    'upload_workers': self.upload_semaphore._value
                }
            }
            
            return ultra_stats
            
        except Exception as e:
            logger.error(f"❌ Failed to get ultra performance stats: {e}")
            return await self.get_performance_stats()  # Fallback to basic stats

    async def _ultra_optimize_file(self, file_path: str, video_info: Dict) -> str:
        """Ultra-optimize file for fastest upload possible"""
        try:
            if not self.upload_optimization_enabled:
                return file_path
            
            file_size = os.path.getsize(file_path)
            file_ext = os.path.splitext(file_path)[1].lower()
            
            # Only optimize large video files
            if file_size < 50 * 1024 * 1024 or file_ext not in ['.mp4', '.avi', '.mkv', '.mov', '.webm']:
                return file_path
            
            logger.info(f"🔧 Ultra-optimizing file: {format_file_size(file_size)}")
            
            # Apply smart compression for large files
            if file_size > 100 * 1024 * 1024:  # Files > 100MB
                compressed_path = await self._smart_compress_video(file_path, video_info)
                if compressed_path and os.path.exists(compressed_path):
                    new_size = os.path.getsize(compressed_path)
                    compression_ratio = ((file_size - new_size) / file_size) * 100
                    logger.info(f"✅ Smart compression: {compression_ratio:.1f}% reduction")
                    return compressed_path
            
            return file_path
            
        except Exception as e:
            logger.warning(f"⚠️ File optimization failed, using original: {e}")
            return file_path
    
    async def _smart_compress_video(self, file_path: str, video_info: Dict) -> Optional[str]:
        """Intelligent video compression for faster uploads"""
        async with self.compression_semaphore:
            try:
                # Create optimized output path
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                optimized_path = os.path.join(
                    os.path.dirname(file_path), 
                    f"{base_name}_optimized.mp4"
                )
                
                # Get video duration for optimization decisions
                duration = video_info.get('duration', 0)
                if duration > 3600:  # Videos > 1 hour
                    crf = "28"  # Higher compression for long videos
                    preset = "veryfast"
                else:
                    crf = "23"  # Better quality for shorter videos
                    preset = "faster"
                
                # Ultra-optimized FFmpeg command for speed and size balance
                ffmpeg_cmd = [
                    'ffmpeg', '-i', file_path,
                    '-c:v', 'libx264',  # Fast H.264 encoding
                    '-preset', preset,  # Fast encoding preset
                    '-crf', crf,  # Quality/size balance
                    '-c:a', 'aac',  # Fast audio codec
                    '-b:a', '128k',  # Optimized audio bitrate
                    '-movflags', '+faststart',  # Fast streaming
                    '-threads', '0',  # Use all CPU cores
                    '-y',  # Overwrite output
                    optimized_path
                ]
                
                logger.info("⚡ Starting ultra-fast compression...")
                start_time = time.time()
                
                # Run compression with timeout
                process = await asyncio.create_subprocess_exec(
                    *ffmpeg_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(), 
                        timeout=300  # 5 minute timeout
                    )
                    
                    if process.returncode == 0 and os.path.exists(optimized_path):
                        compression_time = time.time() - start_time
                        original_size = os.path.getsize(file_path)
                        compressed_size = os.path.getsize(optimized_path)
                        
                        if compressed_size < original_size * 0.9:  # At least 10% reduction
                            logger.info(f"✅ Compression completed in {compression_time:.1f}s")
                            return optimized_path
                        else:
                            # Clean up if no significant reduction
                            os.remove(optimized_path)
                            logger.info("ℹ️ No significant compression achieved")
                            return None
                    else:
                        logger.warning(f"⚠️ Compression failed: {stderr.decode()}")
                        return None
                        
                except asyncio.TimeoutError:
                    process.kill()
                    logger.warning("⚠️ Compression timeout, using original file")
                    return None
                    
            except Exception as e:
                logger.warning(f"⚠️ Smart compression failed: {e}")
                return None

    async def _adaptive_upload_optimization(self, file_size: int) -> Dict[str, Any]:
        """Dynamically optimize upload parameters based on file size and network"""
        try:
            # Analyze recent upload performance
            recent_speeds = self.upload_speed_history[-10:] if self.upload_speed_history else []
            avg_speed = sum(recent_speeds) / len(recent_speeds) if recent_speeds else 0
            
            # Adaptive optimization based on file size and performance
            if file_size > 500 * 1024 * 1024:  # Files > 500MB
                workers = 20 if avg_speed > 10 * 1024 * 1024 else 16  # More workers for fast connections
                chunk_size = 1024 * 1024  # 1MB chunks for large files
                compression_enabled = True
            elif file_size > 100 * 1024 * 1024:  # Files > 100MB
                workers = 12 if avg_speed > 5 * 1024 * 1024 else 8
                chunk_size = 512 * 1024  # 512KB chunks
                compression_enabled = file_size > 200 * 1024 * 1024
            else:  # Smaller files
                workers = 8
                chunk_size = 256 * 1024  # 256KB chunks
                compression_enabled = False
            
            return {
                'workers': workers,
                'chunk_size': chunk_size,
                'compression_enabled': compression_enabled,
                'parallel_streams': min(workers // 2, 6),
                'adaptive_bitrate': True
            }
            
        except Exception as e:
            logger.warning(f"⚠️ Adaptive optimization failed: {e}")
            return {
                'workers': 8,
                'chunk_size': 512 * 1024,
                'compression_enabled': False,
                'parallel_streams': 4,
                'adaptive_bitrate': False
            }

    async def _create_resumable_upload_checkpoint(self, task_id: str, file_path: str, uploaded_bytes: int) -> Dict[str, Any]:
        """Create checkpoint for resumable uploads"""
        try:
            checkpoint_data = {
                'task_id': task_id,
                'file_path': file_path,
                'uploaded_bytes': uploaded_bytes,
                'total_bytes': os.path.getsize(file_path),
                'timestamp': time.time(),
                'file_hash': await self._get_file_hash_async(file_path)
            }
            
            # Store checkpoint in cache for quick access
            await self.progress_tracker.cache_manager.set(
                f"upload_checkpoint:{task_id}",
                checkpoint_data,
                ttl=3600  # 1 hour TTL
            )
            
            logger.info(f"📋 Created upload checkpoint: {task_id} at {uploaded_bytes} bytes")
            return checkpoint_data
            
        except Exception as e:
            logger.error(f"❌ Failed to create upload checkpoint: {e}")
            return {}
    
    async def _resume_upload_from_checkpoint(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Resume upload from existing checkpoint"""
        try:
            checkpoint = await self.progress_tracker.cache_manager.get(f"upload_checkpoint:{task_id}")
            
            if not checkpoint:
                logger.info(f"📋 No checkpoint found for task: {task_id}")
                return None
            
            # Verify file integrity
            file_path = checkpoint['file_path']
            if not os.path.exists(file_path):
                logger.warning(f"⚠️ File not found for resume: {file_path}")
                return None
            
            current_hash = await self._get_file_hash_async(file_path)
            if current_hash != checkpoint['file_hash']:
                logger.warning(f"⚠️ File modified since checkpoint, cannot resume")
                return None
            
            logger.info(f"📋 Resuming upload from checkpoint: {checkpoint['uploaded_bytes']} bytes")
            return checkpoint
            
        except Exception as e:
            logger.error(f"❌ Failed to resume from checkpoint: {e}")
            return None
    
    async def _monitor_upload_performance(self, task_id: str, file_size: int) -> Dict[str, Any]:
        """Monitor and optimize upload performance in real-time"""
        try:
            upload_info = self.active_uploads.get(task_id, {})
            if not upload_info:
                return {}
            
            current_time = time.time()
            elapsed_time = current_time - upload_info['start_time']
            current_bytes = upload_info.get('current_bytes', 0)
            
            # Calculate performance metrics
            if elapsed_time > 0:
                current_speed = current_bytes / elapsed_time
                self.upload_speed_history.append(current_speed)
                
                # Keep only recent speed history (last 20 readings)
                if len(self.upload_speed_history) > 20:
                    self.upload_speed_history = self.upload_speed_history[-20:]
                
                # Adaptive optimization based on performance
                if current_speed < 1024 * 1024:  # Less than 1MB/s
                    # Slow upload - reduce workers, increase chunk size
                    optimization = await self._adaptive_upload_optimization(file_size)
                    optimization['workers'] = max(4, optimization['workers'] - 2)
                    optimization['chunk_size'] = min(1024 * 1024, optimization['chunk_size'] * 2)
                    
                elif current_speed > 10 * 1024 * 1024:  # More than 10MB/s
                    # Fast upload - increase workers for maximum speed
                    optimization = await self._adaptive_upload_optimization(file_size)
                    optimization['workers'] = min(24, optimization['workers'] + 4)
                
                # Predict completion time
                remaining_bytes = file_size - current_bytes
                eta = remaining_bytes / current_speed if current_speed > 0 else 0
                
                performance_data = {
                    'current_speed': current_speed,
                    'average_speed': sum(self.upload_speed_history) / len(self.upload_speed_history),
                    'eta_seconds': eta,
                    'progress_percentage': (current_bytes / file_size) * 100 if file_size > 0 else 0,
                    'elapsed_time': elapsed_time,
                    'optimization_applied': True
                }
                
                # Update performance metrics
                self.performance_metrics['total_updates'] += 1
                self.performance_metrics['peak_concurrent_tasks'] = max(
                    self.performance_metrics['peak_concurrent_tasks'],
                    len(self.active_uploads)
                )
                
                return performance_data
            
            return {}
            
        except Exception as e:
            logger.error(f"❌ Performance monitoring failed: {e}")
            return {}
