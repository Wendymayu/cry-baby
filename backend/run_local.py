"""Start the local API after loading backend/.env."""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"), override=True)

import uvicorn


if __name__ == "__main__":
    uvicorn.run("fastapi_app.main:app", host="127.0.0.1", port=8000)
