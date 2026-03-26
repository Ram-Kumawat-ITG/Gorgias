# Shopify Helpdesk

Private internal helpdesk for a single Shopify store. Support agents manage tickets, view customer/order data from Shopify, get AI-suggested replies, and track SLA compliance.

## Stack

- **Backend:** FastAPI, Motor (async MongoDB), Pydantic v2, APScheduler, OpenAI GPT-4
- **Frontend:** React (Vite), Tailwind CSS, Recharts, React Router v6
- **Database:** MongoDB Atlas
- **Email:** Mailgun Inbound Routes

## Quick Start

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env      # fill in your credentials
python -m scripts.create_agent
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

### First Login

Default agent credentials (change in `scripts/create_agent.py` before running):
- Email: `admin@yourstore.com`
- Password: `change-this-password`

## API Docs

With the backend running: http://localhost:8000/docs
