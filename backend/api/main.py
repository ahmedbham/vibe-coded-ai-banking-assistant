"""Banking Assistant API entry point."""

from fastapi import FastAPI

app = FastAPI(
    title="Banking Assistant API",
    description="Multi-agent banking assistant backend API",
    version="0.1.0",
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health-check endpoint."""
    return {"status": "ok"}
