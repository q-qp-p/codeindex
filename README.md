# codeindex

**Temporal code knowledge graph** with blast-radius impact scoring, semantic symbol search, and git-history-aware dependency analysis — for AI-assisted development.

Point it at any project — Python, JavaScript/TypeScript, Go, Ruby, Rust, Java, PHP, and more — and get:

- A persistent **SQLite graph store** at `<repo>/.codeindex/index.db` — incremental, queryable, temporal
- A `codeindex.json` dependency index written directly into your repo (preserved for backward compatibility)
- Per-file blast-radius scores (how many files break if this one changes), including **historical as-of queries**
- A `symbolindex.json` symbol map so AI can find any function/class without scanning every file
- **Hybrid semantic search** over symbols: natural-language queries fused with keyword + graph expansion
- **Git history backfill** — temporal graph from commit history without touching the working tree
- Ten ways to consume the data: CLI, markdown report, MCP server (10 tools), pre-commit hook, CLAUDE.md injection
- An interactive visualization UI (2D/3D graphs, dependency matrix, treemap)

No build step. No npm. Zero required runtime dependencies — SQLite is stdlib.

---

## Install

```bash
pip install codeindex
```

Or from source:

```bash
git clone https://github.com/scheidydude/codeindex
cd codeindex
pip install -e .
```

---

## Quickstart

```bash
# Build the dependency index (also writes to .codeindex/index.db)
codeindex analyze ./myapp

# Build the symbol index (where every function and class lives)
codeindex symbols ./myapp

# See blast radius for a file before touching it
codeindex impact src/auth.py

# Search symbols with natural language (no embedding endpoint needed — FTS fallback)
codeindex search "validate auth token"

# See what changed since a release tag
codeindex changed-since v1.2.0

# Launch the visualization UI
codeindex serve --viz --repo ./myapp
open http://localhost:8080
```

---

## Commands

### `codeindex analyze`

```bash
codeindex analyze [REPO_PATH] [--output PATH] [--watch]
```

Analyzes the repo and writes `codeindex.json` to the repo root. Detects 12+ languages automatically.

| Flag | Default | Description |
|------|---------|-------------|
| `REPO_PATH` | `.` | Path to repo root |
| `--output` | `<repo>/codeindex.json` | Override output path |
| `--watch` | off | Re-index on file changes (requires `watchdog`) |

---

### `codeindex symbols`

```bash
codeindex symbols [REPO_PATH] [--output PATH] [--inline] [--index PATH]
                  [--claude-md] [--claude-md-path PATH] [--all-symbols]
```

Builds a symbol index — a map of every function, class, struct, and type to its exact file and line number. Lets AI tools (and humans) find any symbol in one lookup instead of scanning the entire repo.

**Modes:**

| Flag | Description |
|------|-------------|
| _(none)_ | Write a standalone `symbolindex.json` |
| `--inline` | Embed symbols into each node in `codeindex.json` instead |
| `--claude-md` | Append a compressed symbol summary to `CLAUDE.md` |

Both `--inline` and `--claude-md` can be combined in a single run.

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `REPO_PATH` | `.` | Path to repo root |
| `--output` | `<repo>/symbolindex.json` | Output path (standalone mode) |
| `--index` | auto-discovered | Path to `codeindex.json` (for `--inline`) |
| `--claude-md-path` | `<repo>/CLAUDE.md` | Override CLAUDE.md path |
| `--all-symbols` | off | Include non-exported symbols in CLAUDE.md (default: exported only) |

**Examples:**

```bash
# Standalone symbol index
codeindex symbols ./myapp

# Embed into codeindex.json (one file for blast radius + symbols)
codeindex symbols ./myapp --inline

# Write CLAUDE.md summary so Claude Code loads symbols automatically
codeindex symbols ./myapp --claude-md

# All three at once
codeindex symbols ./myapp --inline --claude-md

# Re-generate when code changes
codeindex symbols ./myapp --inline --claude-md
```

**Why it matters:** Claude Code and other AI tools normally scan every file to find a function definition. With a symbol index, Claude can load one file, do an O(1) lookup, and open only the relevant file — cutting token usage 60–90% on symbol-location tasks.

**CLAUDE.md injection** is opt-in because it increases base context size on every prompt. Use it when symbol lookups are frequent in your workflow; skip it for simple tasks where the overhead outweighs the benefit.

---

### `codeindex impact`

```bash
codeindex impact FILE [--index PATH] [--out FILE] [--json] [--as-of REF]
```

Shows the blast-radius impact for a specific file: direct dependents, transitive dependents, blast score, and risk level.

```
Impact: src/auth.py
Blast Score: 8.5  (2 direct · 7 transitive)  [HIGH]

Direct dependents (2)
  src/api.py
  src/middleware.py

Transitive dependents (5 additional)
  src/main.py  ← src/api.py
  src/app.py   ← src/middleware.py
  ...

Risk: HIGH — affects 7/42 files (16.7% of codebase)
```

**Blast score formula:** `direct + (0.5 × transitive)`

| Flag | Description |
|------|-------------|
| `--index PATH` | Path to `codeindex.json` (auto-discovered if omitted) |
| `--out FILE` | Write a markdown report to this file |
| `--json` | Output raw JSON |
| `--as-of REF` | Compute blast radius at a historical commit/ref instead of HEAD |

---

### `codeindex search`

```bash
codeindex search QUERY [--k N] [--as-of REF] [--db PATH] [--json]
```

Hybrid semantic + keyword + graph symbol search. Finds relevant functions and classes without knowing their exact names.

**Retrieval signals fused with Reciprocal Rank Fusion (RRF):**
1. **Semantic KNN** — embedding similarity (requires `codeindex[semantic]` + a configured endpoint)
2. **FTS5 keyword** — full-text search over symbol names, signatures, and docstrings
3. **Graph expansion** — structurally adjacent symbols from dependent/dependency files

Degrades gracefully: if no embedding endpoint is configured, falls back to FTS + graph (no crash, no config needed).

```bash
# Keyword + graph search (no embedding setup required)
codeindex search "validate auth token"

# Full semantic search (requires CODEINDEX_EMBEDDING_* env vars)
CODEINDEX_EMBEDDING_ENDPOINT=http://localhost:11434 \
CODEINDEX_EMBEDDING_MODEL=nomic-embed-text \
CODEINDEX_EMBEDDING_DIMS=768 \
codeindex search "validate auth token"

# Historical search — symbols visible at a release tag
codeindex search "token validation" --as-of v1.2.0
```

| Flag | Default | Description |
|------|---------|-------------|
| `QUERY` | — | Natural-language or keyword query |
| `--k N` | `10` | Number of results to return |
| `--as-of REF` | HEAD | Restrict to symbols visible at this commit/ref |
| `--db PATH` | auto-discovered | Path to `.codeindex/index.db` |
| `--json` | off | Output raw JSON |

---

### `codeindex history`

```bash
codeindex history [REPO_PATH] [--since REF] [--max-commits N] [--json]
```

Backfills temporal graph data from git history — without any working-tree checkouts. Reads blobs via `git cat-file --batch` and stamps `first_seen_commit` / `last_seen_commit` on every file, edge, and symbol.

Run this once after initial setup to enable `--as-of` queries across the full history.

```bash
# Backfill up to 1000 commits (default)
codeindex history .

# Backfill only recent history
codeindex history . --since v1.0.0 --max-commits 200
```

| Flag | Default | Description |
|------|---------|-------------|
| `REPO_PATH` | `.` | Path to repo root |
| `--since REF` | — | Only process commits after this date/ref |
| `--max-commits N` | `1000` | Maximum commits to process |
| `--json` | off | Output summary as JSON |

---

### `codeindex changed-since`

```bash
codeindex changed-since REF [--repo PATH] [--db PATH] [--json]
```

Lists files and dependency edges added or removed since a commit, branch, or tag.

```
$ codeindex changed-since v1.2.0
Changes since v1.2.0:

  Added files (2):
    + src/payments/stripe.py
    + src/payments/webhook.py

  Removed edges (1):
    - src/api.py → src/auth_v1.py  [imports]
```

| Flag | Default | Description |
|------|---------|-------------|
| `REF` | — | Commit hash, branch, or tag to compare against |
| `--repo PATH` | `.` | Repo root (for git operations) |
| `--db PATH` | auto-discovered | Path to `.codeindex/index.db` |
| `--json` | off | Output raw JSON |

---

### `codeindex db`

```bash
codeindex db status [--db PATH] [--json]
codeindex db migrate [--db PATH]
```

Manages the SQLite store at `<repo>/.codeindex/index.db`.

```
$ codeindex db status
schema_version      : 2
repo_root           : /Users/alice/myapp
last_indexed_commit : a3f2e1c8
active_files        : 142
active_edges        : 387
active_symbols      : 1204
embedding_model     : nomic-embed-text
embedding_dims      : 768
vec_symbols         : enabled
```

`db migrate` applies any pending schema migrations automatically (also runs on every `codeindex analyze`).

---

### `codeindex serve`

```bash
codeindex serve --viz [--repo PATH] [--port PORT] [--watch]
codeindex serve --mcp
```

`--viz` launches an interactive visualization UI in your browser (5 modes: 2D force graph, 3D network, dependency matrix, treemap, infrastructure graph).

`--mcp` starts a stdio MCP server that exposes codeindex tools directly to Claude and other MCP clients.

**MCP tools:**

| Tool | Description |
|------|-------------|
| `analyze_repo` | Build or refresh the dependency index |
| `get_impact` | Blast-radius report for a file |
| `get_dependencies` | imports + imported-by for a file |
| `get_high_blast_files` | All files above a blast score threshold |
| `build_symbol_index` | Build or refresh the symbol index |
| `lookup_symbol` | Find where any function/class/type is defined (file + line) |
| `semantic_search` | Hybrid semantic + keyword + graph symbol search; degrades gracefully without embeddings |
| `temporal_impact` | Blast-radius at a historical commit/ref (`as_of` parameter) |
| `graph_query` | k-hop dependency neighborhood of a file (`dependents`/`dependencies`/`both`) |
| `changed_since` | Files and edges added or removed since a commit/ref |

**Claude Code MCP config** (`.claude/settings.json`):

```json
{
  "mcpServers": {
    "codeindex": {
      "command": "codeindex",
      "args": ["serve", "--mcp"]
    }
  }
}
```

---

### `codeindex lookup`

```bash
codeindex lookup SYMBOL [--index PATH] [--json]
```

Finds where a function, class, struct, or other symbol is defined. O(1) lookup against `symbolindex.json` — no file scanning.

```
$ codeindex lookup compute_blast_radius
codeindex/impact.py:6  (function)

$ codeindex lookup AuthService
src/auth.py:44  (class)  methods: login, logout, refresh
```

| Flag | Description |
|------|-------------|
| `--index PATH` | Path to `symbolindex.json` (auto-discovered if omitted) |
| `--json` | Output raw JSON |

---

### `codeindex dependencies`

```bash
codeindex dependencies FILE [--index PATH] [--json]
```

Shows what a file imports and what imports it, plus its blast score.

```
$ codeindex dependencies src/auth.py
File: src/auth.py  (blast score: 8.5)

Imports (3):
  src/db.py
  src/config.py
  src/utils.py

Imported by (2):
  src/api.py
  src/middleware.py
```

| Flag | Description |
|------|-------------|
| `--index PATH` | Path to `codeindex.json` (auto-discovered if omitted) |
| `--json` | Output raw JSON |

---

### `codeindex high-blast`

```bash
codeindex high-blast [--threshold N] [--index PATH] [--json]
```

Lists all files whose blast score exceeds the threshold, sorted by score descending. Useful for identifying the riskiest files before a refactor.

```
$ codeindex high-blast --threshold 5
Files with blast score ≥ 5.0  (3 found)

  13.0  src/db.py          (12d / 2t)
   8.5  src/auth.py        (3d / 7t)
   5.5  src/config.py      (5d / 1t)
```

`d` = direct dependents · `t` = transitive dependents

| Flag | Default | Description |
|------|---------|-------------|
| `--threshold N` | `5` | Minimum blast score to include |
| `--index PATH` | auto-discovered | Path to `codeindex.json` |
| `--json` | off | Output raw JSON |

---

### `codeindex install-hook`

```bash
codeindex install-hook [--repo PATH] [--threshold N] [--strict] [--remove]
```

Installs a git pre-commit hook that warns when staged files exceed the blast score threshold.

| Flag | Default | Description |
|------|---------|-------------|
| `--threshold N` | `10` | Blast score above which to warn |
| `--strict` | off | Block the commit instead of just warning |
| `--remove` | — | Uninstall the hook |

---

## Using codeindex in another repo with Claude

Three workflows, ordered by automation level.

### Workflow 1 — MCP server (recommended for active coding)

Claude gets symbol lookup, dependency, and impact tools it calls automatically. No extra prompting needed.

**One-time setup:**
```bash
cd /your/other/repo
codeindex analyze .
codeindex symbols .
```

Register the MCP server with Claude Code using `claude mcp add`. Use `--scope project` to limit it to this repo, or `--scope global` to use it everywhere:

```bash
# Project-scoped (recommended — stored in .claude/settings.json)
claude mcp add --scope project codeindex -- /path/to/codeindex serve --mcp

# Global (available in all repos)
claude mcp add --scope global codeindex -- /path/to/codeindex serve --mcp
```

Find the full path to your codeindex binary with `which codeindex`, then substitute it above.

```bash
# Example with conda install
claude mcp add --scope project codeindex -- /opt/homebrew/Caskroom/miniforge/base/bin/codeindex serve --mcp
```

Verify it registered:
```bash
claude mcp list
```

> **Note:** Do not use `"command": "codeindex"` with a bare name — Claude Code does not inherit your shell PATH, so the binary won't be found unless you use the absolute path.

Claude now has all 10 MCP tools available in every session. When it needs to find `processPayment`, it calls `lookup_symbol("processPayment")` and gets `src/billing.py:142` back in one shot — no file scanning. When it needs to find code that validates auth tokens without knowing the exact name, it calls `semantic_search("validate auth token")`.

**Keep the index fresh:**
```bash
# Auto-rebuild on file changes (leave running in a terminal)
codeindex symbols . --watch
```

---

### Workflow 2 — CLAUDE.md injection (best for repos you revisit often)

Symbol table is embedded in `CLAUDE.md` so it loads into every session automatically — no tool call needed at all.

```bash
cd /your/other/repo
codeindex symbols . --claude-md
```

This upserts a `symbolindex` code fence into `CLAUDE.md`. Every Claude Code session in that repo loads it at startup. Claude can answer "where is `X` defined?" from context alone with zero tool calls.

**Tradeoff:** adds ~500–2000 tokens to every prompt depending on repo size. Worth it for repos where symbol lookups are frequent; skip it for repos where you mostly write new code.

**Keep it fresh:**
```bash
# Re-run after significant refactors
codeindex analyze . && codeindex symbols . --claude-md
```

---

### Workflow 3 — Hybrid (large repos)

For large repos where the `--claude-md` section would be too large, use the MCP server for lookups and add a short hint to `CLAUDE.md` so Claude reaches for the tool first:

```bash
codeindex analyze .
codeindex symbols .
```

Then add to `CLAUDE.md`:
```markdown
## Codeindex
Symbol index: `symbolindex.json` — use the `lookup_symbol` MCP tool before grepping for any function or class.
Dependency index: `codeindex.json` — use `get_impact` before modifying high-blast files.
```

This costs almost no tokens but primes Claude to use the index rather than defaulting to grep.

---

### CLI quick reference for human use

The same data available via MCP is also accessible directly from the terminal:

```bash
# Find where a symbol is defined
codeindex lookup MyClassName
codeindex lookup process_payment --json

# Show what a file imports and what depends on it
codeindex dependencies src/auth.py

# List the riskiest files to change
codeindex high-blast --threshold 5

# Blast-radius report before touching a file
codeindex impact src/auth.py
```

---

### Which workflow to pick

| Situation | Workflow |
|-----------|----------|
| Daily driver repo, active feature work | MCP server |
| Medium repo, frequent symbol lookups | CLAUDE.md injection |
| Large repo (1000+ files) | MCP server + short CLAUDE.md hint |
| Quick one-off in an unfamiliar repo | `codeindex symbols . --claude-md`, delete after |
| Terminal / scripting use | CLI commands (`lookup`, `dependencies`, `high-blast`) |

---

## Supported Languages

| Language | Dependency analysis | Symbol extraction |
|----------|--------------------|--------------------|
| Python | AST imports, type detection | Functions, classes, methods (AST-precise) |
| JavaScript / TypeScript | ES modules, `require()`, framework detection | Exported functions, classes, types, enums, consts |
| Vue | SFC `<script>` imports | Exported symbols from `<script>` block |
| Go | Package-level nodes, `import` blocks | Functions, structs, interfaces (exported flag) |
| Ruby | `require`, `require_relative`, `autoload` | Classes, modules, methods |
| Rust | `mod`, `use crate::` | `pub fn`, structs, enums, traits |
| Java / Kotlin | FQN imports, wildcard imports | Classes, interfaces, methods |
| PHP | PSR-4 namespace resolution | Classes, interfaces, functions |
| CSS / SCSS / Less | `@import`, `@use`, `@forward` | — |
| Docker | Services, `depends_on` edges | — |
| CI/CD | GitHub Actions + GitLab CI jobs, `needs:` edges | — |
| SQL / Prisma | Tables/models, foreign key edges | — |

---

## Output schemas

### `codeindex.json`

```json
{
  "meta": {
    "root": "myapp/",
    "total_files": 60,
    "total_loc": 4085,
    "languages": ["python", "javascript"]
  },
  "nodes": [
    {
      "id": "src/auth.py",
      "type": "module",
      "language": "python",
      "layer": "backend",
      "loc": 142,
      "imports": ["src/db.py"],
      "imported_by": ["src/api.py", "src/middleware.py"],
      "direct_dependents": 2,
      "transitive_dependents": 7,
      "blast_score": 5.5,
      "symbols": [
        { "name": "verify_token", "line": 18, "kind": "function", "exported": true },
        { "name": "AuthService",  "line": 44, "kind": "class",    "exported": true,
          "methods": ["login", "logout", "refresh"] }
      ]
    }
  ],
  "links": [
    { "source": "src/api.py", "target": "src/auth.py", "weight": 1, "kind": "imports" }
  ]
}
```

The `symbols` field is only present when `codeindex symbols --inline` has been run.

---

### `symbolindex.json`

```json
{
  "meta": {
    "generated": "2026-05-21",
    "repo": "myapp/",
    "total_symbols": 312
  },
  "symbols": {
    "verify_token": [
      {
        "file": "src/auth.py",
        "line": 18,
        "kind": "function",
        "exported": true,
        "doc": "Verify a JWT and return the decoded payload."
      }
    ],
    "AuthService": [
      {
        "file": "src/auth.py",
        "line": 44,
        "kind": "class",
        "exported": true,
        "methods": ["login", "logout", "refresh"]
      }
    ]
  },
  "file_symbols": {
    "src/auth.py": [
      { "name": "verify_token", "line": 18, "kind": "function", "exported": true },
      { "name": "AuthService",  "line": 44, "kind": "class",    "exported": true,
        "methods": ["login", "logout", "refresh"] }
    ]
  }
}
```

**Lookup patterns:**

- *"Where is `verify_token` defined?"* → `symbols["verify_token"][0].file` + `.line` — O(1)
- *"What symbols live in `src/auth.py`?"* → `file_symbols["src/auth.py"]` — O(1)
- *"What's the blast radius of changing `verify_token`?"* → cross-reference `codeindex.json` via the file

---

### CLAUDE.md symbol section

When `--claude-md` is used, a compact section is upserted into `CLAUDE.md` bounded by HTML comment markers so re-runs update in place:

```
<!-- codeindex-symbols-start -->
## Symbol Index
_Generated by codeindex. Update: `codeindex symbols --claude-md`_

```symbolindex
src/auth.py: verify_token:fn:18 AuthService:cls:44[login,logout,refresh]
src/db.py: connect:fn:12 query:fn:28 close:fn:55
```
<!-- codeindex-symbols-end -->
```

Format per symbol: `name:kind_abbr:line[methods...]`
Kind abbreviations: `fn` function · `cls` class · `st` struct · `en` enum · `tr` trait · `if` interface · `ty` type · `co` const

---

## AI workflow comparison

| Task | Without codeindex | With symbolindex.json |
|------|-------------------|----------------------|
| Find where `process_payment` is defined | Grep / scan ~200 files | Load 1 file, O(1) lookup |
| Understand blast radius of a change | Manual tracing | `codeindex impact <file>` |
| Load only relevant context | Full repo scan | File + line from symbol map |
| Estimated token savings | baseline | **60–90% on symbol tasks** |

---

## Optional dependencies

| Package | Purpose | Install |
|---------|---------|---------|
| `sqlite-vec` | Semantic vector search in `codeindex search` and `semantic_search` MCP tool | `pip install 'codeindex[semantic]'` |
| `watchdog` | `--watch` file change detection | `pip install 'codeindex[watch]'` |
| `PyYAML` | Better Docker Compose / CI YAML parsing | `pip install 'codeindex[yaml]'` |
| `tomli` | Rust `Cargo.toml` on Python < 3.11 | `pip install 'codeindex[toml]'` |

### Semantic search configuration

Semantic search requires a self-hosted embedding endpoint (Ollama, LM Studio, llama.cpp server, or any OpenAI-compatible `/v1/embeddings` API) and the `sqlite-vec` extension.

```bash
pip install 'codeindex[semantic]'

# Set env vars (add to your shell profile or .env)
export CODEINDEX_EMBEDDING_ENDPOINT=http://localhost:11434
export CODEINDEX_EMBEDDING_MODEL=nomic-embed-text
export CODEINDEX_EMBEDDING_DIMS=768

# Re-index to generate embeddings
codeindex analyze ./myapp

# Search
codeindex search "validate JWT token"
```

Without these env vars, `codeindex search` and the `semantic_search` MCP tool fall back to FTS5 keyword + graph search — no crash, no config required.

---

## Requirements

- Python 3.9+
- A modern browser (for `--viz` mode)

---

## License

Apache 2.0 — free to use and build on; attribution required in derivative works and documentation. Copyright 2026 David Scheiderman.
