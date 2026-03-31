# Repo Viz Explorer

An interactive visualization tool for exploring repository structure across **12+ languages**. Point it at any project — Python, JavaScript/TypeScript, Go, Ruby, Rust, Java, PHP, and more — and get live, multi-mode dependency graphs rendered in your browser. No build step, no npm, no third-party Python packages required.

![Languages](https://img.shields.io/badge/languages-12%2B-00d4ff?style=flat-square) ![Views](https://img.shields.io/badge/views-5%20modes-a855f7?style=flat-square) ![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue?style=flat-square) ![Zero required deps](https://img.shields.io/badge/deps-stdlib%20only-10b981?style=flat-square)

---

## Features

- **5 visualization modes** — 2D force graph, 3D network, dependency matrix, treemap, and infrastructure graph
- **12+ languages** — Python, JavaScript, TypeScript, Vue, CSS/SCSS, Go, Ruby, Rust, Java, Kotlin, PHP, SQL, Prisma, Docker, GitHub Actions, GitLab CI
- **Framework detection** — React, Vue, Next.js, Nuxt, Angular, Svelte, Rails, Laravel, Spring, and more
- **Semantic node types** — module, component, hook, route, store, style, service, pipeline, database
- **Cross-language API edges** — detects FastAPI/Flask/Django routes called by frontend `fetch`/`axios` — shown as orange edges
- **Layer filter** — show only Frontend, Backend, or Infrastructure nodes in one click
- **Monorepo support** — detects pnpm workspaces, npm/yarn workspaces, Lerna, Nx, Turborepo; tags nodes with their package name
- **Infrastructure graph** — dedicated tab showing Docker services, CI/CD jobs, and database tables as a dependency graph
- **Language filter** — toggle individual languages on/off in the force graph
- **Cycle detection** — circular import pairs highlighted in red automatically
- **Search & filter** — type to highlight a module and its neighbors
- **Node detail panel** — click any node to see type, language, layer, package, LOC, imports, and imported-by
- **Cluster mode** — group nodes by directory in the force graph
- **Export** — download the 2D graph as SVG or the 3D view as PNG
- **Auto-refresh** — `--watch` mode re-analyzes on every file change
- **Keyboard shortcuts** — `1`–`5` switch tabs, `F` focuses search, `R` refreshes

---

## Quickstart

```bash
git clone <this-repo>
cd repo-viz-explorer

# Analyze any project and serve the UI
python server.py --repo /path/to/your/project

# Open in browser
open http://localhost:8080
```

No `pip install`, no npm, no build step.

---

## Supported Languages

| Language | Detection Signal | What's Analyzed |
|----------|-----------------|-----------------|
| Python | `*.py` files | AST imports, type detection |
| JavaScript / TypeScript | `package.json` or `*.js/ts/jsx/tsx` | ES module imports, `require()` |
| Vue | `*.vue` files | `<script>` block imports, SFC detection |
| CSS / SCSS / Less | `*.css/scss/sass/less` | `@import`, `@use`, `@forward` |
| Go | `go.mod` or `*.go` | Package-level nodes, `import` blocks |
| Ruby | `Gemfile` or `*.rb` | `require`, `require_relative`, `autoload` |
| Rust | `Cargo.toml` or `*.rs` | `mod`, `use crate::` |
| Java / Kotlin | `*.java/kt` | FQN imports, wildcard imports |
| PHP | `composer.json` or `*.php` | PSR-4 namespace resolution, `use` |
| Docker | `docker-compose.yml` / `Dockerfile` | Services, `depends_on` edges |
| CI/CD | `.github/workflows/` / `.gitlab-ci.yml` | Jobs, `needs:` dependency edges |
| SQL / Prisma | `*.sql` / `*.prisma` | Tables/models, foreign key edges |

---

## Usage

### `server.py`

```
python server.py [--repo PATH] [--port PORT] [--watch]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--repo` | `.` | Path to the project to analyze |
| `--port` | `8080` | Port to serve on |
| `--watch` | off | Auto-re-analyze when files change (requires `watchdog`) |

```bash
# With file watching
pip install watchdog
python server.py --repo ./myapp --watch

# Via environment variable
REPO_PATH=./myapp python server.py
```

### `analyze_repo.py`

Run the analyzer standalone to produce `repo_graph.json` without starting the server:

```bash
python analyze_repo.py ./myapp
# → writes repo_graph.json

python analyze_repo.py ./myapp --output /tmp/graph.json
```

---

## Output format

`analyze_repo.py` emits a single JSON file:

```json
{
  "meta": {
    "root": "myapp/",
    "total_files": 60,
    "total_loc": 4085,
    "languages": ["python", "javascript", "css", "docker"],
    "apiLinks": 2
  },
  "nodes": [
    {
      "id": "frontend/src/services/authService.js",
      "type": "module",
      "language": "javascript",
      "layer": "frontend",
      "package": "@myapp/frontend",
      "loc": 42,
      "group": 3
    }
  ],
  "links": [
    { "source": "frontend/src/services/authService.js", "target": "backend/routers/auth.py", "weight": 1, "kind": "api-call" }
  ]
}
```

### Node fields

| Field | Values | Meaning |
|-------|--------|---------|
| `type` | `module`, `component`, `hook`, `route`, `store`, `style`, `service`, `pipeline`, `database`, `import`, `config` | Semantic node type |
| `language` | `python`, `javascript`, `typescript`, `vue`, `css`, `go`, `ruby`, `rust`, `java`, `kotlin`, `php`, … | Source language |
| `layer` | `frontend`, `backend`, `infrastructure` | Architectural layer |
| `package` | string or `""` | Workspace/monorepo package name |
| `framework` | `react`, `vue`, `next`, `rails`, … or `null` | Detected framework |

### Link kinds

| Kind | Color | Meaning |
|------|-------|---------|
| `imports` | cyan | Standard import / require |
| `renders` | pink | Component renders component |
| `styles` | teal | File imports a stylesheet |
| `depends` | sky blue | Infrastructure dependency |
| `api-call` | orange | Frontend HTTP call → backend route |
| *(cycle)* | red | Circular import |

---

## Visualization modes

### 1 — 2D Force Graph
Force-directed layout using D3. Drag nodes, scroll to zoom. Edges colored by kind (see table above).

- **Layer Filter** (sidebar) — show only Frontend, Backend, or Infrastructure nodes
- **Language filter** (sidebar) — toggle individual languages on/off
- **CLUSTER** toggle — pulls nodes toward their directory centroid
- **Search bar** — highlights matching nodes and their neighbors
- Click a node — opens detail panel showing type, language, layer, package, LOC, imports, imported-by
- **↓ SVG** — exports current view

### 2 — 3D Network
Three.js sphere layout. Drag to orbit, scroll to zoom, right-drag to pan.

- **↓ PNG** — exports canvas

### 3 — Dependency Matrix
Grid showing import relationships. Cell intensity encodes weight; sort by name, connections, or LOC.

### 4 — Treemap
Area-proportional repo structure. Click a group to zoom in; breadcrumb trail to navigate back.

### 5 — Infrastructure
Dedicated force graph showing only `service`, `pipeline`, and `database` nodes with their dependency edges. Useful for understanding Docker, CI, and schema relationships in isolation.

---

## Keyboard shortcuts

| Key | Action |
|-----|--------|
| `1` – `5` | Switch tabs |
| `F` | Focus the search bar |
| `R` | Refresh graph data |
| `Esc` | Clear search / selection |

---

## Architecture

```
repo-viz-explorer/
├── repo-viz-explorer.html     # Single-file frontend (D3 + Three.js, no build step)
├── analyze_repo.py            # Dispatcher: detects languages, delegates to plugins
├── server.py                  # Minimal HTTP server (stdlib only)
├── repo_graph.json            # Generated output
└── analyzers/
    ├── python_analyzer.py     # AST-based Python analysis
    ├── js_analyzer.py         # JS/TS/Vue imports + framework detection
    ├── css_analyzer.py        # CSS/SCSS/Less @import edges
    ├── go_analyzer.py         # Go package-level nodes
    ├── ruby_analyzer.py       # Ruby require/autoload
    ├── rust_analyzer.py       # Rust mod/use crate
    ├── java_analyzer.py       # Java/Kotlin FQN imports
    ├── php_analyzer.py        # PHP PSR-4 namespace resolution
    ├── docker_analyzer.py     # Docker Compose + Dockerfile
    ├── ci_analyzer.py         # GitHub Actions + GitLab CI
    ├── schema_analyzer.py     # SQL + Prisma schema
    ├── cross_lang_analyzer.py # Cross-language API boundary detection
    └── monorepo_analyzer.py   # Workspace / monorepo package detection
```

Each analyzer implements `analyze(root, group_map) → (nodes, ext_nodes, links_map, meta)`. Adding a new language means adding one file to `analyzers/` and one entry in the `_ANALYZERS` table in `analyze_repo.py`.

---

## Optional dependencies

| Package | Purpose | Install |
|---------|---------|---------|
| `watchdog` | `--watch` file change detection | `pip install watchdog` |
| `PyYAML` | Better Docker Compose / CI YAML parsing | `pip install pyyaml` |
| `tomli` | Rust `Cargo.toml` parsing on Python < 3.11 | `pip install tomli` |

All three are optional — the tool works without them, falling back to regex-based parsing where needed.

---

## Requirements

- Python 3.9+
- A modern browser (Chrome, Firefox, Safari, Edge)
- Internet access for CDN fonts and libraries (D3, Three.js) — or swap the CDN links for local copies

---

## License

MIT
