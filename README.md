# CiteGuard - Citation Verification Platform

CiteGuard is a full-stack web application designed to help researchers verify the authenticity of citations in their academic papers. It cross-references bibliography entries with valid databases and checks citation contexts within LaTeX files.

## Features

- **Automated Verification**: Checks if papers exist using Semantic Scholar, CrossRef, and other sources.
- **Context Analysis**: Uses LLMs to verify if the citation context in the paper matches the actual content of the cited work.
- **Fault Tolerant**: Uses a robust message queue (Celery) to handle long-running verification tasks with retries.
- **Real-time Dashboard**: Track the progress of your citation checks in real-time.
- **Resumable**: Close the tab and come back later; your task verification continues in the background.

## Architecture

- **Backend**: FastAPI
- **Worker**: Celery (with SQLite Broker for portability)
- **Database**: SQLite
- **Frontend**: React + Vite + TailwindCSS

## Quick Start

### 1. Backend Setup
```bash
cd backend
pip install -r requirements.txt
```

### 2. Frontend Setup
```bash
cd frontend
npm install
```

### 3. Running the Application
You need to run 3 terminals:

**Terminal 1 (API):**
```bash
cd backend
uvicorn app.main:app --reload
```

**Terminal 2 (Worker):**
```bash
cd backend
celery -A app.celery_app worker --pool=solo -l info
```

**Terminal 3 (Frontend):**
```bash
cd frontend
npm run dev
```

Visit `http://localhost:5173` to start using CiteGuard.
