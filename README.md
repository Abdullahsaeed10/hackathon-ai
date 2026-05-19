# Verdict

An autonomous AI agent system that scouts hackathon competition and passes judgment on submissions.

## Modes

- **Scout** — reads the competitive field: clusters, gaps, threats
- **Judgment** — ranks submissions against a custom rubric

## Stack

- Backend: Python / Flask / Gevent
- AI: Google Gemini (`gemini-2.5-pro` for reasoning, `gemini-2.5-flash` for parsing)
- Frontend: React + Babel (CDN), Cormorant Garamond + JetBrains Mono
- Storage: file-based JSON verdicts in `data/`
- Streaming: Server-Sent Events over POST

## Quick start

```bash
cp .env.example .env
# edit .env — add GEMINI_API_KEY

pip install -r requirements.txt
python -m playwright install chromium

python app.py
# → http://localhost:5000
```

## Production

```bash
VULTR_HOST=your.server.ip bash deploy.sh
```

Runs as a systemd service via gunicorn + gevent workers (required for SSE).

## API

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/scout` | Scout a hackathon URL (streams SSE) |
| POST | `/api/judgment` | Judge submissions (streams SSE) |
| POST | `/api/upload` | Upload submission file |
| GET  | `/api/verdict/<id>` | Retrieve saved verdict |
| GET  | `/api/health` | Health check |

### SSE event shapes

```json
{"type": "thought",     "text": "→ summoning submissions from the field…"}
{"type": "tool_call",   "tool": "fetch_page", "args_summary": "lablab.ai/…"}
{"type": "tool_result", "tool": "fetch_page", "summary": "1.2MB HTML, 47 project blocks found"}
{"type": "final",       "verdict_id": "v_abc123", "report": {…}}
{"type": "error",       "message": "…"}
```

### Scout request

```bash
curl -N -X POST http://localhost:5000/api/scout \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://lablab.ai/event/milan-ai-week-hackathon"}'
```

### Judgment request (hackathon URL)

```bash
curl -N -X POST http://localhost:5000/api/judgment \
  -H 'Content-Type: application/json' \
  -d '{"source_type":"hackathon_url","hackathon_url":"https://lablab.ai/event/milan-ai-week-hackathon","rules":"must use Vultr, must use Gemini, must have video demo"}'
```

### Judgment request (file upload)

```bash
# 1. Upload
FILE_ID=$(curl -s -X POST -F "file=@submissions.csv" http://localhost:5000/api/upload | python3 -c "import sys,json; print(json.load(sys.stdin)['file_id'])")

# 2. Judge
curl -N -X POST http://localhost:5000/api/judgment \
  -H 'Content-Type: application/json' \
  -d "{\"source_type\":\"uploaded_file\",\"uploaded_file_id\":\"$FILE_ID\",\"rules\":\"Novelty 40, Technical depth 30, Real-world impact 30\"}"
```

### Judgment request (manual text)

```bash
curl -N -X POST http://localhost:5000/api/judgment \
  -H 'Content-Type: application/json' \
  -d '{"source_type":"manual_text","manual_text":"Project A: does X. Project B: does Y."}'
```

### Retrieve verdict

```bash
curl http://localhost:5000/api/verdict/v_K3p2lQ
```

## Models

| Role | Model |
|------|-------|
| Planning, scoring, cluster analysis, final summaries | `gemini-2.5-pro` |
| Link extraction, description writing, rule parsing, freeform parsing | `gemini-2.5-flash` |

## Frontend routing

The app uses History API routing. All paths serve `static/index.html` and the client handles `/`, `/scout`, `/judgment`, `/v/<id>`.

The frontend gracefully falls back to mock data when the backend is unavailable — useful for design demos.
