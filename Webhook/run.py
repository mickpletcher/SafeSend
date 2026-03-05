"""
Entry point - run the SafeSend webhook receiver.

Usage:
    python run.py

Or with uvicorn directly:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""

import uvicorn
from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.LOG_LEVEL,
        reload=False,  # Set True during local development only
    )
