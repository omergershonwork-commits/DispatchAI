# DispatchAI: The Next-Gen Autonomous Emergency Grid Powered by AMD

DispatchAI scales to handle simultaneous mass-casualty incidents in under 10 seconds—something a human dispatcher could never do. It leverages an event-driven asynchronous dispatch pipeline to instantly parse chaotic emergency texts via Telegram, match volunteers based on real-time location and skill metrics, and dynamically dispatch resources.

## 🚀 AMD Compute Evidence (Track 3 Requirement)

This project heavily utilizes AMD Instinct™ Accelerators to run the **Qwen2.5-14B-Instruct** model for rapid, accurate AI reasoning on medical dispatches.

**Please review the dedicated AMD evidence folder here:**
👉 [`/amd-compute-evidence`](./amd-compute-evidence)

Inside, you will find our Jupyter Notebook containing the full execution pipeline (`!rocm-smi`, inference execution, and JSON outputs) verifying the hardware backend.

## 🏗️ Quick Start

### 1. Backend (FastAPI)
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 2. Frontend (React/Vite)
```bash
cd frontend
npm install
npm run dev
```

## 🎥 Demo Video & Slide Deck
Please see the submitted Demo Video and Slide Deck (PDF) as part of our Hackathon submission for the complete walk-through of the DispatchAI architecture, human-like AI reasoning, and real-time execution.