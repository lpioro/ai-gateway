# Local Context Engine (MVP)

Project-scoped memory, approved by the user before it can influence answers.

## Data model

- `projects`: project scope (UUID, name).
- `facts`: note text, source, status (`pending`, `approved`, `rejected`), timestamps.
- `facts_fts`: local SQLite FTS5 index, maintained by triggers.
- Existing `chats` and `messages` remain unchanged.

**Privacy:** all stored facts and FTS indexes remain in the SQLite database configured by `DATABASE_PATH`. Only relevant **approved** facts, displayed in Preview, are included in the model request. If the selected provider is Gemini/OpenAI/Groq, that content leaves the LAN. Set `FORCE_LOCAL_ONLY=true` to block cloud requests.

## Usage

1. Connect with your gateway password.
2. Open **Pamięć projektu**, create a project and select it in the top bar.
3. Add a candidate fact. It starts as **pending** and is not used.
4. Approve or reject explicitly.
5. Enter a question in the composer and click **Podgląd dla wpisanego pytania**.
6. With **Kontekst** enabled, send the question. The server independently rebuilds the prompt context at send time.

The preview is a snapshot. If facts change between preview and sending, the actual context can change; the server always rechecks status. No automatic LLM-based fact extraction is performed in this MVP. Facts are entered manually and must be approved.

## Retrieval

FTS5 performs keyword retrieval (Unicode tokenization, OR terms, bm25 ranking), scoped by `project_id` and `approved`. Max 5 facts and 5500 characters. This is **lexical**, not semantic/vector RAG; synonymous wording without shared terms may not match.

The system message treats facts as untrusted source data, not instructions. Prompt injection risk is reduced but cannot be eliminated when including third-party text in prompts.

## API

Authenticated via `X-Gateway-Password`:
- `GET/POST /api/projects`
- `GET/POST /api/projects/{project_id}/facts`
- `PATCH/DELETE /api/projects/{project_id}/facts/{fact_id}`
- `POST /api/context/preview` with `project_id`, `question`
- `POST /api/chat` with optional `project_id` and `use_context` (default true)

Never place API keys, passwords, health/financial personal details or confidential customer data into project memory unless you understand the retention and cloud transmission implications.

## Upgrade on labstack (native LXC)

Back up `/var/lib/ai-gateway/gateway.db`, then update sources and reinstall using the native installer as documented in [LXC.md](LXC.md). SQLite tables and FTS index are initialized on service start. Stop the service while copying the DB for backup.

## Limitations

Single shared password; not multi-tenant authentication. Project isolation is an application query filter, not a separate database or OS-level isolation. HTTPS/firewall still recommended. No background memory mining, embeddings, automatic versioning, or source verification yet.
