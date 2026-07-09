# SoccerSolver

A full-stack football analytics assistant — player search, individual profiles,
head-to-head comparison, and a conversational "Ask SoccerSolver" AI interface.

**Stack:** FastAPI · React + TypeScript · Vite · Recharts · OpenAI GPT-4o-mini · Docker Compose

---

## Quick start (Docker)

```bash
# 1. Clone
git clone https://github.com/varunrout/soccersolver-assessment.git
cd soccersolver-assessment

# 2. Set environment variables (only OPENAI_API_KEY is strictly needed for chat)
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# 3. Build and run
docker-compose up --build
```

| Service  | URL                     |
|----------|-------------------------|
| Frontend | http://localhost:3000   |
| Backend  | http://localhost:8000   |
| API docs | http://localhost:8000/docs |

---

## Local development (without Docker)

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env          # add OPENAI_API_KEY
uvicorn main:app --reload     # or: uvicorn backend.main:app --reload from root
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env          # VITE_API_BASE_URL=http://localhost:8000
npm run dev                   # http://localhost:5173
```

---

## Project structure

```
soccersolver-assessment/
├── backend/
│   ├── main.py               FastAPI entry point
│   ├── routers/              search · profile · compare · chat
│   ├── services/             data · stats · comparison service stubs
│   ├── models/               Pydantic models (player, chat responses)
│   ├── nlu/                  OpenAI intent parser stub
│   ├── data/
│   │   ├── players.csv       2,442 players, 5 leagues, season 2021-22
│   │   └── README.md         dataset documentation
│   └── scripts/
│       ├── build_dataset.py  regenerate players.csv from FBref RDS files
│       └── validate_dataset.py  23-check validation suite
├── frontend/
│   ├── src/
│   │   ├── pages/            SearchPage · ProfilePage · ComparePage · ChatPage
│   │   ├── components/       PlayerCard · MetricsChart · ComparisonChart · ResponseRenderer
│   │   ├── types/            TypeScript types mirroring backend Pydantic models
│   │   └── api/client.ts     axios instance
│   └── nginx.conf            SPA routing (no 404 on refresh)
└── docker-compose.yml
```

---

## Environment variables

| Variable | Where | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | backend `.env` | GPT-4o-mini for the chat NLU layer |
| `CSV_PATH` | backend `.env` | Path to players.csv (default: `data/players.csv`) |
| `VITE_API_BASE_URL` | frontend `.env` | Backend URL baked into the Vite bundle |
