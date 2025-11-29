# main.py
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from bot import get_reply
import os
import logging

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL)

app = FastAPI(title="Medical Voice Chatbot (Concise Mode)")
app.mount("/static", StaticFiles(directory="static"), name="static")

class ChatRequest(BaseModel):
    message: str

@app.get("/", response_class=HTMLResponse)
async def index():
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return HTMLResponse("<h1>index.html not found</h1>", status_code=404)

@app.post("/chat")
async def chat(req: ChatRequest):
    msg = (req.message or "").strip()
    if not msg:
        return JSONResponse({"error": "empty message"}, status_code=400)
    res = get_reply(msg)
    # return only friendly fields
    return {"reply": res["reply"], "emergency": res["emergency"]}
