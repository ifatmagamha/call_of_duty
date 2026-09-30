# Getting started

Every command needed to run, demo, verify, and test Call of Duty. For what the
product is and why it is built this way, see [README.md](README.md).

Python commands use `uv run`, which always runs in the project's `.venv`, so there is
nothing to activate. Commands work unchanged in bash and PowerShell unless two
versions are shown. On Windows PowerShell, `curl` is an alias for
`Invoke-WebRequest`, so this guide uses `curl.exe` (built into Windows 10+) or
`Invoke-RestMethod`.

## 1. Prerequisites

- Docker Desktop (for Neo4j)
- [uv](https://docs.astral.sh/uv/) (it installs Python 3.13 for the project)
- Node.js 20+
- Optional: a Crusoe API key for the AI features (photo, voice, video, text, Ask)

## 2. Configure

Settings are read from the repository-root `.env`, then `backend/.env`; blank values
keep defaults. Copy variable names from [`backend/.env.example`](backend/.env.example).
Never commit a key. If a value contains `$`, wrap it in single quotes
(`CRUSOE_API_KEY='...'`) so `docker compose` does not try to expand it.

## 3. Run

From the repository root:

```bash
docker compose up -d neo4j        # Neo4j 5 on :7474 (browser) and :7687 (bolt)
uv sync
cd backend
uv run python -m uvicorn app.main:app --reload     # API on http://127.0.0.1:8000
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev                       # UI on http://127.0.0.1:5173
```

If port 8000 is taken, start the API with `--port 8010` and point the UI at it:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8010 npm run dev
```

```powershell
$env:VITE_API_BASE_URL='http://127.0.0.1:8010'; npm run dev
```

Seed the demo graph (8 clinics in Kinshasa and Brazzaville, 3 warehouses), or click
**Reset demo** in the UI:

```bash
curl -X POST http://127.0.0.1:8000/admin/reset-demo-data
```

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/admin/reset-demo-data
```

The app starts without `CRUSOE_API_KEY`. The map, risk, recommendations, transfers,
camera counts, and timelines all work offline. Only the AI endpoints
(`/ingestion/image|audio|video|text`, `/briefings/*`) return `503` until a key is set.

## 4. Five-minute demo

1. Reset the demo, then start simulated cameras (no key needed). From `backend/`:
   `uv run python scripts/simulate_cameras.py --interval 5`.
   Queue counts on the map, the KPIs, and the **Activity** feed update every 5 s.
2. **Actions** tab: dispatch the top resupply. Open the clinic and click
   **Mark delivered**; stock, risk, and the clinic timeline update.
3. **Review** tab: low-confidence readings, and every number from text or video,
   wait here for **Apply** or **Reject**.
4. **Report** tab (needs a key): SMS or phone transcript, photo, voice (record in the
   browser), MP4 video, or **Live camera**.
5. **Ask** tab (needs a key): "Which clinics run out of kits first?", or generate a briefing.

Expected starting state: Lingwala (clinic-b) is **high** risk with 35 kits, 96
people waiting, and 2 nurses (24 tests/h, 4.0 h queue, 1.46 h of operations). Its
top recommendation is Central Medical Warehouse with 61 kits. Masina (clinic-d) is
**high** risk; its top recommendation is East Logistics Hub with 28 kits.

## 5. Use your own camera

### Option A: edge counter (recommended, no API key)

`backend/scripts/camera_counter.py` reads a webcam, video file, or RTSP/HTTP stream.
It counts people with OpenCV's built-in HOG detector and posts each count to
`POST /ingestion/camera`, exactly as a deployed edge device would. From `backend/`:

```bash
# Your laptop webcam watching Lingwala; a reading every 5 s:
uv run python scripts/camera_counter.py --clinic clinic-b
# Write the latest annotated frame so you can see what was detected:
uv run python scripts/camera_counter.py --clinic clinic-b --snapshot last.jpg
# A second webcam, a video file, or an IP camera:
uv run python scripts/camera_counter.py --clinic clinic-d --source 1
uv run python scripts/camera_counter.py --clinic clinic-d --source ../fixtures/footage.mp4
uv run python scripts/camera_counter.py --clinic clinic-d --source rtsp://user:pass@192.168.1.20/stream
```

Stand in front of the camera and watch clinic-b's marker count and timeline change.
Readings with confidence of 0.90 or more apply immediately; lower ones wait in
**Review**. Useful flags:
- `--interval`: seconds between readings.
- `--work-width`: detection resolution. Raise it for distant crowds, lower it for speed.
- `--once`: send one reading and exit.

HOG is a zero-dependency baseline. It finds upright, reasonably sized people but
undercounts dense or aerial crowds (about 10 of roughly 30 people in `fixtures/queue.jpeg`).
Replace `count_people()` with a YOLO/ONNX detector when accuracy matters.

### Option B: browser camera (uses the vision model, needs a key)

**Report → Live camera**: choose the clinic, click **Connect this device's camera**,
and allow access. A frame is sent to Gemma at the chosen interval (15 s to 5 min).
Each frame is a paid inference call.

### Option C: simulator

`scripts/simulate_cameras.py` posts random-walk counts for every clinic. Use it for
demos without any camera.

## 6. Verify the Neo4j integration

**1. Automated checks**, from `backend/`. The integration tests **reset the graph**:

```bash
uv run python scripts/diagnose_system.py --neo4j
RUN_NEO4J_INTEGRATION=1 uv run python -m pytest -q -m neo4j_integration
```

```powershell
uv run python scripts/diagnose_system.py --neo4j
$env:RUN_NEO4J_INTEGRATION='1'; uv run python -m pytest -q -m neo4j_integration
```

The diagnostic checks connectivity, the three uniqueness constraints, node counts,
and the `Observation-[:OBSERVED_AT]->Clinic` links. The integration tests cover
persistence, auditing, idempotency, and the full loop: camera, manual edit,
dispatch, delivery, timeline, and priority actions.

**2. See the graph.** Open <http://localhost:7474>, connect to `neo4j://localhost:7687`
with the credentials from `docker-compose.yml`, and run:

```cypher
// Supply network, in-flight transfers, and the latest evidence for one clinic
MATCH p=(:Warehouse)-[:CAN_SUPPLY]->(:Clinic) RETURN p
UNION MATCH p=(:Warehouse)-[:TRANSFER_SOURCE]->(:Transfer)-[:TRANSFER_TARGET]->(:Clinic) RETURN p
UNION MATCH p=(o:Observation)-[:OBSERVED_AT]->(:Clinic {id:'clinic-b'})
      WITH p, o ORDER BY o.created_at DESC LIMIT 12 RETURN p
```

```cypher
// Audit trail: every applied change with before/after values and risk transition
MATCH (o:Observation)-[:OBSERVED_AT]->(c:Clinic)
RETURN c.name, o.source_type, o.event_type, o.status, o.previous_value, o.new_value,
       o.previous_risk_level, o.new_risk_level, o.created_at
ORDER BY o.created_at DESC LIMIT 25
```

```cypher
// Graph schema
CALL db.schema.visualization()
```

**3. Cross-check the UI against the graph.** The KPI "People waiting" should equal
`MATCH (c:Clinic) RETURN sum(c.people_waiting)`. A clinic's timeline should list the
same observations as the audit-trail query filtered by that clinic.

## 7. Verify the AI models (Crusoe)

From `backend/`:

```bash
uv run python scripts/diagnose_system.py --crusoe     # key valid + 3 models listed
uv run python -m pytest -q tests/contract             # exact request contracts, no network
RUN_CRUSOE_LIVE=1 uv run python -m pytest -q -m crusoe_live    # one real call per model
```

```powershell
$env:RUN_CRUSOE_LIVE='1'; uv run python -m pytest -q -m crusoe_live
```

Model listing proves access, not inference; the live suite proves inference.
With the API running, from the repository root (use `curl.exe` on Windows):

```bash
curl.exe -X POST http://127.0.0.1:8000/ingestion/image -F "file=@fixtures/queue.jpeg;type=image/jpeg" -F "clinic_hint=clinic-b"
curl.exe -X POST http://127.0.0.1:8000/ingestion/audio -F "file=@fixtures/clinic-b-report.wav;type=audio/wav" -F "clinic_hint=clinic-b"
curl.exe -X POST http://127.0.0.1:8000/ingestion/video -F "file=@fixtures/footage.mp4;type=video/mp4" -F "clinic_hint=clinic-b"
```

JSON endpoints:

```bash
curl -X POST http://127.0.0.1:8000/ingestion/text -H "Content-Type: application/json" \
  -d '{"text":"Masina: only 9 test kits left","channel":"sms"}'
curl -X POST http://127.0.0.1:8000/briefings/ask -H "Content-Type: application/json" \
  -d '{"question":"Which clinics run out of kits first?"}'
```

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/ingestion/text -ContentType 'application/json' `
  -Body '{"text":"Masina: only 9 test kits left","channel":"sms"}'
Invoke-RestMethod -Method Post http://127.0.0.1:8000/briefings/ask -ContentType 'application/json' `
  -Body '{"question":"Which clinics run out of kits first?"}'
```

If an observation is `pending_review`, apply it in the **Review** tab or with
`POST /observations/<id>/apply`, then check the change in the audit-trail query above.

## 8. Tests and build

```bash
cd backend
uv run python -m pytest -q        # unit + contract; no Neo4j, no paid calls
cd ../frontend
npm run build                     # type-check + production build
```

## 9. API reference

Interactive docs: <http://127.0.0.1:8000/docs>.

```text
GET  /health                              POST /admin/reset-demo-data
GET  /clinics                             GET  /clinics/{id}
PATCH /clinics/{id}                       GET  /clinics/{id}/timeline
GET  /timeline                            GET  /actions
GET  /alerts                              GET  /clinics/{id}/agent-recommendation
GET  /clinics/{id}/resupply-options       POST /clinics/{id}/transfers
GET  /transfers                           POST /transfers/{id}/complete
GET  /warehouses                          GET|PATCH /warehouses/{id}
GET  /supply-links
POST /ingestion/camera                    POST /ingestion/text
POST /ingestion/image                     POST /ingestion/audio
POST /ingestion/video
GET  /observations                        GET  /observations/{id}
POST /observations/{id}/apply             POST /observations/{id}/reject
POST /briefings/generate                  POST /briefings/ask
```

Camera payload: `{"clinic_id", "camera_id", "people_count", "confidence"}`.

## Troubleshooting

- **`VIRTUAL_ENV=... does not match the project environment`** (from uv): another
  virtualenv is activated. Run `deactivate`. `uv run` uses the right environment
  either way. The project environment is the root `.venv` only.
- **`../.venv/bin/python` is not recognized**: that path only exists on macOS and Linux.
  Use `uv run python ...` as shown in this guide.
- **`[WinError 10013]` or "address already in use" when starting the API**: another
  process already listens on port 8000, usually an earlier uvicorn. Find it with
  `Get-NetTCPConnection -LocalPort 8000 -State Listen` (PowerShell) or `lsof -i :8000`,
  then stop it, or start on another port (see §3).
- **`docker compose` warns a variable "is not set"**: a `.env` value contains `$`;
  wrap it in single quotes.
- **`503 Crusoe rejected the configured credentials`**: rotate `CRUSOE_API_KEY`.
- **`npm install` reports vulnerabilities**: run `npm audit`. All current advisories
  were in build-time tooling and are fixed in `frontend/package-lock.json`.
- **`Cannot open camera source '0'`**: another app holds the webcam, or camera
  access is disabled in your OS privacy settings. Try `--source 1`.
- **The UI shows nothing**: check that `GET /health` returns `neo4j: connected` and that
  the demo was reset.
