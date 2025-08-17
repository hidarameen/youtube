"""
Progress Tracker - مراقب التقدم المتطور
"""

import time
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class ProgressInfo:
    """معلومات التقدم"""
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed: float = 0.0
    eta: int = 0
    progress_percent: float = 0.0
    status: str = "pending"
    last_update: float = 0.0


class ProgressTracker:
    """مراقب التقدم المتطور"""
    
    def __init__(self):
        self.progress_data: Dict[str, ProgressInfo] = {}
        self.lock = Lock()
        self.last_cleanup = time.time()
    
    def update_progress(self, d: Dict[str, Any]):
        """تحديث التقدم"""
        try:
            with self.lock:
                # الحصول على معرف التحميل
                download_id = self._extract_download_id(d)
                if not download_id:
                    return
                
                # إنشاء أو تحديث معلومات التقدم
                if download_id not in self.progress_data:
                    self.progress_data[download_id] = ProgressInfo()
                
                progress = self.progress_data[download_id]
                
                # تحديث البيانات
                if d.get('status') == 'downloading':
                    progress.status = 'downloading'
                    progress.downloaded_bytes = d.get('downloaded_bytes', 0)
                    progress.total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    progress.speed = d.get('speed', 0.0)
                    progress.eta = d.get('eta', 0)
                    
                    # حساب النسبة المئوية
                    if progress.total_bytes > 0:
                        progress.progress_percent = (progress.downloaded_bytes / progress.total_bytes) * 100
                    else:
                        progress.progress_percent = 0.0
                
                elif d.get('status') == 'finished':
                    progress.status = 'finished'
                    progress.progress_percent = 100.0
                
                elif d.get('status') == 'error':
                    progress.status = 'error'
                
                progress.last_update = time.time()
                
                # تنظيف البيانات القديمة
                self._cleanup_old_data()
                
        except Exception as e:
            logger.error(f"❌ خطأ في تحديث التقدم: {e}")
    
    def _extract_download_id(self, d: Dict[str, Any]) -> Optional[str]:
        """استخراج معرف التحميل من البيانات"""
        try:
            # محاولة استخراج من filename
            filename = d.get('filename', '')
            if filename:
                # البحث عن معرف في اسم الملف
                import re
                match = re.search(r'\[([a-zA-Z0-9_-]+)\]', filename)
                if match:
                    return match.group(1)
            
            # محاولة استخراج من info
            info = d.get('info', {})
            if info:
                return info.get('id')
            
            return None
            
        except Exception as e:
            logger.error(f"❌ خطأ في استخراج معرف التحميل: {e}")
            return None
    
    def get_progress(self, download_id: Optional[str] = None) -> Dict[str, Any]:
        """الحصول على التقدم"""
        try:
            with self.lock:
                if download_id:
                    # الحصول على تقدم محدد
                    if download_id in self.progress_data:
                        progress = self.progress_data[download_id]
                        return {
                            'download_id': download_id,
                            'progress_percent': progress.progress_percent,
                            'downloaded_bytes': progress.downloaded_bytes,
                            'total_bytes': progress.total_bytes,
                            'speed': progress.speed,
                            'eta': progress.eta,
                            'status': progress.status,
                            'last_update': progress.last_update
                        }
                    return {}
                else:
                    # الحصول على جميع التقدم
                    return {
                        download_id: {
                            'progress_percent': progress.progress_percent,
                            'downloaded_bytes': progress.downloaded_bytes,
                            'total_bytes': progress.total_bytes,
                            'speed': progress.speed,
                            'eta': progress.eta,
                            'status': progress.status,
                            'last_update': progress.last_update
                        }
                        for download_id, progress in self.progress_data.items()
                    }
                    
        except Exception as e:
            logger.error(f"❌ خطأ في الحصول على التقدم: {e}")
            return {}
    
    def remove_progress(self, download_id: str):
        """إزالة التقدم"""
        try:
            with self.lock:
                if download_id in self.progress_data:
                    del self.progress_data[download_id]
                    logger.debug(f"تم إزالة تقدم التحميل: {download_id}")
                    
        except Exception as e:
            logger.error(f"❌ خطأ في إزالة التقدم: {e}")
    
    def _cleanup_old_data(self, max_age: int = 3600):
        """تنظيف البيانات القديمة"""
        try:
            current_time = time.time()
            
            # تنظيف كل ساعة
            if current_time - self.last_cleanup < 3600:
                return
            
            self.last_cleanup = current_time
            
            with self.lock:
                to_remove = []
                
                for download_id, progress in self.progress_data.items():
                    # إزالة البيانات الأقدم من ساعة
                    if current_time - progress.last_update > max_age:
                        to_remove.append(download_id)
                
                for download_id in to_remove:
                    del self.progress_data[download_id]
                
                if to_remove:
                    logger.debug(f"تم تنظيف {len(to_remove)} سجل تقدم قديم")
                    
        except Exception as e:
            logger.error(f"❌ خطأ في تنظيف البيانات: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """الحصول على إحصائيات التقدم"""
        try:
            with self.lock:
                total_downloads = len(self.progress_data)
                active_downloads = sum(1 for p in self.progress_data.values() if p.status == 'downloading')
                completed_downloads = sum(1 for p in self.progress_data.values() if p.status == 'finished')
                failed_downloads = sum(1 for p in self.progress_data.values() if p.status == 'error')
                
                total_bytes = sum(p.total_bytes for p in self.progress_data.values())
                downloaded_bytes = sum(p.downloaded_bytes for p in self.progress_data.values())
                
                avg_speed = 0.0
                if active_downloads > 0:
                    speeds = [p.speed for p in self.progress_data.values() if p.status == 'downloading' and p.speed > 0]
                    if speeds:
                        avg_speed = sum(speeds) / len(speeds)
                
                return {
                    'total_downloads': total_downloads,
                    'active_downloads': active_downloads,
                    'completed_downloads': completed_downloads,
                    'failed_downloads': failed_downloads,
                    'total_bytes': total_bytes,
                    'downloaded_bytes': downloaded_bytes,
                    'avg_speed': avg_speed,
                    'progress_percent': (downloaded_bytes / total_bytes * 100) if total_bytes > 0 else 0.0
                }
                
        except Exception as e:
            logger.error(f"❌ خطأ في الحصول على الإحصائيات: {e}")
            return {}
    
    def reset(self):
        """إعادة تعيين مراقب التقدم"""
        try:
            with self.lock:
                self.progress_data.clear()
                self.last_cleanup = time.time()
                logger.info("تم إعادة تعيين مراقب التقدم")
                
        except Exception as e:
            logger.error(f"❌ خطأ في إعادة تعيين مراقب التقدم: {e}")


# إنشاء نسخة عامة من مراقب التقدم
progress_tracker = ProgressTracker()