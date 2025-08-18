from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from .auth import router as auth_router, get_current_user


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

	# Include auth routes
	app.include_router(auth_router)

	@app.get("/health")
	async def health() -> dict:
		return {"status": "ok"}

	@app.get("/dashboard")
	async def dashboard(user: str = Depends(get_current_user)) -> dict:
		return {"status": "ok", "user": user}

	return app

