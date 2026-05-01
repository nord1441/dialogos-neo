# dialogos-neo

A profile-based LLM chat web app. **The filesystem is the source of truth** —
each chat profile is a directory you can SSH into and edit with vim. The
server reads/writes Markdown history files, proxies to LLM APIs, and
streams responses back via SSE.

```
profiles/
├── coding-assistant/
│   ├── profile.toml      # model + behavior config
│   ├── system.md         # system prompt
│   └── history.md        # the conversation, in plain Markdown
└── journal/
    ├── profile.toml      # history_strategy = "daily"
    ├── system.md
    └── history/
        ├── 2026-04-30.md
        └── 2026-05-01.md
```

Profile = URL. `/p/coding-assistant` is its own page, addable to a phone
home screen as a PWA.

## Why

- **`grep`-able history.** Search across years of conversations with `rg`.
- **No DB, no migrations.** Reload restores state from files.
- **HTTP for automation.** `cron` can POST a "review your day" prompt nightly.
- **Per-profile system prompts and models.** Spin up new "apps" by `mkdir`.

## Quick start

```bash
pip install -e .
export PROFILES_ROOT=$PWD/examples/profiles
export API_KEY_ANTHROPIC_MAIN=sk-ant-...
export API_TOKEN=$(openssl rand -hex 32)   # for /api/* automation
chatapp serve
# open http://127.0.0.1:8080
```

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `PROFILES_ROOT` | `./profiles` | directory holding all profile dirs |
| `KEYS_FILE` | unset | optional YAML keystore (mode 0600) |
| `API_KEY_<REF>` | unset | per-key env var; `key_ref="anthropic_main"` → `API_KEY_ANTHROPIC_MAIN` |
| `API_TOKEN` | unset | bearer token required for all `/api/*` routes |
| `LISTEN_ADDR` | `127.0.0.1:8080` | host:port |
| `LOG_LEVEL` | `info` | passed through to uvicorn |

The keystore lookup is case-insensitive on the ref.

## Profile config (`profile.toml`)

```toml
[meta]
display_name = "Coding Assistant"
icon = "🛠"

[model]
provider = "anthropic"      # anthropic | openai | local
name = "claude-opus-4-7"
temperature = 1.0
max_tokens = 4096
top_p = 1.0
# endpoint = "http://localhost:8080/v1/chat/completions"  # for local

[behavior]
history_strategy = "single" # single | daily | session
auto_save = true
session_gap_hours = 6.0     # session strategy: gap before splitting
timezone = "local"          # local | utc

[api]
key_ref = "anthropic_main"

[ui]
markdown_render = true
code_highlight = true
```

`system.md` is the system prompt — pure Markdown, no front-matter.

## History format

```markdown
## user
What does git rebase do?

## assistant
It rewrites commits onto a new base...
```

Only lines that exactly match `## user`, `## assistant`, or `## system`
(no trailing words) split turns. The body can freely contain `## something`
headings — the parser does not get confused.

## HTTP API

Browser pages:

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | profile list |
| GET | `/p/{slug}` | conversation view (current history) |
| GET | `/p/{slug}/history/{name}` | view an older history file |
| POST | `/p/{slug}/messages` | send a message, SSE stream back |
| POST | `/p/{slug}/sessions` | create a new session file (session strategy) |
| GET | `/p/{slug}/manifest.json` | per-profile PWA manifest |

JSON automation API (requires `Authorization: Bearer $API_TOKEN`):

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/profiles` | list profiles |
| GET | `/api/profiles/{slug}/history?name=...` | parsed messages |
| POST | `/api/profiles/{slug}/messages` | send + (optionally) wait for response |

```bash
curl -X POST -H "Authorization: Bearer $API_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"content":"今日の振り返りを促してください"}' \
     http://127.0.0.1:8080/api/profiles/journal/messages
```

## Operations

- **Locking.** Each profile has a `.lock` file created with `O_EXCL`.
  Concurrent POSTs to the same profile get a 409.
- **Crash safety.** The user message is appended *before* the LLM call. The
  assistant response is buffered and appended on completion (or on error
  with an `[error: ...]` marker). If the lock can't be re-acquired, the
  partial response is dropped into a `*.pending` sidecar.
- **Disconnect safety.** If the SSE client disconnects, the server keeps
  consuming the upstream so the assistant turn still lands in `history.md`.
  Refresh the page to see it.
- **Permissions.** `chmod 0700 profiles/` is recommended.

## Development

```bash
pip install -e '.[dev]'
pytest
```

The repo includes a small SSE client (`static/chatapp-sse.js`) that doesn't
depend on htmx — `static/htmx.min.js` is a placeholder you can replace with
the real htmx build if you want its declarative attributes elsewhere.

## Future

- Image attachments (Anthropic image content blocks)
- OpenAI / local provider polish (basic plumbing is already in place)
- PWA icon generation from emoji
- Auto-summarization for long histories
