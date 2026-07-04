# Crusoe Multimodal Graph Integration Design

Date: 2026-07-05

## Objective

Extend the existing Ebola test-kit resupply application so image and audio reports become validated operational observations, approved observations update Neo4j through fixed Cypher operations, and a global situation agent produces grounded text briefings that the browser can read aloud.

The deterministic risk, resupply, and transfer engines remain the authority for operational decisions. Models extract facts and explain computed state; they do not generate arbitrary Cypher or approve transfers.

## Current Baseline

The repository already provides:

- FastAPI routes for clinics, warehouses, graph links, transfers, and recommendations.
- Neo4j `Clinic`, `Warehouse`, and `CAN_SUPPLY` data with deterministic seed data.
- Deterministic risk and recommendation engines.
- Pydantic API models.
- A React dashboard and map.
- A generic OpenAI-compatible critical-case LLM note.

The repository does not yet provide media ingestion, model routing, observation history, trend computation, global briefings, safe event-to-Cypher mapping, or Crusoe-specific tests. The checked-in `CRUSOE.md` file is empty and the existing environment example still targets Mistral.

## Approaches Considered

### 1. Explicit FastAPI orchestration — selected

Each task has a dedicated service and a fixed model assignment. Pydantic contracts connect the services. Graph writes use backend-owned Cypher templates.

Benefits: auditable, easy to test, preserves deterministic authority, and fits the existing code. It also demonstrates agent cooperation without adding a workflow framework.

### 2. Tool-calling supervisor agent

Kimi would act as a supervisor and call graph, image, audio, and update tools.

Trade-off: this looks more visibly agentic, but introduces tool-loop failure modes, harder testing, and a larger risk that model behavior influences writes. It is deferred until the explicit pipeline is stable.

### 3. Durable workflow framework

Use LangGraph, Celery, or another workflow engine for asynchronous media processing and retries.

Trade-off: appropriate for production workloads, but unnecessary for the hackathon MVP. The service boundaries in this design allow a workflow engine to be added later without changing API contracts.

## Model Responsibilities

### Image extraction: `google/gemma-4-31b-it`

Gemma receives one image plus a short schema-focused prompt. It returns a structured `ObservationCandidate` and never receives database credentials. It is responsible for visible facts such as clinic identity, people waiting, visible kit counts, or an explicitly displayed status.

### Audio extraction: `nvidia/Nemotron-3-Nano-Omni-Reasoning-30B-A3B`

Nemotron receives an audio clip and returns both a transcript and a structured `ObservationCandidate`. Thinking is disabled for transcription and structured extraction to reduce latency and avoid reasoning text contaminating JSON.

### Global synthesis: `moonshotai/Kimi-K2.6`

Kimi receives a backend-built situation snapshot containing current clinic state, deterministic trends, alerts, transfers, and recent applied observations. It returns a typed `SituationBriefing`. Thinking is disabled for this structured response. The backend does not ask Kimi to calculate risk or select transfers.

### Speech output

The three selected models return text. The MVP converts the Kimi briefing to speech in the frontend with the browser `speechSynthesis` API. Real phone calls or server-generated audio require a separate TTS and telephony integration and are outside this implementation slice.

## Data Contracts

### Observation candidate

Every extraction returns a discriminated Pydantic model with these common fields:

- `event_type`
- `clinic_id`
- `source_type`: `image`, `audio`, or `manual`
- `confidence`: 0 through 1
- `observed_at`
- `raw_text` or transcript when available
- `evidence_summary`

Supported initial event variants:

- `QUEUE_COUNT_UPDATED` with `people_waiting`.
- `TEST_KITS_UPDATED` with `test_kits_available`.
- `NURSES_AVAILABLE_UPDATED` with `nurses_available`.
- `CLINIC_STATUS_REPORTED` with a non-mutating status note.

The first three variants can update a `Clinic`. Status reports are retained as observations but do not mutate operational quantities.

### Observation persistence

Neo4j gains an `Observation` node with:

- `id`, `event_type`, `source_type`, and `status`.
- extracted values and confidence.
- transcript/evidence summary.
- timestamps, model ID, request ID, and error detail when relevant.

Each observation links to its target clinic through:

```text
(:Observation)-[:OBSERVED_AT]->(:Clinic)
```

Statuses are `pending_review`, `applied`, `rejected`, and `failed`.

### Situation briefing

`SituationBriefing` contains:

- `global_status`: `stable`, `watch`, `degrading`, or `critical`.
- `headline` and `summary`.
- `detected_trends`.
- `center_messages`, each tied to a known clinic ID.
- `recommended_operator_checks`.
- `generated_at`, model ID, and source observation IDs.

## Safe Graph Update Policy

The model never returns Cypher. `ObservationService` maps each allowed event type to one backend method and one parameterized Cypher transaction.

1. Persist the candidate as an `Observation`.
2. Validate the clinic exists and all values satisfy Pydantic constraints.
3. Apply automatically when confidence is at least `0.90`.
4. Leave lower-confidence observations as `pending_review`.
5. When applied, update only the allowlisted property for that event.
6. Recompute clinic metrics in the same transaction or immediately afterward.
7. Preserve previous and new values on the observation for auditability.

Review endpoints allow an operator to apply or reject a pending observation. Reprocessing the same observation ID is idempotent.

## Request Flows

### Image

1. Frontend uploads JPEG or PNG with an optional clinic hint.
2. FastAPI validates MIME type and size and converts the image to a data URL.
3. `CrusoeClient` calls Gemma.
4. The response is validated as an `ObservationCandidate`.
5. `ObservationService` stores and conditionally applies it.
6. The backend returns the observation, updated clinic, and refreshed recommendation.

### Audio

1. Frontend records or uploads WAV/MP3 with an optional clinic hint.
2. FastAPI validates MIME type and size.
3. `CrusoeClient` calls Nemotron with thinking disabled.
4. Transcript and extracted event are validated.
5. The same observation workflow stores and conditionally applies the event.

### Global briefing

1. `SituationService` reads all clinics, current alerts and transfers, and recent applied observations.
2. Deterministic code calculates changes over the selected time window.
3. Kimi converts that bounded snapshot into `SituationBriefing`.
4. The frontend displays the briefing and can read it aloud.

## Backend File Design

Existing files to refactor:

- `backend/app/config.py`: replace generic LLM settings with Crusoe base URL, API key, three model IDs, timeouts, retry count, confidence threshold, and upload limits.
- `backend/app/models.py`: keep existing domain models and move new inference/observation contracts into focused modules to prevent further growth.
- `backend/app/services/llm_agent.py`: replace the Mistral-specific single-model implementation with compatibility wrappers or remove it after callers migrate.
- `backend/app/services/seed_data.py`: add observation constraints without changing the existing demo entities.
- `backend/app/main.py`: register ingestion, observations, and briefing routers.
- `backend/requirements.txt`: add multipart upload and image-processing dependencies.
- `backend/.env.example`: document Crusoe configuration without secrets.

New files:

```text
backend/app/models/
  observations.py
  inference.py
  briefings.py
backend/app/services/
  crusoe_client.py
  model_router.py
  media_service.py
  observation_service.py
  situation_service.py
backend/app/routes/
  ingestion.py
  observations.py
  briefings.py
backend/app/prompts/
  image_observation.md
  audio_observation.md
  situation_briefing.md
```

The repository context file will be populated with the verified Crusoe conventions or replaced by a short local reference that points to the maintained source. `AGENTS.md` will instruct coding agents to read it before changing inference code.

## Frontend File Design

New components:

```text
frontend/src/components/
  MediaIngestionPanel.tsx
  ObservationReviewPanel.tsx
  SituationBriefingPanel.tsx
```

`MediaIngestionPanel` supports image upload and microphone recording. `ObservationReviewPanel` displays extracted values, confidence, source, and apply/reject actions. `SituationBriefingPanel` displays the global status and uses `window.speechSynthesis` for local voice playback.

The API client and TypeScript types gain contracts matching the Pydantic response models.

## Crusoe Client Behavior

`CrusoeClient` uses the existing OpenAI Python SDK against:

```text
https://api.inference.crusoecloud.com/v1/
```

It exposes task-specific methods rather than a general `complete()` method. It provides:

- explicit model IDs;
- timeouts;
- bounded retries for rate limits and transient server errors;
- request ID and token usage capture;
- safe error mapping;
- no secret logging;
- structured-response validation;
- dependency injection so tests never call Crusoe accidentally.

Application startup validates configuration shape but does not make a paid inference call. A separate diagnostic endpoint or script lists available models and performs opt-in smoke tests.

## Error Handling

- Invalid media returns `400` or `413` before Crusoe is called.
- Authentication and unavailable models return a safe `503` with an internal diagnostic code.
- Malformed model output creates a `failed` observation and never updates a clinic.
- Low confidence creates `pending_review` rather than an error.
- Neo4j transaction failure leaves the observation unapplied and preserves an error record where possible.
- Kimi failure leaves deterministic alerts and recommendations available; the UI marks only the generated briefing unavailable.

## Testing Strategy

### Unit tests

- Validate each Pydantic event variant and reject invalid values.
- Verify event-to-property allowlisting.
- Verify confidence threshold behavior and idempotency.
- Test situation trend calculations without any model.
- Test media type and size validation.

### Contract tests with mocked Crusoe responses

Inject a fake Crusoe transport and store sanitized fixtures for:

- valid Gemma image extraction;
- malformed Gemma JSON;
- valid Nemotron audio extraction and transcript;
- valid Kimi situation briefing;
- rate limit, timeout, authentication error, and unknown model.

These tests assert exact model routing and request parameters without network calls.

### Neo4j integration tests

Use the Docker Neo4j service with a test database or resettable test graph. Submit an observation, verify its relationship and previous/new values, verify clinic metrics changed, and verify duplicate submission does not apply twice.

### Opt-in Crusoe smoke tests

Tests marked `crusoe_live` run only when `CRUSOE_API_KEY` and an explicit opt-in flag are set. Use one small fixture per model and never run them in the default unit suite.

### End-to-end demo

1. Reset the graph.
2. Upload a fixture image showing an updated queue or kit count.
3. Review the extracted observation and confirm the graph update.
4. Upload or record a fixture voice report.
5. Confirm the transcript, observation, graph update, and recalculated risk.
6. Generate the global briefing.
7. Verify center-specific messages and browser speech playback.

## Security and Operational Constraints

- `CRUSOE_API_KEY` remains in `.env` or the deployment secret store and is never sent to the frontend.
- File content and model output are untrusted inputs.
- No unrestricted Cypher is accepted over HTTP or generated by a model.
- Uploads are size-limited and processed in memory for the MVP; they are not persisted by default.
- Logs contain request IDs, model IDs, latency, and status, but not API keys or full sensitive media.
- Human-approved transfer creation remains separate from observation ingestion.

## Implementation Sequence

1. Stabilize the Python environment and baseline tests.
2. Introduce configuration and typed contracts.
3. Add the injectable Crusoe client and model router.
4. Add observation schema, constraints, and safe update service.
5. Add image and audio ingestion routes.
6. Add deterministic situation snapshot and Kimi briefing.
7. Add frontend ingestion, review, briefing, and browser speech.
8. Add mocked contract, Neo4j integration, live smoke, and end-to-end tests.
9. Update README, `AGENTS.md`, and Crusoe operational documentation.

## Success Criteria

- An image reaches Gemma and produces a validated observation.
- An audio report reaches Nemotron and produces a transcript plus validated observation.
- Only allowlisted, validated events can mutate Neo4j.
- Low-confidence and failed extractions never silently mutate operational state.
- Risk and resupply recommendations remain deterministic.
- Kimi produces a grounded global briefing from a backend-built graph snapshot.
- The frontend displays and can read the briefing aloud.
- Default tests use no external API, while opt-in tests verify all three live Crusoe models.
