# AI Gateway 1.0 — Workspace UI (first iteration)

## Implemented in this branch

- Chat-first responsive layout with sidebar navigation and a compact toolbar.
- Four selectable color schemes: Graphite, Paper, PI-LAB Blue and Forest.
- Theme preference stored **only** in browser localStorage (no passwords/keys).
- Existing streaming chat, history, project selection, approved project facts and context preview kept operational.
- Separate **Models** view showing real provider configuration state from `GET /api/models`.
- Separate **Observability** view with authenticated local SQLite counters for chats, messages, projects, approved and pending facts. No mock metrics.
- **Knowledge Studio** placeholder accurately labelled as not yet implemented.
- Bootstrap Icons via external jsDelivr stylesheet. **Offline icon bundling is still outstanding.** Layout uses local CSS, not Bootstrap component styles.

## Security boundaries

- This does **not** yet implement provider configuration wizard, secure API key vault, file upload, RAG indexing, vector search or tracing.
- It keeps the MVP shared-password mechanism, so do not expose the app to the public Internet or untrusted LAN.
- Do not persist the password to browser localStorage.
- SQLite counters only expose aggregate counts after authentication; no prompts or key material.
- The RAG upload panel deliberately does not accept files until a secure ingestion path exists.

## Next milestones

1. Provider connection wizard backed by server-side credential storage and endpoint testing (validation and SSRF restrictions).
2. RAG ingestion pipeline: file size/type limits, isolated extraction, staging and approval, chunking, provenance and lifecycle controls.
3. Hybrid retrieval: project-filtered FTS5 plus sqlite-vec/locally generated embeddings.
4. Request-level observability: timings, safe metadata, error rates, retention and audit.
5. Bundle Bootstrap Icons locally for offline installations and refine mobile accessibility.

## Manual browser checks

- Open UI, select Paper, reload: theme persists.
- Connect with configured password; models and projects populate.
- Start a conversation, receive streamed response, open conversation from history.
- In Memory, add a project, propose a fact, approve it, and preview context for a question.
- In Models, see correct configured/unconfigured status.
- In Observability, check counts update after refresh.
- On a narrow screen, open sidebar via menu icon and navigate.

## User profiles and sidebar connection (next iteration)

- Profiles are **workspace personas, not security accounts**. All profiles share the existing gateway password and database access; do not use them to isolate private data between independent users.
- Profiles have a name, preferred provider, visual theme and optional instructions for LLM answers.
- The frontend switches profile chat lists; new chats are tagged with `profile_id`. Previous chats migrate to the `default` profile without losing messages.
- Backend prevents posting new messages to a chat whose `profile_id` differs from the active one.
- Profile instructions are added as a system message for new LLM requests. They may be included in requests to cloud providers. Do not put confidential data or API keys in profile instructions.
- Password / Connect were moved from the header to the expandable **Połączenie Gateway** section in the left sidebar; credentials are not stored in localStorage.
- APIs: `GET /api/profiles`, `POST /api/profiles`, `PUT /api/profiles/{profile_id}`; `GET /api/chats?profile_id=...`; `POST /api/chat` accepts `profile_id`.
- New profiles currently do not support deletion; old projects and approved facts are shared across profiles. Fine-grained authorization and true multi-user accounts remain out of scope.

### Deployment

This modifies the SQLite schema additively on startup. Back up the DB before updating native LXC. Existing conversations remain and are associated with the default workspace profile.
