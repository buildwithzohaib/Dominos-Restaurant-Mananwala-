# My Restaurant POS

Standalone restaurant POS MVP inspired by the workflows studied in URY, implemented independently.

Stack: React + TypeScript + Vite, FastAPI, SQLAlchemy, SQLite.

Features:
- Menu/categories and product search
- Cart and quantity controls
- Dine In / Takeaway / Delivery
- Table selection
- Discount and tax
- Cash/card/other payment
- Persistent SQLite orders
- Order history
- Browser-print receipt
- Seeded sample data

## Backend
```cmd
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python seed.py
uvicorn app.main:app --reload
```

API: http://127.0.0.1:8000
Docs: http://127.0.0.1:8000/docs

## Frontend
Open a second terminal:
```cmd
cd frontend
npm install
npm run dev
```
Open the Vite URL, normally http://localhost:5173.

The backend uses SQLite, so no Docker/WSL/database server is required.

## Structure
```text
my-pos/
├── backend/
│   ├── app/
│   │   ├── models/
│   │   ├── routes/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── database.py
│   │   └── main.py
│   ├── requirements.txt
│   └── seed.py
└── frontend/
    ├── src/
    │   ├── components/
    │   ├── context/
    │   ├── data/
    │   ├── pages/
    │   ├── services/
    │   ├── types/
    │   ├── App.tsx
    │   └── main.tsx
    └── package.json
```

Later phases can add KOT/KDS, thermal/QZ printing, authentication, inventory, backups and offline sync.
