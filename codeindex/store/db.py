# Copyright 2026 David Scheiderman
# Licensed under the Apache License, Version 2.0
"""SQLite-backed persistent store for codeindex graph data.

Dependency rule: this module must not import from codeindex.graph or
codeindex.semantic. The dependency arrow points only upward into this layer.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "1"

_DDL = """
CREATE TABLE IF NOT EXISTS index_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS commits (
    hash         TEXT PRIMARY KEY,
    authored_at  TEXT,
    committed_at TEXT,
    author       TEXT,
    message      TEXT,
    parent_hash  TEXT
);

CREATE TABLE IF NOT EXISTS files (
    id                    INTEGER PRIMARY KEY,
    path                  TEXT NOT NULL,
    node_type             TEXT DEFAULT 'module',
    language              TEXT,
    layer                 TEXT,
    size                  INTEGER,
    loc                   INTEGER,
    node_group            INTEGER DEFAULT 0,
    imports_count         INTEGER DEFAULT 0,
    package               TEXT,
    content_hash          TEXT,
    blast_score           REAL DEFAULT 0.0,
    direct_dependents     INTEGER DEFAULT 0,
    transitive_dependents INTEGER DEFAULT 0,
    active                INTEGER NOT NULL DEFAULT 1,
    first_seen_commit     TEXT,
    last_seen_commit      TEXT,
    first_seen_at         TEXT,
    last_seen_at          TEXT,
    UNIQUE (path)
);

CREATE TABLE IF NOT EXISTS edges (
    id                INTEGER PRIMARY KEY,
    source_file_id    INTEGER NOT NULL REFERENCES files(id),
    target_file_id    INTEGER NOT NULL REFERENCES files(id),
    kind              TEXT NOT NULL,
    weight            REAL DEFAULT 1,
    active            INTEGER NOT NULL DEFAULT 1,
    first_seen_commit TEXT,
    last_seen_commit  TEXT,
    first_seen_at     TEXT,
    last_seen_at      TEXT,
    UNIQUE (source_file_id, target_file_id, kind)
);

CREATE TABLE IF NOT EXISTS symbols (
    id                INTEGER PRIMARY KEY,
    file_id           INTEGER NOT NULL REFERENCES files(id),
    name              TEXT NOT NULL,
    kind              TEXT,
    line              INTEGER,
    exported          INTEGER DEFAULT 0,
    signature         TEXT,
    doc               TEXT,
    active            INTEGER NOT NULL DEFAULT 1,
    first_seen_commit TEXT,
    last_seen_commit  TEXT,
    first_seen_at     TEXT,
    last_seen_at      TEXT
);

CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_file_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_file_id);
CREATE INDEX IF NOT EXISTS idx_symbols_name  ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_file  ON symbols(file_id);
CREATE INDEX IF NOT EXISTS idx_files_active  ON files(active);
"""

# FTS is created separately because executescript cannot mix DDL and virtual tables
# on all SQLite builds.
_FTS_DDL = """
CREATE VIRTUAL TABLE IF NOT EXISTS symbols_fts USING fts5(
    name, doc, signature
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    """Persistent graph store backed by SQLite.

    Opens (or creates) the database at *db_path*, applies the schema, and
    exposes upsert / export / status operations.  All writes are transactional.
    """

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._apply_schema()

    # ── schema ────────────────────────────────────────────────────────────────

    def _apply_schema(self) -> None:
        self._conn.executescript(_DDL)
        try:
            self._conn.executescript(_FTS_DDL)
        except sqlite3.OperationalError:
            # FTS5 not available on this SQLite build — degraded gracefully.
            pass
        existing = self.get_meta("schema_version")
        if existing is None:
            self.set_meta("schema_version", SCHEMA_VERSION)
        self._conn.commit()

    # ── meta ──────────────────────────────────────────────────────────────────

    def get_meta(self, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM index_meta WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else None

    def set_meta(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO index_meta(key, value) VALUES (?, ?)",
            (key, value),
        )

    # ── sync ──────────────────────────────────────────────────────────────────

    def sync(
        self,
        data: dict,
        commit: str | None = None,
        changed_paths: set | None = None,
    ) -> None:
        """Upsert all nodes/edges from a fully-enriched graph dict.

        *changed_paths* is informational: when provided it is logged so callers
        can assert that only the expected change set was processed.  The full
        graph is always written because Phase-1 parsers scan the whole repo;
        per-file parsing is a future optimisation.
        """
        now = _now()
        seen_file_ids: list[int] = []
        node_id_map: dict[str, int] = {}  # path -> rowid

        for node in data["nodes"]:
            path = node["id"]
            imports = node.get("imports", [])
            imports_count = len(imports) if isinstance(imports, list) else int(imports or 0)

            row = self._conn.execute(
                "SELECT id FROM files WHERE path = ?", (path,)
            ).fetchone()

            if row:
                fid = row[0]
                self._conn.execute(
                    """UPDATE files SET
                        node_type=?, language=?, layer=?, size=?, loc=?,
                        node_group=?, imports_count=?, package=?, content_hash=?,
                        blast_score=?, direct_dependents=?, transitive_dependents=?,
                        active=1, last_seen_commit=?, last_seen_at=?
                       WHERE id=?""",
                    (
                        node.get("type", "module"),
                        node.get("language"),
                        node.get("layer"),
                        node.get("size"),
                        node.get("loc"),
                        node.get("group", 0),
                        imports_count,
                        node.get("package"),
                        node.get("content_hash"),
                        node.get("blast_score", 0.0),
                        node.get("direct_dependents", 0),
                        node.get("transitive_dependents", 0),
                        commit,
                        now,
                        fid,
                    ),
                )
            else:
                cur = self._conn.execute(
                    """INSERT INTO files(
                        path, node_type, language, layer, size, loc,
                        node_group, imports_count, package, content_hash,
                        blast_score, direct_dependents, transitive_dependents,
                        active, first_seen_commit, last_seen_commit,
                        first_seen_at, last_seen_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?,?,?)""",
                    (
                        path,
                        node.get("type", "module"),
                        node.get("language"),
                        node.get("layer"),
                        node.get("size"),
                        node.get("loc"),
                        node.get("group", 0),
                        imports_count,
                        node.get("package"),
                        node.get("content_hash"),
                        node.get("blast_score", 0.0),
                        node.get("direct_dependents", 0),
                        node.get("transitive_dependents", 0),
                        commit,
                        commit,
                        now,
                        now,
                    ),
                )
                fid = cur.lastrowid  # type: ignore[assignment]

            node_id_map[path] = fid
            seen_file_ids.append(fid)

        # Soft-delete files absent from current graph
        if seen_file_ids:
            placeholders = ",".join("?" * len(seen_file_ids))
            self._conn.execute(
                f"UPDATE files SET active=0, last_seen_at=? WHERE active=1 AND id NOT IN ({placeholders})",
                [now] + seen_file_ids,
            )
        else:
            self._conn.execute(
                "UPDATE files SET active=0, last_seen_at=? WHERE active=1", (now,)
            )

        # Sync edges: upsert current links, then soft-delete removed ones
        seen_edge_ids: list[int] = []
        for link in data["links"]:
            s_fid = node_id_map.get(link["source"])
            t_fid = node_id_map.get(link["target"])
            if s_fid is None or t_fid is None:
                continue
            kind = link.get("kind", "imports")
            weight = link.get("weight", 1)

            row = self._conn.execute(
                "SELECT id FROM edges WHERE source_file_id=? AND target_file_id=? AND kind=?",
                (s_fid, t_fid, kind),
            ).fetchone()

            if row:
                eid = row[0]
                self._conn.execute(
                    """UPDATE edges SET weight=?, active=1,
                        last_seen_commit=?, last_seen_at=?
                       WHERE id=?""",
                    (weight, commit, now, eid),
                )
            else:
                cur = self._conn.execute(
                    """INSERT INTO edges(
                        source_file_id, target_file_id, kind, weight, active,
                        first_seen_commit, last_seen_commit, first_seen_at, last_seen_at
                    ) VALUES (?,?,?,?,1,?,?,?,?)""",
                    (s_fid, t_fid, kind, weight, commit, commit, now, now),
                )
                eid = cur.lastrowid  # type: ignore[assignment]

            seen_edge_ids.append(eid)

        if seen_edge_ids:
            placeholders = ",".join("?" * len(seen_edge_ids))
            self._conn.execute(
                f"UPDATE edges SET active=0, last_seen_at=? WHERE active=1 AND id NOT IN ({placeholders})",
                [now] + seen_edge_ids,
            )
        else:
            self._conn.execute(
                "UPDATE edges SET active=0, last_seen_at=? WHERE active=1", (now,)
            )

        self._conn.commit()

    def sync_symbols(
        self,
        symbol_data: dict,
        commit: str | None = None,
    ) -> None:
        """Upsert symbols from build_symbol_index() output and refresh FTS."""
        now = _now()
        seen_symbol_ids: list[int] = []

        for rel_path, syms in symbol_data.get("file_symbols", {}).items():
            row = self._conn.execute(
                "SELECT id FROM files WHERE path=? AND active=1", (rel_path,)
            ).fetchone()
            if not row:
                continue
            fid = row[0]

            for sym in syms:
                existing = self._conn.execute(
                    "SELECT id FROM symbols WHERE file_id=? AND name=?",
                    (fid, sym["name"]),
                ).fetchone()

                if existing:
                    sid = existing[0]
                    self._conn.execute(
                        """UPDATE symbols SET kind=?, line=?, exported=?,
                            signature=?, doc=?, active=1,
                            last_seen_commit=?, last_seen_at=?
                           WHERE id=?""",
                        (
                            sym.get("kind"),
                            sym.get("line"),
                            1 if sym.get("exported") else 0,
                            sym.get("signature"),
                            sym.get("doc"),
                            commit,
                            now,
                            sid,
                        ),
                    )
                else:
                    cur = self._conn.execute(
                        """INSERT INTO symbols(
                            file_id, name, kind, line, exported,
                            signature, doc, active,
                            first_seen_commit, last_seen_commit,
                            first_seen_at, last_seen_at
                        ) VALUES (?,?,?,?,?,?,?,1,?,?,?,?)""",
                        (
                            fid,
                            sym["name"],
                            sym.get("kind"),
                            sym.get("line"),
                            1 if sym.get("exported") else 0,
                            sym.get("signature"),
                            sym.get("doc"),
                            commit,
                            commit,
                            now,
                            now,
                        ),
                    )
                    sid = cur.lastrowid  # type: ignore[assignment]

                seen_symbol_ids.append(sid)

        if seen_symbol_ids:
            placeholders = ",".join("?" * len(seen_symbol_ids))
            self._conn.execute(
                f"UPDATE symbols SET active=0, last_seen_at=? WHERE active=1 AND id NOT IN ({placeholders})",
                [now] + seen_symbol_ids,
            )
        else:
            self._conn.execute(
                "UPDATE symbols SET active=0, last_seen_at=? WHERE active=1", (now,)
            )

        # Refresh FTS index: clear and repopulate from active symbols.
        # Uses a standalone (non-content) FTS5 table so DELETE works normally.
        try:
            self._conn.execute("DELETE FROM symbols_fts")
            self._conn.execute(
                """INSERT INTO symbols_fts(name, doc, signature)
                   SELECT name, COALESCE(doc,''), COALESCE(signature,'')
                   FROM symbols WHERE active=1"""
            )
        except sqlite3.OperationalError:
            pass  # FTS5 not available on this build

        self._conn.commit()

    # ── status ────────────────────────────────────────────────────────────────

    def status(self) -> dict:
        """Return a snapshot of store state for `codeindex db status`."""
        return {
            "schema_version":      self.get_meta("schema_version") or "unknown",
            "last_indexed_commit": self.get_meta("last_indexed_commit") or "none",
            "repo_root":           self.get_meta("repo_root") or "unknown",
            "active_files":        self._conn.execute(
                "SELECT COUNT(*) FROM files WHERE active=1"
            ).fetchone()[0],
            "active_edges":        self._conn.execute(
                "SELECT COUNT(*) FROM edges WHERE active=1"
            ).fetchone()[0],
            "active_symbols":      self._conn.execute(
                "SELECT COUNT(*) FROM symbols WHERE active=1"
            ).fetchone()[0],
        }

    # ── close ─────────────────────────────────────────────────────────────────

    def close(self) -> None:
        self._conn.close()
