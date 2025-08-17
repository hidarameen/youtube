"""
File Utils - أدوات الملفات
"""

import os
import shutil
import hashlib
import mimetypes
from pathlib import Path
from typing import Optional, List, Dict, Any
import aiofiles
import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class FileUtils:
    """أدوات الملفات المتطورة"""
    
    @staticmethod
    def get_file_info(file_path: Path) -> Dict[str, Any]:
        """الحصول على معلومات الملف"""
        try:
            stat = file_path.stat()
            mime_type, _ = mimetypes.guess_type(str(file_path))
            
            return {
                "name": file_path.name,
                "size": stat.st_size,
                "size_human": FileUtils.human_size(stat.st_size),
                "mime_type": mime_type or "application/octet-stream",
                "extension": file_path.suffix,
                "created": stat.st_ctime,
                "modified": stat.st_mtime,
                "is_file": file_path.is_file(),
                "is_dir": file_path.is_dir(),
                "exists": file_path.exists(),
                "md5": FileUtils.calculate_md5(file_path),
                "path": str(file_path.absolute())
            }
        except Exception as e:
            logger.error(f"❌ خطأ في الحصول على معلومات الملف: {e}")
            return {}
    
    @staticmethod
    def human_size(size_bytes: int) -> str:
        """تحويل الحجم إلى صيغة مقروءة"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.2f} {size_names[i]}"
    
    @staticmethod
    def calculate_md5(file_path: Path, chunk_size: int = 8192) -> str:
        """حساب MD5 للملف"""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"❌ خطأ في حساب MD5: {e}")
            return ""
    
    @staticmethod
    async def copy_file_async(src: Path, dst: Path) -> bool:
        """نسخ ملف بشكل غير متزامن"""
        try:
            async with aiofiles.open(src, 'rb') as fsrc:
                async with aiofiles.open(dst, 'wb') as fdst:
                    await fdst.write(await fsrc.read())
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في نسخ الملف: {e}")
            return False
    
    @staticmethod
    async def move_file_async(src: Path, dst: Path) -> bool:
        """نقل ملف بشكل غير متزامن"""
        try:
            # نسخ الملف
            success = await FileUtils.copy_file_async(src, dst)
            if success:
                # حذف الملف الأصلي
                src.unlink()
                return True
            return False
        except Exception as e:
            logger.error(f"❌ خطأ في نقل الملف: {e}")
            return False
    
    @staticmethod
    def safe_filename(filename: str) -> str:
        """إنشاء اسم ملف آمن"""
        import re
        # إزالة الأحرف غير المسموحة
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # إزالة المسافات المتعددة
        filename = re.sub(r'\s+', ' ', filename)
        # تقصير الاسم إذا كان طويلاً
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            filename = name[:200-len(ext)] + ext
        return filename.strip()
    
    @staticmethod
    def get_unique_filename(file_path: Path) -> Path:
        """الحصول على اسم ملف فريد"""
        if not file_path.exists():
            return file_path
        
        counter = 1
        while True:
            new_path = file_path.parent / f"{file_path.stem}_{counter}{file_path.suffix}"
            if not new_path.exists():
                return new_path
            counter += 1
    
    @staticmethod
    async def cleanup_temp_files(temp_dir: Path, max_age_hours: int = 24) -> int:
        """تنظيف الملفات المؤقتة"""
        try:
            import time
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            deleted_count = 0
            
            for file_path in temp_dir.rglob("*"):
                if file_path.is_file():
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > max_age_seconds:
                        try:
                            file_path.unlink()
                            deleted_count += 1
                        except Exception as e:
                            logger.warning(f"فشل في حذف الملف المؤقت: {e}")
            
            logger.info(f"✅ تم حذف {deleted_count} ملف مؤقت")
            return deleted_count
            
        except Exception as e:
            logger.error(f"❌ خطأ في تنظيف الملفات المؤقتة: {e}")
            return 0
    
    @staticmethod
    def split_large_file(file_path: Path, chunk_size: int = 50 * 1024 * 1024) -> List[Path]:
        """تقسيم الملف الكبير إلى أجزاء"""
        try:
            chunks = []
            chunk_number = 1
            
            with open(file_path, 'rb') as f:
                while True:
                    chunk_data = f.read(chunk_size)
                    if not chunk_data:
                        break
                    
                    chunk_path = file_path.parent / f"{file_path.stem}_part{chunk_number:03d}{file_path.suffix}"
                    with open(chunk_path, 'wb') as chunk_file:
                        chunk_file.write(chunk_data)
                    
                    chunks.append(chunk_path)
                    chunk_number += 1
            
            return chunks
            
        except Exception as e:
            logger.error(f"❌ خطأ في تقسيم الملف: {e}")
            return []
    
    @staticmethod
    def merge_file_chunks(chunk_paths: List[Path], output_path: Path) -> bool:
        """دمج أجزاء الملف"""
        try:
            with open(output_path, 'wb') as output_file:
                for chunk_path in chunk_paths:
                    if chunk_path.exists():
                        with open(chunk_path, 'rb') as chunk_file:
                            shutil.copyfileobj(chunk_file, output_file)
            
            # حذف الأجزاء
            for chunk_path in chunk_paths:
                chunk_path.unlink()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ خطأ في دمج أجزاء الملف: {e}")
            return False
    
    @staticmethod
    def get_directory_size(directory: Path) -> int:
        """الحصول على حجم المجلد"""
        try:
            total_size = 0
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
            return total_size
        except Exception as e:
            logger.error(f"❌ خطأ في حساب حجم المجلد: {e}")
            return 0
    
    @staticmethod
    async def create_backup(file_path: Path, backup_dir: Path) -> Optional[Path]:
        """إنشاء نسخة احتياطية"""
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = int(time.time())
            backup_name = f"{file_path.stem}_backup_{timestamp}{file_path.suffix}"
            backup_path = backup_dir / backup_name
            
            success = await FileUtils.copy_file_async(file_path, backup_path)
            if success:
                logger.info(f"✅ تم إنشاء نسخة احتياطية: {backup_path}")
                return backup_path
            return None
            
        except Exception as e:
            logger.error(f"❌ خطأ في إنشاء النسخة الاحتياطية: {e}")
            return None


# إنشاء نسخة عامة
file_utils = FileUtils()