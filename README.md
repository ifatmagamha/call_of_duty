# Ebola Test Kit Resupply Platform

MVP for graph-backed Ebola test kit resupply decisions around Kinshasa, DRC.

The backend owns all operational calculations:

- nurse testing capacity
- queue delay
- operations remaining
- risk level
- ranked resupply options from warehouses and connected clinics

The frontend displays a Leaflet map, warehouse and clinic markers, Neo4j
warehouse supply routes, selected node details, clinic update form, and
deterministic agent reasoning from backend data.

## Structure

```text
backend/   FastAPI, Neo4j driver, deterministic risk and recommendation logic
frontend/  React, TypeScript, Leaflet, Tailwind
docker-compose.yml  Neo4j local service
```

## Run Locally

Start Neo4j:

```bash
docker compose up -d neo4j
```

Run the backend:

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

If port `8000` is already occupied, use another port:

```bash
uvicorn app.main:app --reload --port 8010
```

Seed demo data:

```bash
curl -X POST http://127.0.0.1:8000/admin/reset-demo-data
```

The agent endpoint is deterministic. When a clinic is high or critical risk,
it proposes a solution using only Neo4j warehouse-to-clinic `CAN_SUPPLY`
relationships. Clinic-to-clinic stock is intentionally excluded.

Optional critical-case LLM note:

```bash
export LLM_API_KEY=your_mistral_key
export LLM_BASE_URL=https://api.mistral.ai/v1
export LLM_MODEL=mistral-small-latest
```

The deterministic recommendation remains the source of truth. The LLM note
appears underneath it only for `critical` clinics and receives only a JSON
payload built from Neo4j warehouse/clinic data, warehouse-to-clinic supply
relationships, and deterministic backend outputs.

Run the frontend:

```bash
cd frontend
npm install
npm run dev
```

If the backend is running on a non-default port, set `VITE_API_BASE_URL`:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8010 npm run dev
```

Open `http://127.0.0.1:5173`.

## Key Endpoints

```text
GET  /health
POST /admin/reset-demo-data
GET  /clinics
GET  /clinics/{clinic_id}
PATCH /clinics/{clinic_id}
GET  /warehouses
GET  /warehouses/{warehouse_id}
PATCH /warehouses/{warehouse_id}
GET  /supply-links
GET  /clinics/{clinic_id}/resupply-options
GET  /clinics/{clinic_id}/agent-recommendation
POST /clinics/{clinic_id}/transfers
GET  /transfers
GET  /alerts
```

Approving a transfer reserves stock immediately by decrementing the selected
warehouse and creates an `ongoing` transfer record. Clinic stock is not
increased until a future completion workflow is added.

## Demo Checks

Clinic B should start as high risk:

```text
35 kits, 96 people waiting, 2 nurses
capacity = 24 tests/hour
queue delay = 4.0 hours
operations remaining = 1.46 hours
```

The top recommendation should be Central Medical Warehouse with 61 kits.

Clinic D should also start as high risk:

```text
20 kits, 60 people waiting, 1 nurse
capacity = 12 tests/hour
queue delay = 5.0 hours
operations remaining = 1.67 hours
```

The top recommendation should be East Logistics Hub with 28 kits.

## Tests

Run backend calculation tests:

```bash
cd backend
PYTHONPATH=. python3 -m unittest discover -s tests
```

If you install `pytest`, the same tests also run with `PYTHONPATH=. pytest`.
