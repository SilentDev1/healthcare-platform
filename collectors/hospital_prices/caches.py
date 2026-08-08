"""In-memory lookup caches for hospital price imports.

Loaded once at import start. No DB queries during row processing.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from collectors.hospital_prices.normalization import normalize_payer_name
from packages.database import (
    InsurancePlanEntity,
    PayerAlias,
    ProcedureAlias,
    ProcedureCodeMapping,
    ProcedureCodeSystem,
)
from packages.identity import normalize_name


@dataclass
class ImportCaches:
    """Pre-loaded lookup caches. No session queries during row processing."""

    # normalized_alias -> payer_entity_id
    payer_aliases: dict[str, uuid.UUID] = field(default_factory=dict)
    # (payer_id, normalized_plan) -> plan_id
    plan_cache: dict[tuple[uuid.UUID, str], uuid.UUID] = field(default_factory=dict)
    # (code_system, code) -> (procedure_id, mapping_id)
    code_map: dict[tuple[str, str], tuple[uuid.UUID, uuid.UUID]] = field(default_factory=dict)
    # normalized_alias -> procedure_id
    procedure_aliases: dict[str, uuid.UUID] = field(default_factory=dict)
    # raw_desc -> normalized_desc (memoize normalize_name)
    description_cache: dict[str, str] = field(default_factory=dict)

    # Statistics
    payer_hits: int = 0
    payer_misses: int = 0
    plan_hits: int = 0
    plan_misses: int = 0
    procedure_hits: int = 0
    procedure_misses: int = 0

    # Pending batch creates
    pending_payer_aliases: list[PayerAlias] = field(default_factory=list)
    pending_plans: list[InsurancePlanEntity] = field(default_factory=list)

    def load(self, session: Session) -> None:
        """Load all caches from DB. Call once at import start."""
        # Payer aliases
        for alias in session.scalars(select(PayerAlias).where(PayerAlias.active.is_(True))):
            self.payer_aliases[alias.normalized_alias] = alias.payer_entity_id

        # Plan cache
        for plan in session.scalars(select(InsurancePlanEntity)):
            self.plan_cache[(plan.payer_entity_id, plan.normalized_name)] = plan.id

        # Code map
        rows = session.execute(
            select(ProcedureCodeMapping, ProcedureCodeSystem)
            .join(ProcedureCodeSystem)
            .where(ProcedureCodeMapping.mapping_status.in_(["reviewed", "approved"]))
        ).all()
        for mapping, system in rows:
            self.code_map[(system.code_system, mapping.code)] = (
                mapping.procedure_id,
                mapping.id,
            )

        # Procedure aliases
        for proc_alias in session.scalars(
            select(ProcedureAlias).where(ProcedureAlias.active.is_(True))
        ):
            self.procedure_aliases[proc_alias.normalized_alias] = proc_alias.procedure_id

    def match_payer(self, source_name: str | None) -> tuple[uuid.UUID | None, str, float]:
        """Pure in-memory payer lookup. Returns (payer_id, method, confidence)."""
        if not source_name or not source_name.strip():
            return None, "blank", 0
        normalized = normalize_payer_name(source_name)
        payer_id = self.payer_aliases.get(normalized)
        if payer_id is not None:
            self.payer_hits += 1
            return payer_id, "exact_alias", 1.0
        self.payer_misses += 1
        return None, "unknown", 0

    def match_or_create_plan(
        self, payer_id: uuid.UUID | None, source_plan: str | None
    ) -> uuid.UUID | None:
        """In-memory plan lookup. Accumulates unknown plans for batch persist."""
        if payer_id is None or not source_plan or not source_plan.strip():
            return None
        normalized = normalize_payer_name(source_plan)
        cache_key = (payer_id, normalized)
        plan_id = self.plan_cache.get(cache_key)
        if plan_id is not None:
            self.plan_hits += 1
            return plan_id
        self.plan_misses += 1
        # Create a new plan with pre-assigned UUID
        new_id = uuid.uuid4()
        plan = InsurancePlanEntity(
            id=new_id,
            payer_entity_id=payer_id,
            canonical_name=source_plan.strip(),
            normalized_name=normalized,
        )
        self.pending_plans.append(plan)
        self.plan_cache[cache_key] = new_id
        return new_id

    def normalize_description(self, desc: str) -> str:
        """Memoized normalize_name() call."""
        cached = self.description_cache.get(desc)
        if cached is not None:
            return cached
        normalized = normalize_name(desc)
        self.description_cache[desc] = normalized
        return normalized

    def lookup_code(self, system: str, code: str) -> tuple[uuid.UUID, uuid.UUID] | None:
        """Look up approved code mapping. Returns (procedure_id, mapping_id) or None."""
        return self.code_map.get((system, code))

    def lookup_procedure_alias(self, normalized_desc: str) -> uuid.UUID | None:
        """Look up procedure by normalized description alias."""
        result = self.procedure_aliases.get(normalized_desc)
        if result is not None:
            self.procedure_hits += 1
        else:
            self.procedure_misses += 1
        return result

    def flush_pending(self, session: Session) -> None:
        """Batch-persist new payer aliases and plans, then reload affected caches."""
        if self.pending_plans:
            session.add_all(self.pending_plans)
            self.pending_plans.clear()
        if self.pending_payer_aliases:
            session.add_all(self.pending_payer_aliases)
            self.pending_payer_aliases.clear()

    def stats(self) -> dict[str, int]:
        return {
            "payer_hits": self.payer_hits,
            "payer_misses": self.payer_misses,
            "plan_hits": self.plan_hits,
            "plan_misses": self.plan_misses,
            "procedure_hits": self.procedure_hits,
            "procedure_misses": self.procedure_misses,
            "description_cache_size": len(self.description_cache),
        }
