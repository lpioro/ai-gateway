# AI Gateway 1.0 — PI-LAB Workspace

## Available in main

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

## User profiles and sidebar connection (implemented)

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


## Profiles: typical workflow

1. Expand **Połączenie Gateway** in the left sidebar, enter the existing gateway password, and click **Połącz**.
2. Select **Zarządzaj profilami** and create a profile such as `Programista` or `Analityk`.
3. Define its name, preferred provider, theme and response instructions. Click **Zapisz profil**.
4. Pick the profile in the sidebar selector. Only its linked conversations appear in the history list.
5. New conversations will be assigned to that profile, and its instructions will accompany the question sent to the model.

All pre-existing conversations are assigned to the `default` profile on the first startup after upgrade. This is an additive SQLite migration, not a destructive reset.

### Important caveats

- **Not multi-user authentication:** anyone with the gateway password can switch profiles. Projects, facts and conversation read/delete endpoints are not protected by per-profile authorization; the filtered list is a UI convenience.
- Model preferences are not per-profile provider credentials. The API keys remain server-owned in the gateway environment configuration.
- Model selection depends on whether the preferred provider is configured and permitted by Local Only mode.
- The theme selection in browser settings and profile switching may override each other; profile selection applies its stored theme.
- Profile deletion is not implemented.
- No real RAG ingestion, provider wizard, secure credential vault, or detailed model traces exist yet.

### Deployment checklist

Back up the SQLite file **with the service stopped** before upgrading. Update the git checkout and rerun the native installer described in [LXC.md](LXC.md). Verify `/api/profiles`, switch between two profiles, and confirm that existing chats still appear in **Domyślny**. Use a controlled LAN or HTTPS reverse proxy; the shared-password mechanism is not sufficient for public access.

See [PROFILES.md](PROFILES.md) for API examples, data model and troubleshooting.
