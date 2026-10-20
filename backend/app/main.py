from dotenv import load_dotenv
import logging 
from pathlib import Path

load_dotenv()

LOG_FILE = Path(__file__).resolve().parent.parent / "agent.log"   # backend/agent.log
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(),                       # keeps printing in the terminal
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)



from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.webhooks import router as webhook_router


app = FastAPI(title="PR Review Agent API")

# CORS: only your dashboard (once built) should be allowed to call this API.
# Locked down even in dev so the habit is already correct before deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # your Next.js dashboard, later
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(webhook_router, prefix="/api")


@app.get("/health")
def health():
    """Simple liveness check — hosting platforms and you will both use this."""
    return {"status": "ok"}