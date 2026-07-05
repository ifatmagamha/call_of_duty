# Ebola Test Kit Resupply Platform

MVP for graph-backed Ebola test kit resupply decisions around Kinshasa, DRC.

The backend owns all operational calculations:

- nurse testing capacity
- queue delay
- operations remaining
- risk level
- ranked resupply options from warehouses and connected clinics

The frontend displays the operational graph and deterministic recommendations,
accepts image/audio clinic observations through Crusoe, supports human review of
low-confidence facts, and explicitly generates grounded Kimi situation briefings.

## Structure

```text
backend/app/api/             FastAPI routers
backend/app/core/            environment settings
backend/app/inference/       task agents, media validation, prompts, model routing
backend/app/infrastructure/  Crusoe and Neo4j provider clients
backend/app/repositories/    fixed parameterized Cypher access
backend/app/schemas/         Pydantic API and inference contracts
backend/app/services/        deterministic operational policy
backend/scripts/             graph initialization and diagnostics
backend/tests/               unit, contract, integration, and live scopes
frontend/                    React, TypeScript, Leaflet, Tailwind
```

## Run Locally

Start Neo4j:

```bash
docker compose up -d neo4j
```

Create the uv-locked environment from the repository root:

```bash
uv sync
```

PowerShell uses the same command. Run the backend:

```bash
cd backend
../.venv/bin/python -m uvicorn app.main:app --reload
```

If port `8000` is already occupied, use another port:

```bash
../.venv/bin/python -m uvicorn app.main:app --reload --port 8010
```

Seed demo data:

```bash
curl -X POST http://127.0.0.1:8000/admin/reset-demo-data
```

The agent endpoint is deterministic. When a clinic is high or critical risk,
it proposes a solution using only Neo4j warehouse-to-clinic `CAN_SUPPLY`
relationships. Clinic-to-clinic stock is intentionally excluded.

On PowerShell, use:

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

The application starts without `CRUSOE_API_KEY`; maps, risk calculations,
recommendations, and transfer approval continue working. Only `/ingestion/*` and
`/briefings/generate` return `503` until a Crusoe key is configured. Copy variable
names from `backend/.env.example` into your private environment; never commit a key.

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
POST /ingestion/image
POST /ingestion/audio
GET  /observations
GET  /observations/{observation_id}
POST /observations/{observation_id}/apply
POST /observations/{observation_id}/reject
POST /briefings/generate
```

Briefing generation is explicit and stateless; there is no `/briefings/latest`
endpoint and normal clinic/recommendation reads never trigger paid inference.

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

## Crusoe safety model

- Gemma (`google/gemma-4-31b-it`) extracts image facts only.
- Nemotron Omni (`nvidia/Nemotron-3-Nano-Omni-Reasoning-30B-A3B`) transcribes
  audio and extracts one event with thinking disabled.
- Kimi (`moonshotai/Kimi-K2.6`) summarizes a bounded backend-built snapshot with
  thinking disabled.
- Complete model output is Pydantic-validated. Models never receive Neo4j
  credentials, generate Cypher, calculate authoritative risk, approve transfers,
  or write graph data.
- Confidence `>= 0.90` auto-applies an allowlisted clinic property; lower
  confidence remains `pending_review`. Status reports never mutate numeric state.
- Uploaded media is validated and processed in memory, then discarded. Images are
  normalized to JPEG up to 1600×1600; audio accepts WAV/MP3 up to 25 MiB. Keep audio
  clips short enough for the provider request timeout (60 seconds by default).

## Tests

Default tests use fake provider clients and no live Neo4j or paid inference:

```bash
cd backend
../.venv/bin/python -m pytest -q
```

PowerShell:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
$env:RUN_NEO4J_INTEGRATION='1'; ..\.venv\Scripts\python.exe -m pytest -m neo4j_integration
$env:RUN_CRUSOE_LIVE='1'; ..\.venv\Scripts\python.exe -m pytest -m crusoe_live
```

Neo4j integration tests reset the configured graph and therefore require the explicit
`RUN_NEO4J_INTEGRATION=1` opt-in. Live tests additionally require a private
`CRUSOE_API_KEY`. Verify platform and graph connections with:

```powershell
..\.venv\Scripts\python.exe scripts\diagnose_system.py --neo4j
..\.venv\Scripts\python.exe scripts\diagnose_system.py --crusoe
..\.venv\Scripts\python.exe scripts\diagnose_system.py  # both
```

The Neo4j check verifies connectivity, constraints, node counts, and the observation
relationship query. The Crusoe check lists models and verifies all three configured
IDs are accessible without printing the key. Model listing does not prove inference;
use the opt-in `crusoe_live` suite for that. See
`docs/context/crusoe-managed-inference.md` for the complete proof ladder.

Build the frontend with `npm.cmd run build` on PowerShell or `npm run build` elsewhere.

## Fixture-based simulation

1. Run `docker compose up -d neo4j` and start FastAPI and React as above.
2. Reset the graph: `curl -X POST http://127.0.0.1:8000/admin/reset-demo-data`.
3. Upload a JPEG/PNG fixture containing a clinic update:

   ```bash
   curl -X POST http://127.0.0.1:8000/ingestion/image \
     -F "file=@fixtures/clinic-board.png;type=image/png" \
     -F "clinic_hint=clinic-b"
   ```

4. Confirm the returned event/confidence. If pending, apply it with
   `curl -X POST http://127.0.0.1:8000/observations/OBSERVATION_ID/apply`.
5. In Neo4j Browser, inspect the audit link with
   `MATCH (o:Observation)-[:OBSERVED_AT]->(c:Clinic) RETURN o,c` and verify the
   clinic's deterministic metrics changed.
6. Record “Clinic B has twenty test kits remaining” or upload a WAV/MP3 fixture:

   ```bash
   curl -X POST http://127.0.0.1:8000/ingestion/audio \
     -F "file=@fixtures/clinic-b-report.wav;type=audio/wav" \
     -F "clinic_hint=clinic-b"
   ```

7. Verify transcript, audit values, risk, and recommendation recomputation.
8. Generate the global briefing:

   ```bash
   curl -X POST http://127.0.0.1:8000/briefings/generate \
     -H "Content-Type: application/json" -d '{"window_hours":24}'
   ```

9. Confirm all briefing clinic IDs and trends exist in the graph-backed snapshot.
   Use “Read aloud” in the UI; it is local browser speech synthesis, not Crusoe TTS.
