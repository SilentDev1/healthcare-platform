"""Pipeline performance instrumentation for hospital price imports."""

import resource
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class SectionMetrics:
    elapsed: float = 0.0
    calls: int = 0


@dataclass
class ImportProfiler:
    """Tracks elapsed time per stage and throughput metrics."""

    sections: dict[str, SectionMetrics] = field(default_factory=dict)
    db_statements: int = 0
    db_transactions: int = 0
    rows_processed: int = 0
    records_created: int = 0
    rate_details_created: int = 0
    _start_time: float = field(default_factory=time.perf_counter)
    _peak_memory_kb: int = 0

    @contextmanager
    def time_section(self, name: str) -> Iterator[None]:
        """Context manager that accumulates elapsed time for a named stage."""
        if name not in self.sections:
            self.sections[name] = SectionMetrics()
        section = self.sections[name]
        started = time.perf_counter()
        try:
            yield
        finally:
            section.elapsed += time.perf_counter() - started
            section.calls += 1

    def record_row(self) -> None:
        self.rows_processed += 1

    def record_insert(self, count: int = 1) -> None:
        self.records_created += count

    def record_rate_detail(self, count: int = 1) -> None:
        self.rate_details_created += count

    def record_db_statement(self, count: int = 1) -> None:
        self.db_statements += count

    def record_db_transaction(self) -> None:
        self.db_transactions += 1

    def sample_memory(self) -> None:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        self._peak_memory_kb = max(self._peak_memory_kb, usage.ru_maxrss // 1024)

    @property
    def elapsed_total(self) -> float:
        return time.perf_counter() - self._start_time

    @property
    def rows_per_sec(self) -> float:
        elapsed = self.elapsed_total
        return self.rows_processed / elapsed if elapsed > 0 else 0.0

    @property
    def records_per_sec(self) -> float:
        elapsed = self.elapsed_total
        return self.records_created / elapsed if elapsed > 0 else 0.0

    @property
    def rate_details_per_sec(self) -> float:
        elapsed = self.elapsed_total
        return self.rate_details_created / elapsed if elapsed > 0 else 0.0

    def milestone_report(self, every: int = 1000) -> dict[str, object] | None:
        """Returns a report dict every `every` rows, or None."""
        if self.rows_processed == 0 or self.rows_processed % every != 0:
            return None
        self.sample_memory()
        return {
            "rows_processed": self.rows_processed,
            "records_created": self.records_created,
            "rate_details_created": self.rate_details_created,
            "rows_per_sec": round(self.rows_per_sec, 1),
            "records_per_sec": round(self.records_per_sec, 1),
            "elapsed_sec": round(self.elapsed_total, 2),
            "peak_memory_mb": round(self._peak_memory_kb / 1024, 1),
            "db_statements": self.db_statements,
        }

    def summary(self) -> dict[str, object]:
        """Final summary report."""
        self.sample_memory()
        section_report = {
            name: {"elapsed_sec": round(m.elapsed, 4), "calls": m.calls}
            for name, m in sorted(self.sections.items(), key=lambda x: -x[1].elapsed)
        }
        return {
            "total_elapsed_sec": round(self.elapsed_total, 2),
            "rows_processed": self.rows_processed,
            "records_created": self.records_created,
            "rate_details_created": self.rate_details_created,
            "rows_per_sec": round(self.rows_per_sec, 1),
            "records_per_sec": round(self.records_per_sec, 1),
            "rate_details_per_sec": round(self.rate_details_per_sec, 1),
            "db_statements": self.db_statements,
            "db_transactions": self.db_transactions,
            "peak_memory_mb": round(self._peak_memory_kb / 1024, 1),
            "sections": section_report,
        }
