"""Checkpoint management for resumable hospital price imports."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from packages.database import ImportCheckpoint, ImportRun, SourceFile

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manages checkpoints for resumable imports."""

    def __init__(
        self,
        session: Session,
        import_run: ImportRun,
        source_file: SourceFile,
        parser_version: str,
    ) -> None:
        self._session = session
        self._run = import_run
        self._source = source_file
        self._parser_version = parser_version
        self._checkpoint_id: uuid.UUID | None = None

    @property
    def source_checksum(self) -> str:
        return self._source.checksum_sha256

    def find_active(self) -> ImportCheckpoint | None:
        """Find an active checkpoint for this source file."""
        return self._session.scalar(
            select(ImportCheckpoint)
            .where(
                ImportCheckpoint.source_file_id == self._source.id,
                ImportCheckpoint.status == "active",
            )
            .order_by(ImportCheckpoint.checkpoint_at.desc())
            .limit(1)
        )

    def can_resume(self) -> bool:
        """True if an active checkpoint exists with matching checksum + parser version."""
        checkpoint = self.find_active()
        if checkpoint is None:
            return False
        return (
            checkpoint.source_checksum == self.source_checksum
            and checkpoint.parser_version == self._parser_version
        )

    def get_resume_position(self) -> int:
        """Returns line number to skip to."""
        checkpoint = self.find_active()
        if checkpoint is None:
            return 0
        return checkpoint.last_completed_line

    def get_resume_counters(self) -> tuple[int, int, int]:
        """Returns (records_committed, rate_details_committed, batch_number)."""
        checkpoint = self.find_active()
        if checkpoint is None:
            return 0, 0, 0
        return (
            checkpoint.normalized_records_committed,
            checkpoint.rate_details_committed,
            checkpoint.batch_number,
        )

    def validate_resumability(self) -> None:
        """Raises if source checksum or parser version changed."""
        checkpoint = self.find_active()
        if checkpoint is None:
            raise ValueError("No active checkpoint found")
        if checkpoint.source_checksum != self.source_checksum:
            raise ValueError(
                f"Source checksum changed: checkpoint={checkpoint.source_checksum}, "
                f"current={self.source_checksum}"
            )
        if checkpoint.parser_version != self._parser_version:
            raise ValueError(
                f"Parser version changed: checkpoint={checkpoint.parser_version}, "
                f"current={self._parser_version}"
            )

    def resume_existing(self, checkpoint_id: uuid.UUID) -> None:
        """Adopt an existing active checkpoint so save() updates it in place.

        Without this, a resumed import's first save() would CREATE a second
        checkpoint row for the same source file, splitting resume state.
        """
        self._checkpoint_id = checkpoint_id

    def save(
        self,
        line_number: int,
        records_committed: int,
        rate_details_committed: int,
        batch_number: int,
    ) -> None:
        """Called after each committed batch. Updates or creates checkpoint."""
        now = datetime.now(UTC)
        if self._checkpoint_id is not None:
            # Update existing checkpoint
            self._session.execute(
                update(ImportCheckpoint)
                .where(ImportCheckpoint.id == self._checkpoint_id)
                .values(
                    last_completed_line=line_number,
                    normalized_records_committed=records_committed,
                    rate_details_committed=rate_details_committed,
                    batch_number=batch_number,
                    checkpoint_at=now,
                )
            )
        else:
            # Create new checkpoint
            self._checkpoint_id = uuid.uuid4()
            self._session.add(
                ImportCheckpoint(
                    id=self._checkpoint_id,
                    import_run_id=self._run.id,
                    source_file_id=self._source.id,
                    parser_version=self._parser_version,
                    source_checksum=self.source_checksum,
                    last_completed_line=line_number,
                    normalized_records_committed=records_committed,
                    rate_details_committed=rate_details_committed,
                    batch_number=batch_number,
                    checkpoint_at=now,
                    status="active",
                )
            )
        # Update import run
        self._run.last_checkpoint_at = now
        self._run.batches_committed = batch_number
        logger.info(
            "checkpoint_saved",
            extra={
                "line": line_number,
                "records": records_committed,
                "rate_details": rate_details_committed,
                "batch": batch_number,
            },
        )

    def complete(self) -> None:
        """Marks checkpoint as completed when import finishes."""
        if self._checkpoint_id is not None:
            self._session.execute(
                update(ImportCheckpoint)
                .where(ImportCheckpoint.id == self._checkpoint_id)
                .values(status="completed", checkpoint_at=datetime.now(UTC))
            )

    def abandon(self) -> None:
        """Marks checkpoint as abandoned."""
        if self._checkpoint_id is not None:
            self._session.execute(
                update(ImportCheckpoint)
                .where(ImportCheckpoint.id == self._checkpoint_id)
                .values(status="abandoned", checkpoint_at=datetime.now(UTC))
            )
