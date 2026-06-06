#!/bin/bash
# ────────────────────────────────────────────────────────────────
#  BI Traffic System — start everything with one command
#  Usage:  bash start.sh
# ────────────────────────────────────────────────────────────────

set -e
cd "$(dirname "$0")"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}  BI Traffic Monitoring System       ${NC}"
echo -e "${GREEN}=====================================${NC}"

# ── 1. Ollama ────────────────────────────────────────────────────
echo -e "\n${YELLOW}[1/3] Ollama ishga tushirilmoqda...${NC}"
pkill -f "ollama serve" 2>/dev/null || true
sleep 1
ollama serve &>/tmp/bi_ollama.log &
OLLAMA_PID=$!
echo -e "      PID: $OLLAMA_PID  |  Log: /tmp/bi_ollama.log"

# Wait for Ollama to be ready
for i in {1..10}; do
  sleep 1
  if curl -sf http://localhost:11434/api/tags &>/dev/null; then
    echo -e "      ${GREEN}✓ Ollama tayyor${NC}"
    break
  fi
  [ $i -eq 10 ] && echo -e "      ${RED}✗ Ollama ishga tushmadi${NC}" && exit 1
done

# ── 2. Flask backend ─────────────────────────────────────────────
echo -e "\n${YELLOW}[2/3] Flask backend ishga tushirilmoqda (port 8080)...${NC}"
pkill -f "python server.py" 2>/dev/null || true
sleep 0.5
PORT=8080 .venv/bin/python server.py &>/tmp/bi_server.log &
SERVER_PID=$!
echo -e "      PID: $SERVER_PID  |  Log: /tmp/bi_server.log"
sleep 2

if curl -sf http://localhost:8080/health &>/dev/null; then
  echo -e "      ${GREEN}✓ Backend tayyor → http://localhost:8080${NC}"
else
  echo -e "      ${RED}✗ Backend ishga tushmadi. Log: /tmp/bi_server.log${NC}"
  exit 1
fi

# ── 3. Chatbot UI ────────────────────────────────────────────────
echo -e "\n${YELLOW}[3/3] Chatbot UI ochilmoqda...${NC}"
open "http://localhost:8080"
echo -e "      ${GREEN}✓ Chatbot ochildi → http://localhost:8080${NC}"

# ── 4. YOLO kamera ───────────────────────────────────────────────
echo -e "\n${GREEN}=====================================${NC}"
echo -e "${GREEN}  Hammasi tayyor!${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""
echo -e "  🌐 Chatbot  : chatbot.html (brauzer)"
echo -e "  🔗 Backend  : http://localhost:8080"
echo -e "  🦙 Ollama   : http://localhost:11434"
echo ""
echo -e "${YELLOW}[4/4] YOLO kamera ishga tushirilmoqda...${NC}"
echo -e "      (Oyna yopish uchun 'q' tugmasini bosing)\n"

.venv/bin/python app.py

# ── Cleanup on exit ──────────────────────────────────────────────
echo ""
echo -e "${YELLOW}Toxtatilmoqda...${NC}"
kill $SERVER_PID 2>/dev/null || true
kill $OLLAMA_PID 2>/dev/null || true
echo -e "${GREEN}Barcha servislar toxtatildi.${NC}"
