from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_web_app() -> FastAPI:
	app = FastAPI(title="YouTube Telegram Bot API", version="2.0.0")

	# Basic CORS; can be refined via config later
	app.add_middleware(
		CORSMiddleware,
		allow_origins=["*"],
		allow_credentials=True,
		allow_methods=["*"],
		allow_headers=["*"],
	)

	@app.get("/health")
	async def health() -> dict:
		return {"status": "ok"}

	return app

