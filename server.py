"""
BI Traffic Chatbot — Flask backend (Ollama local models)
Run: python server.py
Default: http://localhost:5000
"""

import json
import os
from pathlib import Path

import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder=".")
CORS(app, origins="*")

OLLAMA_BASE   = os.getenv("OLLAMA_URL",   "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
STATS_FILE     = Path("stats.json")   # written by app.py
HISTORY_FILE   = Path("history.json") # written by app.py

# ── System context injected into every conversation ───────────────────────────
DEFAULT_SYSTEM = """Sen Smart Surveillance BI tizimining yordamchi chatbotiSan.
Loyiha haqida ma'lumot:
- Smart City doirasida mashinalar oqimi va transport zichligini kuzatadi
- YOLOv8 modeli bilan real vaqtda mashinalarni (car) aniqlaydi
- Diagonal counter line orqali mashinalar o'tishlarini hisoblaydi
- OpenCV va Ultralytics kutubxonalari, Python 3.11 ishlatiladi
- Boshqaruv tugmalari: W/S = yuqori/pastga, A/D = chap/o'nga, [/] = qiyalik, R = reset, Q = chiqish
Foydalanuvchi savollariga O'ZBEK TILIDA qisqa va aniq javob ber.
BI (Business Intelligence) tahlilchisi sifatida tahliliy ma'lumotlar berishga harakat qil."""


def ollama_chat(model: str, messages: list) -> str:
    """Call Ollama /api/chat and return the reply text."""
    resp = requests.post(
        f"{OLLAMA_BASE}/api/chat",
        json={"model": model, "messages": messages, "stream": False},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def read_live_stats() -> str:
    """Read stats.json written by app.py and return a human-readable summary."""
    if not STATS_FILE.exists():
        return "(Kamera hozir ishlamayapti — app.py ishga tushirilmagan)"
    try:
        data = json.loads(STATS_FILE.read_text())
        if data.get("stopped"):
            return (
                f"TIZIM TO'XTATILGAN.\n"
                f"Oxirgi hisob: {data.get('crossed', 0)} ta mashina chiziqdan o'tgan."
            )
        return (
            f"REAL VAQT STATISTIKASI (BI Insights):\n"
            f"- Chiziqdan o'tgan mashinalar (jami): {data.get('crossed', 0)} ta\n"
            f"- Hozir kadrda ko'rinayotgan mashinalar: {data.get('in_scene', 0)} ta\n"
            f"- Transport zichligi: {'YUQORI' if data.get('in_scene', 0) > 20 else 'NORMAL'}\n"
            f"- Qayta ishlangan kadrlar: {data.get('frame', 0)}\n"
            f"- So'nggi yangilanish: {data.get('updated_at', 'noma`lum')}"
        )
    except Exception as exc:
        return f"(Statistikani o'qishda xato: {exc})"


@app.route("/history", methods=["GET"])
def get_history():
    """Serve history.json for charts."""
    if not HISTORY_FILE.exists():
        return jsonify([])
    try:
        return jsonify(json.loads(HISTORY_FILE.read_text()))
    except:
        return jsonify([])



# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve chatbot.html at http://localhost:8080 — no file:// CORS issues."""
    return send_from_directory(".", "chatbot.html")


@app.route("/health", methods=["GET"])
def health():
    """Quick health-check — also verifies Ollama is reachable."""
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        return jsonify({"status": "ok", "ollama": "reachable", "models": models})
    except Exception as exc:
        return jsonify({"status": "ok", "ollama": "unreachable", "error": str(exc)}), 200


@app.route("/models", methods=["GET"])
def list_models():
    """Return list of locally available Ollama models."""
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        return jsonify({"models": models})
    except Exception as exc:
        return jsonify({"error": str(exc), "models": []}), 503


@app.route("/chat", methods=["POST"])
def chat():
    """
    Expected JSON body:
      {
        "message":  "...",           # required — current user message
        "history":  [...],           # optional — previous messages [{role, content}]
        "system":   "...",           # optional — override system prompt
        "model":    "llama3.2"       # optional — override model
      }

    Returns:
      {"reply": "..."}
    """
    data = request.get_json(silent=True) or {}

    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "message is required"}), 400

    model   = data.get("model")  or DEFAULT_MODEL
    system  = data.get("system") or DEFAULT_SYSTEM
    history = data.get("history") or []

    # Build Ollama messages array
    # Inject live stats into the system prompt automatically
    live = read_live_stats()
    enriched_system = f"{system}\n\n{live}"
    messages = [{"role": "system", "content": enriched_system}]

    # Add previous turns (skip the last entry if it's the current user message)
    for turn in history:
        role    = turn.get("role", "")
        content = turn.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    # Remove duplicate last user msg if history already includes it
    if messages and messages[-1]["role"] == "user" and messages[-1]["content"] == message:
        messages.pop()

    messages.append({"role": "user", "content": message})

    try:
        reply = ollama_chat(model, messages)
        return jsonify({"reply": reply})
    except requests.exceptions.ConnectionError:
        return jsonify({
            "error": "Ollama serverga ulanib bo'lmadi. "
                     "Terminalni oching va: ollama serve"
        }), 503
    except requests.exceptions.Timeout:
        return jsonify({"error": "Model javob bermadi (timeout). Qaytadan urinib ko'ring."}), 504
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"[INFO] BI Chatbot backend → http://localhost:{port}")
    print(f"[INFO] Ollama URL  : {OLLAMA_BASE}")
    print(f"[INFO] Default model: {DEFAULT_MODEL}")
    print("[INFO] Press Ctrl+C to stop.")
    app.run(host="0.0.0.0", port=port, debug=False)
