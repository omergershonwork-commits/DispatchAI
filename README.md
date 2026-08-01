<div align="center">
  <img src="https://img.icons8.com/color/120/000000/ambulance.png" alt="Logo"/>
  
  # 🚨 AI Rescue Connect (DispatchAI)
  **AI-assisted incident intake and volunteer dispatch for high-pressure emergency coordination.**
  
  [![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
  [![FastAPI](https://img.shields.io/badge/FastAPI-High%20Performance-green.svg)](https://fastapi.tiangolo.com/)
  [![React](https://img.shields.io/badge/React-18-blue.svg)](https://reactjs.org/)
  [![Qwen](https://img.shields.io/badge/AI-Qwen%202.5%20(14B)-orange.svg)](https://qwenlm.github.io/)
  [![AMD](https://img.shields.io/badge/Hardware-AMD%20ROCm-red.svg)](https://www.amd.com/)
</div>

<br/>

> **⚠️ Safety Notice**
> DispatchAI is a coordination platform and hackathon prototype. It does not replace official emergency services, trained dispatchers, police, fire departments, medical services, or human approval in safety-critical operations.

## 🌐 Overview
**AI Rescue Connect** is a completely autonomous, AI-driven emergency response platform designed to eliminate dispatch bottlenecks during mass casualty events. Emergency reports are often incomplete, multilingual, emotional, or spread across multiple messages. DispatchAI reduces the operational burden by turning those chaotic reports into validated incident records and explainable volunteer recommendations.

The platform is designed around three core principles:
1. **Understand the incident accurately.**
2. **Exclude responders who are unavailable or ineligible.**
3. **Explain why a responder was selected or rejected.**

---

## 🧠 Why AMD Compute Matters
Incident understanding is more demanding than simple classification. Reports can contain uncertainty, corrections, mixed languages, missing details, and several facts that must be reconciled. 

The **AMD developer notebook environment** provides the VRAM and compute capacity required to run a stronger, reasoning-capable **Qwen 2.5 14B** model completely locally. This drastically improves extraction quality compared with using a significantly smaller local model, while ensuring zero data-privacy leaks (no civilian medical data is sent to cloud APIs like OpenAI). The model does not directly execute irreversible actions; its output is validated, persisted, logged, and passed into deterministic eligibility and matching rules.

---

## 🔥 Key Features & Capabilities

- 🧠 **Zero-Latency NLU (Structured Extraction):** Uses local AMD-accelerated Qwen to parse unstructured texts into strict JSON schemas (Type, Urgency, Location, Casualties, Missing Fields, Confidence).
- 💬 **Autonomous Follow-Ups:** If a citizen sends a vague location ("There's a fire in my building!"), the AI detects the missing variables and autonomously replies in natural language to ask for the exact address.
- 🗺️ **Intelligent Geocoding & GPS:** Supports Telegram live GPS as well as text-address geocoding via ArcGIS REST API.
- ⚡ **Auto-Dispatch Engine:** Automatically matches the nearest and most qualified volunteers to active incidents using Haversine distance calculations and Hard travel-radius enforcement.
- 📊 **Real-Time Tactical Dashboard:** A beautiful React frontend utilizing OpenStreetMap/Leaflet to show active incidents, volunteer locations, and operator dossiers in real-time.
- 📱 **Telegram Lifecycle:** Manages volunteer registration, dispatch offers, and the Accept/Decline/Timeout/Done lifecycle directly through Telegram bots.
- 🔍 **Observability:** Structured operational logs for auditing (e.g., `volunteer_excluded reason=outside_travel_radius`).

---

## ⚙️ Volunteer Selection Logic
Volunteer selection is split into two deterministic stages:

### 1. Hard Eligibility Filters
A volunteer is completely excluded before scoring when:
- Status is not 'available' or registration is incomplete.
- They are already busy with an open dispatch.
- Coordinates are missing (while geospatial matching is enabled).
- Calculated distance exceeds their maximum allowed travel radius.
*(A highly skilled but distant volunteer is therefore never selected).*

### 2. Weighted Ranking
Eligible volunteers are ranked by: **Location/Distance**, **Skill Match**, **Estimated Response Time**, **Reliability/Trust Score**, **Inventory**, and **Vehicle Match**.
Weights vary by scenario. Medical incidents emphasize medical skills and response time, while evacuation incidents place more weight on vehicle suitability.

---

## 🛠️ Architecture & Tech Stack

```text
Reporter / Volunteer
        |
        v
Telegram Bot API
        |
        v
FastAPI Webhook Layer
        |
        +---------------------------+
        |                           |
        v                           v
Qwen Incident Extraction     Volunteer Management
        |                           |
        +-------------+-------------+
                      |
                      v
             PostgreSQL (Supabase)
                      |
                      v
          Geospatial Eligibility Filter
                      |
                      v
       Scenario-Specific Weighted Ranking
                      |
                      v
            Telegram Dispatch Offer
```

### **Tech Stack**
- **Backend:** Python 3.10+, FastAPI, SQLAlchemy, Pydantic
- **Database:** PostgreSQL (Supabase)
- **AI Inference:** Qwen 2.5 14B (AMD-hosted OpenAI-compatible endpoint)
- **Frontend:** React, Vite, `react-leaflet`
- **Infrastructure:** Docker, Docker Compose, GitHub Actions

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+ / Node.js 18+
- Reachable Qwen endpoint (e.g., LM Studio on port 8001)
- Supabase PostgreSQL database
- Telegram bot tokens (for live Telegram flows)

### 2. Configuration (`.env`)
Create a `.env` file in the `backend/` directory. **Never commit real tokens.**
```ini
# Application & Database
APP_NAME=AI-Rescue-Connect
DATABASE_URL=postgresql+psycopg://user:pass@db.supabase.com:5432/postgres

# Local AI (Qwen on AMD)
QWEN_BASE_URL=http://localhost:8001
QWEN_MODEL_NAME=qwen
QWEN_TIMEOUT_SECONDS=30

# Telegram Bots
TELEGRAM_INCIDENT_BOT_TOKEN=your_incident_bot_token
TELEGRAM_VOLUNTEER_BOT_TOKEN=your_volunteer_bot_token
```

### 3. Run Locally (Development)
**Backend:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### 4. Run with Docker
```bash
docker compose up --build -d
# Verify
curl http://localhost:8000/health
# View Logs
docker compose logs -f backend
```

---

## 🎮 How to Use & Demo Flow

Because testing Telegram Webhooks locally requires tunneling (like Ngrok/Pinggy), we have included a **Simulation Script** that bypasses Telegram and allows you to test the AI pipeline directly against your local backend.

1. Ensure your local LLM (Qwen) is running on `localhost:8001`.
2. Ensure your FastAPI backend is running on `localhost:8000`.
3. **Seed Database:** Generate 30 realistic volunteers scattered across Israel:
   ```bash
   python backend/seed_demo_volunteers.py
   ```
4. **Run Simulation:** Fire 3 hyper-realistic emergency scenarios into the AI pipeline:
   ```bash
   python backend/simulate_telegram.py
   ```
5. **Watch the Dashboard:** You will see the AI process the events, plot them on the map, and assign volunteers autonomously!

---

## 🔒 Security & Production Hardening
Before deployment in a real emergency environment, the following must be completed:
- Signed and authenticated webhooks.
- Dashboard authentication and Role-Based Access Control (RBAC).
- TLS termination and managed secret storage.
- Encrypted sensitive medical data.
- Formal security testing and audit retention policies.
- **Human approval rules for safety-critical dispatch.**

---

## 🗺️ Roadmap
- Volunteer location freshness enforcement.
- Road-route travel-time estimation.
- Parallel top-candidate offers with atomic first acceptance.
- Dispatcher assignment and reassignment controls.
