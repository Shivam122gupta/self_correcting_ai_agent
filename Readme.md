# ⚡ Self-Correcting AI Multi-Agent Platform

An autonomous, self-correcting multi-agent engineering platform powered by **LangGraph**, **Groq Cloud LPU Inference**, and **FastAPI**.

## 🌟 Overview

SelfCorrect AI runs an autonomous **tri-agent evaluation loop** to eliminate AI hallucinations and generate verified, structured engineering specifications.

```
                  ┌──────────────────────┐
                  │    User Prompt       │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │    Writer Agent      │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │   Reviewer Agent     │◄────────────┐
                  └──────────┬───────────┘             │
                             │                         │
                  Is Factual │                         │ Revision
                  Score >= 95%?                        │ Request
                             │                         │
                   ┌─────────┴─────────┐               │
             PASS  │                   │ REVISE        │
                   ▼                   ▼               │
         ┌──────────────────┐ ┌──────────────────┐    │
         │ Accepted Output  │ │  Reviser Agent   ├────┘
         └──────────────────┘ └──────────────────┘
```

---

## 🚀 1-Click Deployment Options

### **Option 1: Deploy on Render (Recommended)**
1. Fork or push this repository to your GitHub account.
2. Click **Deploy to Render** above or create a new Web Service on [Render](https://render.com).
3. Set **Build Command**: `pip install -r requirements.txt`
4. Set **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`
5. Add your Environment Variable: `GROQ_API_KEY=your_groq_api_key`

### **Option 2: Deploy on Railway**
1. Click **Deploy on Railway** or import your repo on [Railway](https://railway.app).
2. Railway automatically detects `Procfile` and deploys your app.
3. Add `GROQ_API_KEY` in environment settings.

### **Option 3: Deploy with Docker**
```bash
docker build -t self-correcting-ai-agent .
docker run -p 8000:8000 -e GROQ_API_KEY="your_groq_api_key" self-correcting-ai-agent
```

---

## 💻 Local Development Setup

### **1. Clone & Install Dependencies**
```bash
git clone https://github.com/Shivam122gupta/self_correcting_ai_agent.git
cd self_correcting_ai_agent
pip install -r requirements.txt
```

### **2. Configure Environment Variables**
Create a `.env` file in the root directory:
```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama3-70b-8192
MAX_REVISIONS=3
MIN_FACTUAL_SCORE=0.95
```

### **3. Run Server**
```bash
python app.py
```
Open **`http://localhost:8000/`** in your browser.

---

## 📂 Project Structure

```
├── app.py              # FastAPI server & route handlers
├── backend.py          # LangGraph multi-agent workflow state graph
├── Procfile            # Cloud platform process file
├── render.yaml         # Render 1-click configuration
├── vercel.json         # Vercel deployment configuration
├── Dockerfile          # Containerized deployment file
├── requirements.txt    # Python production dependencies
├── static/             # CSS & JS frontend assets
│   ├── app.js          # Interactive execution trace handler
│   ├── style.css       # High-contrast brutalist design theme
│   └── logo.png        # SelfCorrect AI emblem logo
└── templates/          # Jinja2 HTML templates
    ├── index.html      # Landing page
    └── workspace.html  # Interactive agent console
```

---

## 📜 Author & License

Created by **[Shivam122gupta](https://github.com/Shivam122gupta)**.  
Licensed under the **MIT License**.
