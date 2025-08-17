import os
import sys
import shlex
import time
import math
import asyncio
import logging
import subprocess
import json
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Optional, Tuple

from telethon import TelegramClient, events
from telethon.tl.types import DocumentAttributeVideo
from dotenv import load_dotenv

# Optional import guard for yt_dlp to provide a clear error if missing
try:
	import yt_dlp
except Exception as e:  # pragma: no cover
	print("[FATAL] yt-dlp is not installed. Run: pip install yt-dlp", file=sys.stderr)
	raise


logging.basicConfig(
	level=logging.INFO,
	format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("yt_telethon_userbot")


@dataclass
class Config:
	api_id: int
	api_hash: str
	session_name: str = "userbot"
	download_dir: Path = Path("downloads")
	max_file_size_gb: float = 2.0

	@property
	def max_file_size_bytes(self) -> int:
		# Interpret as GiB
		return int(self.max_file_size_gb * 1024 * 1024 * 1024)


def load_config_from_env() -> Config:
	load_dotenv(override=False)
	api_id_str = os.getenv("API_ID", "").strip()
	api_hash = os.getenv("API_HASH", "").strip()
	session_name = os.getenv("SESSION_NAME", "userbot").strip() or "userbot"
	download_dir = Path(os.getenv("DOWNLOAD_DIR", "downloads").strip() or "downloads")
	max_file_size_gb = float(os.getenv("MAX_FILE_SIZE_GB", "2").strip() or 2)

	if not api_id_str.isdigit():
		raise RuntimeError("API_ID is missing or invalid in environment.")
	if not api_hash:
		raise RuntimeError("API_HASH is missing in environment.")

	cfg = Config(
		api_id=int(api_id_str),
		api_hash=api_hash,
		session_name=session_name,
		download_dir=download_dir,
		max_file_size_gb=max_file_size_gb,
	)
	cfg.download_dir.mkdir(parents=True, exist_ok=True)
	return cfg


def human_size(num_bytes: Optional[int]) -> str:
	if num_bytes is None:
		return "?"
	units = ["B", "KB", "MB", "GB", "TB"]
	size = float(num_bytes)
	for unit in units:
		if size < 1024.0 or unit == units[-1]:
			return f"{size:.2f} {unit}"
		size /= 1024.0
	return f"{size:.2f} TB"


def format_duration(seconds: Optional[int]) -> str:
	if seconds is None:
		return "?"
	return str(timedelta(seconds=int(seconds)))


def pick_format_for_resolution(target_res: int) -> str:
	# Robust selector: prefer separate best video/audio up to target height, fallback to best single stream.
	# Merging is forced to mp4 via options.
	return (
		f"bestvideo[height<={target_res}]+bestaudio/"
		f"best[height<={target_res}]"
	)


def probe_video_stream_info(file_path: Path) -> Tuple[Optional[int], Optional[int], Optional[int]]:
	"""Return (width, height, duration_seconds) using ffprobe if available."""
	try:
		cmd = [
			"ffprobe", "-v", "error",
			"-select_streams", "v:0",
			"-show_entries", "stream=width,height:format=duration",
			"-of", "json", str(file_path),
		]
		res = subprocess.run(
			cmd,
			stdout=subprocess.PIPE,
			stderr=subprocess.DEVNULL,
			text=True,
			check=True,
		)
		data = json.loads(res.stdout or "{}")
		width: Optional[int] = None
		height: Optional[int] = None
		duration_seconds: Optional[int] = None
		streams = data.get("streams") or []
		if streams:
			s0 = streams[0]
			w = s0.get("width")
			h = s0.get("height")
			if isinstance(w, int) and w > 0:
				width = w
			if isinstance(h, int) and h > 0:
				height = h
		fmt = data.get("format") or {}
		if "duration" in fmt:
			try:
				duration_seconds = int(float(fmt["duration"]))
			except Exception:
				pass
		return width, height, duration_seconds
	except Exception:
		return None, None, None


async def run_yt_dlp_download(
	url: str,
	download_dir: Path,
	resolution: int,
	status_updater,
) -> Tuple[Path, dict]:
	"""Download a single video using yt-dlp in a thread; return final file path and info dict."""

	loop = asyncio.get_running_loop()
	last_update_ts = 0.0

	async def edit_status(text: str) -> None:
		try:
			await status_updater(text)
		except Exception:
			logger.debug("Failed to edit status message", exc_info=True)

	def progress_hook(d):
		nonlocal last_update_ts
		if d.get("status") == "downloading":
			now = time.time()
			if now - last_update_ts < 1.5:
				return
			last_update_ts = now
			downloaded = d.get("downloaded_bytes") or 0
			total = d.get("total_bytes") or d.get("total_bytes_estimate")
			pct = 0
			if total:
				pct = downloaded * 100.0 / max(total, 1)
			speed = d.get("speed")
			eta = d.get("eta")
			msg = (
				f"⏬ جاري التنزيل من يوتيوب\n"
				f"المكتمل: {human_size(downloaded)} / {human_size(total)} ({pct:.1f}%)\n"
				f"السرعة: {human_size(int(speed))}/s\n" if speed else f"" 
			)
			if eta is not None:
				msg += f"الوقت المتبقي: {format_duration(eta)}\n"
			# run thread-safe edit on the loop
			asyncio.run_coroutine_threadsafe(edit_status(msg), loop)

	# Prepare yt-dlp options
	ydl_opts = {
		"outtmpl": str(download_dir / "%(title).200B [%(id)s].%(ext)s"),
		"noplaylist": True,
		"quiet": True,
		"no_warnings": True,
		"merge_output_format": "mp4",
		"progress_hooks": [progress_hook],
		"concurrent_fragment_downloads": 5,
		"retries": 5,
		"fragment_retries": 10,
		"trim_file_name": 200,
		"ignoreerrors": False,
	}

	format_selector = pick_format_for_resolution(resolution)
	ydl_opts["format"] = format_selector

	def blocking_download():
		with yt_dlp.YoutubeDL(ydl_opts) as ydl:
			info = ydl.extract_info(url, download=True)
			if info is None:
				raise RuntimeError("لم أستطع جلب معلومات الفيديو.")
			# Find the final file path using the video id
			vid = info.get("id")
			final_path: Optional[Path] = None
			candidates = list(download_dir.glob(f"*[{vid}].*") ) if vid else []
			# Prefer mp4
			for p in candidates:
				if p.suffix.lower() == ".mp4":
					final_path = p
					break
			if final_path is None and candidates:
				# fallback to first
				final_path = candidates[0]
			if not final_path or not final_path.exists():
				# As a last resort, use prepare_filename
				prepared = Path(ydl.prepare_filename(info))
				if prepared.exists():
					final_path = prepared
				else:
					raise FileNotFoundError("تعذر تحديد مسار الملف النهائي بعد التنزيل.")
			return final_path, info

	path, info = await asyncio.to_thread(blocking_download)
	return path, info


async def send_with_progress(client: TelegramClient, chat_id: int, file_path: Path, caption: str, duration: Optional[int]) -> None:
	status_msg = await client.send_message(chat_id, "⏫ جاري الرفع إلى تيليجرام...")

	last_ts = 0.0

	def progress(current: int, total: int):
		nonlocal last_ts
		now = time.time()
		if now - last_ts < 1.0:
			return
		last_ts = now
		pct = current * 100.0 / max(total, 1)
		msg = (
			f"⏫ جاري الرفع إلى تيليجرام\n"
			f"المكتمل: {human_size(current)} / {human_size(total)} ({pct:.1f}%)"
		)
		try:
			asyncio.create_task(status_msg.edit(msg))
		except Exception:
			pass

	w, h, probed_dur = probe_video_stream_info(file_path)
	if not duration and probed_dur:
		duration = probed_dur

	video_attr = DocumentAttributeVideo(
		duration=int(duration) if duration else 0,
		w=int(w) if w else 0,
		h=int(h) if h else 0,
		supports_streaming=True,
	)

	await client.send_file(
		chat_id,
		str(file_path),
		caption=caption,
		attributes=[video_attr],
		force_document=False,
		progress_callback=progress,
	)
	try:
		await status_msg.delete()
	except Exception:
		pass


def parse_command_args(arg_line: str) -> Tuple[Optional[str], int]:
	"""Parse `.yt <url> [--res N]` and return (url, resolution)."""
	url: Optional[str] = None
	resolution = 720
	try:
		tokens = shlex.split(arg_line)
	except ValueError:
		tokens = arg_line.split()
	for i, tok in enumerate(tokens):
		if tok.startswith("--res="):
			try:
				resolution = int(tok.split("=", 1)[1])
			except Exception:
				pass
		elif tok == "--res" and i + 1 < len(tokens):
			try:
				resolution = int(tokens[i + 1])
			except Exception:
				pass
		elif not tok.startswith("--") and url is None:
			url = tok
	return url, resolution


async def main() -> None:
	cfg = load_config_from_env()
	client = TelegramClient(cfg.session_name, cfg.api_id, cfg.api_hash)
	semaphore = asyncio.Semaphore(1)  # limit to one job at a time to reduce resource usage

	@client.on(events.NewMessage(outgoing=True, pattern=r"^\.yt\s+(.+)$"))
	async def handler(event: events.NewMessage.Event):
		# Parse arguments
		arg_line = event.pattern_match.group(1)
		url, resolution = parse_command_args(arg_line)
		if not url:
			await event.reply("❌ يرجى تزويد رابط صحيح. مثال: .yt https://youtu.be/xxxx --res 480")
			return

		async with semaphore:
			status_msg = await event.reply("🔎 جارِ التحضير...")

			try:
				await status_msg.edit("⏬ بدأ التنزيل...")

				async def updater(text: str):
					await status_msg.edit(text)

				file_path, info = await run_yt_dlp_download(
					url=url,
					download_dir=cfg.download_dir,
					resolution=resolution,
					status_updater=updater,
				)

				# Size check
				size_bytes = file_path.stat().st_size
				if size_bytes > cfg.max_file_size_bytes:
					try:
						await status_msg.edit(
							f"⚠️ الحجم النهائي {human_size(size_bytes)} يتجاوز الحد {cfg.max_file_size_gb}GB.\n"
							f"جرّب دقّة أقل عبر: .yt {url} --res 480"
						)
					finally:
						try:
							file_path.unlink(missing_ok=True)
						except Exception:
							pass
					return

				# Compose caption
				title = info.get("title") or ""
				duration = info.get("duration")
				source_url = info.get("webpage_url") or url
				caption = f"{title}\n\nالمصدر: {source_url}"
				if len(caption) > 1024:
					caption = caption[:1000] + "...\n" + source_url

				await send_with_progress(client, event.chat_id, file_path, caption, duration)

				try:
					await status_msg.edit("✅ تم الرفع، جاري حذف الملف المحلي...")
				except Exception:
					pass
				try:
					file_path.unlink(missing_ok=True)
				except Exception:
					logger.warning("Failed to remove file %s", file_path)
				try:
					await status_msg.delete()
				except Exception:
					pass

			except yt_dlp.utils.DownloadError as de:
				logger.exception("Download error")
				await status_msg.edit(f"❌ فشل التنزيل: {str(de)[:1000]}")
			except Exception as e:
				logger.exception("Unhandled error")
				await status_msg.edit(f"❌ حدث خطأ غير متوقع: {str(e)[:1000]}")

	await client.start()
	logger.info("Userbot started. Send .yt <url> in any chat from your account.")
	await client.run_until_disconnected()


if __name__ == "__main__":
	try:
		asyncio.run(main())
	except KeyboardInterrupt:
		print("Exiting...")