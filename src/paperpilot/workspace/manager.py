"""SQLite database manager for Multi-Paper Workspace Management."""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator
from uuid import UUID, uuid4

from paperpilot.core.models import ChunkingStrategy, PaperMetadata, PaperSource, TextChunk

logger = logging.getLogger(__name__)


class WorkspaceManager:
    """Manages the SQLite database for storing workspaces, papers, and text chunks.

    Handles connection lifecycle and schema setup.
    """

    def __init__(self, db_path: Path | str) -> None:
        """Initialize the database manager and setup tables."""
        self.db_path = Path(db_path)
        logger.info("Initializing WorkspaceManager at %s", self.db_path)
        self._init_db()

    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        """Yield a database connection with Row factory and foreign keys enabled.

        A plain sqlite3.Connection used as `with conn:` only commits/rolls back
        the transaction — it never closes the connection. Wrapping this as a
        contextmanager ensures every `with self._get_connection() as conn:`
        call site also closes the connection on exit, avoiding a connection
        leak on every database call.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Create schema tables if they do not exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._get_connection() as conn:
            # 1. Workspaces Table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workspaces (
                    workspace_id TEXT PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

            # 2. Papers Table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS papers (
                    paper_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    authors TEXT,
                    publication_year INTEGER,
                    citation_count INTEGER,
                    abstract TEXT,
                    doi TEXT,
                    pdf_url TEXT,
                    source TEXT,
                    venue TEXT,
                    keywords TEXT,
                    discovered_at TEXT NOT NULL
                );
                """
            )

            # 3. Workspace Papers Mapping Table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workspace_papers (
                    workspace_id TEXT,
                    paper_id TEXT,
                    PRIMARY KEY (workspace_id, paper_id),
                    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
                    FOREIGN KEY (paper_id) REFERENCES papers(paper_id) ON DELETE CASCADE
                );
                """
            )

            # 4. Text Chunks Table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS text_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    paper_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    char_count INTEGER NOT NULL,
                    start_page INTEGER,
                    end_page INTEGER,
                    strategy TEXT NOT NULL,
                    metadata TEXT,
                    FOREIGN KEY (paper_id) REFERENCES papers(paper_id) ON DELETE CASCADE
                );
                """
            )

            # 5. Chat Messages Table — persists WorkspaceChatStore's conversation
            # memory (app/utils.py) so it survives a server restart, not just
            # the lifetime of the process. ON DELETE CASCADE means deleting a
            # workspace also deletes its conversation with no extra code.
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    workspace_id TEXT NOT NULL,
                    turn_index INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (workspace_id, turn_index),
                    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id) ON DELETE CASCADE
                );
                """
            )
            conn.commit()
            logger.info("Workspace database tables initialized successfully.")

    def create_workspace(self, name: str) -> UUID:
        """Create a new workspace with a unique name.

        Args:
            name: Human-readable name.

        Returns:
            The created workspace UUID.
        """
        workspace_id = uuid4()
        created_at = datetime.now().isoformat()

        with self._get_connection() as conn:
            try:
                conn.execute(
                    "INSERT INTO workspaces (workspace_id, name, created_at) VALUES (?, ?, ?);",
                    (str(workspace_id), name, created_at),
                )
                conn.commit()
                logger.info("Created workspace '%s' with ID %s", name, workspace_id)
                return workspace_id
            except sqlite3.IntegrityError as e:
                logger.error("Failed to create workspace '%s': name already exists. Error: %s", name, e)
                raise ValueError(f"Workspace with name '{name}' already exists.") from e

    def delete_workspace(self, workspace_id: UUID) -> None:
        """Delete a workspace. Associated mappings are deleted via CASCADE."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM workspaces WHERE workspace_id = ?;", (str(workspace_id),))
            conn.commit()
            logger.info("Deleted workspace %s", workspace_id)

    def list_workspaces(self) -> list[dict[str, Any]]:
        """Return a list of all workspaces and their paper counts.

        Returns:
            List of dicts: [{'workspace_id': UUID, 'name': str, 'created_at': datetime, 'paper_count': int}]
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT w.workspace_id, w.name, w.created_at, COUNT(wp.paper_id) as paper_count
                FROM workspaces w
                LEFT JOIN workspace_papers wp ON w.workspace_id = wp.workspace_id
                GROUP BY w.workspace_id;
                """
            )
            rows = cursor.fetchall()
            return [
                {
                    "workspace_id": UUID(row["workspace_id"]),
                    "name": row["name"],
                    "created_at": datetime.fromisoformat(row["created_at"]),
                    "paper_count": row["paper_count"],
                }
                for row in rows
            ]

    def add_paper_to_workspace(
        self,
        workspace_id: UUID,
        paper: PaperMetadata,
        chunks: list[TextChunk],
    ) -> None:
        """Add a paper's metadata and chunks to a workspace.

        Saves paper metadata to `papers` table, inserts workspace mapping,
        and saves all chunks to the `text_chunks` table.

        Args:
            workspace_id: The target workspace UUID.
            paper: PaperMetadata object.
            chunks: List of TextChunk objects to save.
        """
        with self._get_connection() as conn:
            # 1. Insert paper metadata (ignore if already exists)
            conn.execute(
                """
                INSERT OR IGNORE INTO papers (
                    paper_id, title, authors, publication_year, citation_count,
                    abstract, doi, pdf_url, source, venue, keywords, discovered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    str(paper.paper_id),
                    paper.title,
                    json.dumps(paper.authors),
                    paper.publication_year,
                    paper.citation_count,
                    paper.abstract,
                    paper.doi,
                    paper.pdf_url,
                    paper.source.value,
                    paper.venue,
                    json.dumps(paper.keywords),
                    paper.discovered_at.isoformat(),
                ),
            )

            # 2. Map paper to workspace (ignore if mapping exists)
            conn.execute(
                """
                INSERT OR IGNORE INTO workspace_papers (workspace_id, paper_id)
                VALUES (?, ?);
                """,
                (str(workspace_id), str(paper.paper_id)),
            )

            # 3. Insert chunks (ignore duplicate chunks if re-indexing)
            for chunk in chunks:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO text_chunks (
                        chunk_id, paper_id, chunk_index, text, char_count,
                        start_page, end_page, strategy, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        str(chunk.chunk_id),
                        str(chunk.paper_id),
                        chunk.chunk_index,
                        chunk.text,
                        chunk.char_count,
                        chunk.start_page,
                        chunk.end_page,
                        chunk.strategy.value,
                        json.dumps(chunk.metadata),
                    ),
                )
            conn.commit()
            logger.info("Added paper '%s' and %d chunks to workspace %s", paper.title, len(chunks), workspace_id)

    @staticmethod
    def _row_to_paper_metadata(row: sqlite3.Row) -> PaperMetadata:
        """Map a `papers` table row to a PaperMetadata instance.

        Shared by every method that reads from the `papers` table so the
        row-to-model mapping has exactly one implementation.
        """
        return PaperMetadata(
            paper_id=UUID(row["paper_id"]),
            title=row["title"],
            authors=json.loads(row["authors"]) if row["authors"] else [],
            publication_year=row["publication_year"],
            citation_count=row["citation_count"],
            abstract=row["abstract"],
            doi=row["doi"],
            pdf_url=row["pdf_url"],
            source=PaperSource(row["source"]),
            venue=row["venue"],
            keywords=json.loads(row["keywords"]) if row["keywords"] else [],
            discovered_at=datetime.fromisoformat(row["discovered_at"]),
        )

    def get_workspace_papers(self, workspace_id: UUID) -> list[PaperMetadata]:
        """Retrieve all papers belonging to a workspace.

        Args:
            workspace_id: The workspace UUID.

        Returns:
            List of PaperMetadata objects.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT p.* FROM papers p
                JOIN workspace_papers wp ON p.paper_id = wp.paper_id
                WHERE wp.workspace_id = ?;
                """,
                (str(workspace_id),),
            )
            rows = cursor.fetchall()
            return [self._row_to_paper_metadata(row) for row in rows]

    def get_paper_by_id(self, paper_id: UUID) -> PaperMetadata | None:
        """Retrieve a single paper's metadata by ID, independent of workspace membership.

        Args:
            paper_id: The paper's UUID.

        Returns:
            The PaperMetadata, or None if no paper with that ID exists.
        """
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM papers WHERE paper_id = ?;", (str(paper_id),)
            ).fetchone()
            return self._row_to_paper_metadata(row) if row else None

    def get_chunks_for_workspace(self, workspace_id: UUID) -> list[TextChunk]:
        """Retrieve all chunks belonging to all papers in a workspace.

        Args:
            workspace_id: The workspace UUID.

        Returns:
            List of TextChunk objects.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT tc.* FROM text_chunks tc
                JOIN workspace_papers wp ON tc.paper_id = wp.paper_id
                WHERE wp.workspace_id = ?;
                """,
                (str(workspace_id),),
            )
            rows = cursor.fetchall()

            chunks = []
            for row in rows:
                chunks.append(
                    TextChunk(
                        chunk_id=UUID(row["chunk_id"]),
                        paper_id=UUID(row["paper_id"]),
                        chunk_index=row["chunk_index"],
                        text=row["text"],
                        char_count=row["char_count"],
                        start_page=row["start_page"],
                        end_page=row["end_page"],
                        strategy=ChunkingStrategy(row["strategy"]),
                        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    )
                )
            return chunks

    def update_paper_metadata(self, paper: PaperMetadata) -> None:
        """Update an existing paper's metadata in the database.

        Args:
            paper: Updated PaperMetadata object.
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE papers SET
                    title = ?,
                    authors = ?,
                    publication_year = ?,
                    citation_count = ?,
                    abstract = ?,
                    doi = ?,
                    pdf_url = ?,
                    venue = ?,
                    keywords = ?
                WHERE paper_id = ?;
                """,
                (
                    paper.title,
                    json.dumps(paper.authors),
                    paper.publication_year,
                    paper.citation_count,
                    paper.abstract,
                    paper.doi,
                    paper.pdf_url,
                    paper.venue,
                    json.dumps(paper.keywords),
                    str(paper.paper_id),
                ),
            )
            conn.commit()
            logger.info("Updated paper metadata in database for: '%s'", paper.title)

    def get_chat_messages(self, workspace_id: UUID) -> list[dict[str, str]]:
        """Retrieve a workspace's conversation history, oldest turn first.

        Returns:
            List of {'role': str, 'content': str} dicts ordered by turn_index.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT role, content FROM chat_messages
                WHERE workspace_id = ?
                ORDER BY turn_index ASC;
                """,
                (str(workspace_id),),
            )
            return [{"role": row["role"], "content": row["content"]} for row in cursor.fetchall()]

    def replace_chat_messages(self, workspace_id: UUID, messages: list[tuple[str, str]]) -> None:
        """Overwrite a workspace's stored conversation with `messages`.

        Matches WorkspaceChatStore's existing "whole-history replace" contract
        (get the full history, hand it to a service, write back whatever comes
        out) rather than an append-only log, so no caller above this needed to
        change when memory moved from an in-memory dict to this table.

        Args:
            workspace_id: The workspace UUID.
            messages: Ordered (role, content) pairs, oldest first.
        """
        created_at = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("DELETE FROM chat_messages WHERE workspace_id = ?;", (str(workspace_id),))
            conn.executemany(
                """
                INSERT INTO chat_messages (workspace_id, turn_index, role, content, created_at)
                VALUES (?, ?, ?, ?, ?);
                """,
                [
                    (str(workspace_id), index, role, content, created_at)
                    for index, (role, content) in enumerate(messages)
                ],
            )
            conn.commit()

    def clear_chat_messages(self, workspace_id: UUID) -> None:
        """Delete a workspace's stored conversation without deleting the workspace."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM chat_messages WHERE workspace_id = ?;", (str(workspace_id),))
            conn.commit()
            logger.info("Cleared chat history for workspace %s", workspace_id)
