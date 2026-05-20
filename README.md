# codeindex

Repo dependency analyzer with **blast-radius impact scoring** for AI-assisted development.

Point it at any project — Python, JavaScript/TypeScript, Go, Ruby, Rust, Java, PHP, and more — and get:

- A `codeindex.json` dependency index written directly into your repo
- Per-file blast-radius scores (how many files break if this one changes)
- Four ways to consume the data: CLI, markdown report, MCP server, pre-commit hook
- An interactive visualization UI (2D/3D graphs, dependency matrix, treemap)

No build step. No npm. Pure Python stdlib — zero required dependencies.

---

## Install

```bash
pip install codeindex
```

Or from source:

```bash
git clone https://github.com/scheidydudes/codeindex
cd codeindex
pip install -e .
```

---

## Quickstart

```bash
# Build the index (writes codeindex.json into your repo)
codeindex analyze ./myapp

# See blast radius for a file before touching it
codeindex impact src/auth.py

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

### `codeindex impact`

```bash
codeindex impact FILE [--index PATH] [--out FILE] [--json]
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
| `analyze_repo` | Build or refresh the index |
| `get_impact` | Blast-radius report for a file |
| `get_dependencies` | imports + imported-by for a file |
| `get_high_blast_files` | All files above a blast score threshold |

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

## Supported Languages

| Language | What's analyzed |
|----------|----------------|
| Python | AST imports, type detection |
| JavaScript / TypeScript | ES modules, `require()`, framework detection |
| Vue | SFC `<script>` imports |
| CSS / SCSS / Less | `@import`, `@use`, `@forward` |
| Go | Package-level nodes, `import` blocks |
| Ruby | `require`, `require_relative`, `autoload` |
| Rust | `mod`, `use crate::` |
| Java / Kotlin | FQN imports, wildcard imports |
| PHP | PSR-4 namespace resolution |
| Docker | Services, `depends_on` edges |
| CI/CD | GitHub Actions + GitLab CI jobs, `needs:` edges |
| SQL / Prisma | Tables/models, foreign key edges |

---

## `codeindex.json` schema

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
      "blast_score": 5.5
    }
  ],
  "links": [
    {
      "source": "src/api.py",
      "target": "src/auth.py",
      "weight": 1,
      "kind": "imports"
    }
  ]
}
```

---

## Optional dependencies

| Package | Purpose | Install |
|---------|---------|---------|
| `watchdog` | `--watch` file change detection | `pip install 'codeindex[watch]'` |
| `PyYAML` | Better Docker Compose / CI YAML parsing | `pip install 'codeindex[yaml]'` |
| `tomli` | Rust `Cargo.toml` on Python < 3.11 | `pip install 'codeindex[toml]'` |

---

## Requirements

- Python 3.9+
- A modern browser (for `--viz` mode)

---

## License

MIT
