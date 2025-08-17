"""
Upload Manager - مدير الرفع البسيط (placeholder)
"""

import logging
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)


class UploadManager:
	"""مدير رفع بسيط لتلبية الواردات. يمكن استبداله لاحقاً بتنفيذ كامل."""

	def __init__(self) -> None:
		pass

	async def upload_file(self, file_path: Path, chat_id: int, caption: Optional[str] = None) -> bool:
		logger.info("Uploading placeholder: %s -> %s", file_path, chat_id)
		return True

