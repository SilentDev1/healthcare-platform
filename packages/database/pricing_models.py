import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from packages.database.models import Base, TimestampMixin


class ImportCheckpoint(Base):
    __tablename__ = "import_checkpoints"
    __table_args__ = (Index("ix_checkpoint_run_status", "import_run_id", "status"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    import_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_runs.id"), index=True)
    source_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_files.id"), index=True)
    parser_version: Mapped[str] = mapped_column(String(50))
    source_checksum: Mapped[str] = mapped_column(String(64))
    last_completed_line: Mapped[int] = mapped_column(BigInteger)
    normalized_records_committed: Mapped[int] = mapped_column(BigInteger)
    rate_details_committed: Mapped[int] = mapped_column(BigInteger)
    batch_number: Mapped[int] = mapped_column(default=0)
    checkpoint_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    resume_token: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)


class FacilityPriceSource(TimestampMixin, Base):
    __tablename__ = "facility_price_sources"
    __table_args__ = (
        UniqueConstraint(
            "facility_id", "machine_readable_file_url", name="uq_facility_price_source_url"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), index=True)
    facility_location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("facility_locations.id"), index=True
    )
    location_association_status: Mapped[str] = mapped_column(
        String(40), default="unresolved", server_default="unresolved", index=True
    )
    location_association_evidence: Mapped[dict[str, object] | None] = mapped_column(JSON)
    source_type: Mapped[str] = mapped_column(String(50), index=True)
    source_page_url: Mapped[str | None] = mapped_column(String(2048))
    machine_readable_file_url: Mapped[str] = mapped_column(String(2048))
    cms_hpt_txt_url: Mapped[str | None] = mapped_column(String(2048))
    declared_format: Mapped[str | None] = mapped_column(String(30))
    detected_format: Mapped[str | None] = mapped_column(String(30))
    declared_schema_version: Mapped[str | None] = mapped_column(String(50))
    detected_schema_version: Mapped[str | None] = mapped_column(String(50))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    discovery_method: Mapped[str] = mapped_column(String(50))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_successful_download_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failed_download_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_files.id"), index=True
    )
    file_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    health_system_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vendor_name: Mapped[str | None] = mapped_column(String(100), nullable=True)


class FacilityPriceSourceHistory(Base):
    """Tracks URL changes for facility price sources (self-healing audit trail)."""

    __tablename__ = "facility_price_source_history"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    facility_price_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("facility_price_sources.id"), index=True
    )
    previous_url: Mapped[str] = mapped_column(String(2048))
    new_url: Mapped[str] = mapped_column(String(2048))
    change_reason: Mapped[str] = mapped_column(String(255))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PriceSourceDiscoveryRun(Base):
    __tablename__ = "price_source_discovery_runs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), index=True)
    facilities_examined: Mapped[int] = mapped_column(default=0)
    sources_found: Mapped[int] = mapped_column(default=0)
    sources_updated: Mapped[int] = mapped_column(default=0)
    sources_missing: Mapped[int] = mapped_column(default=0)
    sources_failed: Mapped[int] = mapped_column(default=0)
    error_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PriceSourceDiscoveryObservation(Base):
    __tablename__ = "price_source_discovery_observations"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "facility_id", "candidate_url", name="uq_price_discovery_observation"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("price_source_discovery_runs.id"), index=True
    )
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), index=True)
    candidate_url: Mapped[str] = mapped_column(String(2048))
    source_page_url: Mapped[str | None] = mapped_column(String(2048))
    discovery_method: Mapped[str] = mapped_column(String(50))
    content_type: Mapped[str | None] = mapped_column(String(255))
    http_status: Mapped[int | None] = mapped_column()
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    status: Mapped[str] = mapped_column(String(40), index=True)
    reason: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ParserReview(TimestampMixin, Base):
    __tablename__ = "parser_reviews"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_files.id"), index=True)
    detected_format: Mapped[str] = mapped_column(String(30))
    detected_headers: Mapped[list[object]] = mapped_column(JSON)
    bounded_sample: Mapped[list[object]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(
        String(40), default="unsupported_pending_review", index=True
    )
    reason: Mapped[str] = mapped_column(Text)


class ParserMappingProposal(TimestampMixin, Base):
    __tablename__ = "parser_mapping_proposals"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    parser_review_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parser_reviews.id"), index=True)
    proposed_mapping: Mapped[dict[str, object]] = mapped_column(JSON)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    explanation: Mapped[str] = mapped_column(Text)
    proposal_method: Mapped[str] = mapped_column(String(40))


class ParserMappingDecision(Base):
    __tablename__ = "parser_mapping_decisions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("parser_mapping_proposals.id"), index=True
    )
    decision: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(Text)
    reviewed_by: Mapped[str] = mapped_column(String(255))
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PayerEntity(TimestampMixin, Base):
    __tablename__ = "payer_entities"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    canonical_name: Mapped[str] = mapped_column(String(255), unique=True)
    slug: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class PayerAlias(TimestampMixin, Base):
    __tablename__ = "payer_aliases"
    __table_args__ = (UniqueConstraint("normalized_alias", name="uq_payer_alias_normalized"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    payer_entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payer_entities.id"), index=True)
    source_alias: Mapped[str] = mapped_column(String(500))
    normalized_alias: Mapped[str] = mapped_column(String(500), index=True)
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_files.id"))
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class InsurancePlanEntity(TimestampMixin, Base):
    __tablename__ = "insurance_plan_entities"
    __table_args__ = (
        UniqueConstraint("payer_entity_id", "normalized_name", name="uq_plan_payer_name"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    payer_entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payer_entities.id"), index=True)
    canonical_name: Mapped[str] = mapped_column(String(500))
    normalized_name: Mapped[str] = mapped_column(String(500), index=True)
    plan_type: Mapped[str | None] = mapped_column(String(100))
    network_name: Mapped[str | None] = mapped_column(String(255))
    product_name: Mapped[str | None] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class InsurancePlanAlias(TimestampMixin, Base):
    __tablename__ = "insurance_plan_aliases"
    __table_args__ = (
        UniqueConstraint("insurance_plan_entity_id", "normalized_alias", name="uq_plan_alias"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    insurance_plan_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("insurance_plan_entities.id"), index=True
    )
    source_alias: Mapped[str] = mapped_column(String(500))
    normalized_alias: Mapped[str] = mapped_column(String(500), index=True)
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_files.id"))
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class HospitalPriceRecord(Base):
    __tablename__ = "hospital_price_records"
    __table_args__ = (
        UniqueConstraint(
            "source_file_id", "source_record_identifier", name="uq_price_record_source_identifier"
        ),
        Index("ix_price_record_facility_observed", "facility_id", "observed_at"),
        CheckConstraint(
            "gross_charge IS NULL OR gross_charge >= 0", name="ck_price_gross_nonnegative"
        ),
        CheckConstraint(
            "discounted_cash_price IS NULL OR discounted_cash_price >= 0",
            name="ck_price_cash_nonnegative",
        ),
        CheckConstraint(
            "deidentified_minimum_negotiated_rate IS NULL OR "
            "deidentified_minimum_negotiated_rate >= 0",
            name="ck_price_min_nonnegative",
        ),
        CheckConstraint(
            "deidentified_maximum_negotiated_rate IS NULL OR "
            "deidentified_maximum_negotiated_rate >= 0",
            name="ck_price_max_nonnegative",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), index=True)
    facility_location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("facility_locations.id"), index=True
    )
    source_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_files.id"), index=True)
    import_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_runs.id"), index=True)
    facility_source_observation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("facility_source_observations.id")
    )
    source_record_identifier: Mapped[str] = mapped_column(String(500))
    source_line_number: Mapped[int | None] = mapped_column(BigInteger)
    source_payload_hash: Mapped[str] = mapped_column(String(64), index=True)
    raw_description: Mapped[str] = mapped_column(Text)
    service_description_normalized: Mapped[str | None] = mapped_column(Text)
    setting: Mapped[str | None] = mapped_column(String(40), index=True)
    billing_class: Mapped[str | None] = mapped_column(String(40))
    service_package: Mapped[str | None] = mapped_column(String(255))
    drug_unit: Mapped[str | None] = mapped_column(String(100))
    drug_type_of_measurement: Mapped[str | None] = mapped_column(String(100))
    gross_charge: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    discounted_cash_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    deidentified_minimum_negotiated_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    deidentified_maximum_negotiated_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSON)
    parser_name: Mapped[str] = mapped_column(String(100), index=True)
    parser_version: Mapped[str] = mapped_column(String(50))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HospitalPriceRateDetail(Base):
    __tablename__ = "hospital_price_rate_details"
    __table_args__ = (
        UniqueConstraint(
            "hospital_price_record_id",
            "source_payer_name",
            "source_plan_name",
            "negotiated_rate",
            name="uq_price_rate_tuple",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    hospital_price_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hospital_price_records.id"), index=True
    )
    payer_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payer_entities.id"), index=True
    )
    insurance_plan_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("insurance_plan_entities.id"), index=True
    )
    source_payer_name: Mapped[str] = mapped_column(String(500))
    source_plan_name: Mapped[str | None] = mapped_column(String(500))
    negotiated_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    negotiated_rate_type: Mapped[str | None] = mapped_column(String(30))
    negotiated_rate_algorithm: Mapped[str | None] = mapped_column(Text)
    percentage_of_total: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    contract_method: Mapped[str | None] = mapped_column(String(100))
    additional_generic_notes: Mapped[str | None] = mapped_column(Text)
    source_payload: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PriceServiceCode(Base):
    __tablename__ = "price_service_codes"
    __table_args__ = (
        UniqueConstraint(
            "hospital_price_record_id",
            "code_system",
            "code",
            "modifier",
            name="uq_price_service_code",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    hospital_price_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hospital_price_records.id"), index=True
    )
    code_system: Mapped[str] = mapped_column(String(40), index=True)
    code: Mapped[str] = mapped_column(String(100), index=True)
    modifier: Mapped[str | None] = mapped_column(String(255))
    raw_code_type: Mapped[str] = mapped_column(String(100))
    raw_code: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PricingUnmatchedRecord(TimestampMixin, Base):
    __tablename__ = "pricing_unmatched_records"
    __table_args__ = (
        UniqueConstraint(
            "source_file_id", "source_record_identifier", "reason", name="uq_pricing_unmatched"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_files.id"), index=True)
    import_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_runs.id"), index=True)
    facility_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("facilities.id"), index=True)
    source_record_identifier: Mapped[str] = mapped_column(String(500))
    reason: Mapped[str] = mapped_column(Text)
    raw_description: Mapped[str | None] = mapped_column(Text)
    supplied_codes: Mapped[dict[str, object] | None] = mapped_column(JSON)
    supplied_payer: Mapped[str | None] = mapped_column(String(500))
    supplied_plan: Mapped[str | None] = mapped_column(String(500))
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSON)
    review_status: Mapped[str] = mapped_column(String(30), default="pending", index=True)


class PriceRecordProcedureCandidate(TimestampMixin, Base):
    __tablename__ = "price_record_procedure_candidates"
    __table_args__ = (
        UniqueConstraint(
            "hospital_price_record_id",
            "procedure_id",
            "match_method",
            name="uq_price_procedure_candidate",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    hospital_price_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hospital_price_records.id"), index=True
    )
    procedure_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("procedures.id"), index=True)
    match_method: Mapped[str] = mapped_column(String(50))
    score: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)


class PriceRecordProcedureMapping(TimestampMixin, Base):
    __tablename__ = "price_record_procedure_mappings"
    __table_args__ = (
        UniqueConstraint(
            "hospital_price_record_id", "procedure_id", name="uq_price_procedure_mapping"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    hospital_price_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hospital_price_records.id"), index=True
    )
    procedure_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("procedures.id"), index=True)
    mapping_method: Mapped[str] = mapped_column(String(50))
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    reviewed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", index=True
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(255))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_code_mapping_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("procedure_code_mappings.id")
    )


class PricingAnomaly(Base):
    __tablename__ = "pricing_anomalies"
    __table_args__ = (
        UniqueConstraint(
            "hospital_price_record_id",
            "hospital_price_rate_detail_id",
            "rule_key",
            name="uq_pricing_anomaly_rule",
        ),
        Index("ix_pricing_anomaly_filters", "severity", "status", "detected_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    hospital_price_record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("hospital_price_records.id"), index=True
    )
    hospital_price_rate_detail_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("hospital_price_rate_details.id"), index=True
    )
    anomaly_type: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(20), index=True)
    rule_key: Mapped[str] = mapped_column(String(100))
    rule_version: Mapped[str] = mapped_column(String(20), default="1.0")
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[dict[str, object]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="open", index=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_notes: Mapped[str | None] = mapped_column(Text)


class FacilityProcedurePriceObservation(TimestampMixin, Base):
    __tablename__ = "facility_procedure_price_observations"
    __table_args__ = (
        UniqueConstraint(
            "hospital_price_record_id",
            "hospital_price_rate_detail_id",
            "price_type",
            name="uq_facility_procedure_price_observation",
        ),
        Index(
            "ix_price_observation_consumer_detail",
            "procedure_id",
            "facility_location_id",
            "publication_status",
            "price_type",
        ),
        # Indexes the inbound FK to hospital_price_rate_details so deleting a
        # rate-detail row does an index lookup for referencing observations, not a
        # full seq scan of this (all-hospitals) table per deleted row. Without it,
        # deleting a source's rate details is O(rows^2) and never completes on a
        # large source (see migration 0013).
        Index(
            "ix_price_observation_rate_detail_id",
            "hospital_price_rate_detail_id",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), index=True)
    facility_location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("facility_locations.id"), index=True
    )
    procedure_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("procedures.id"), index=True)
    hospital_price_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hospital_price_records.id"), index=True
    )
    hospital_price_rate_detail_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("hospital_price_rate_details.id")
    )
    payer_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payer_entities.id"), index=True
    )
    insurance_plan_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("insurance_plan_entities.id")
    )
    price_type: Mapped[str] = mapped_column(String(30), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    service_setting: Mapped[str] = mapped_column(String(40), index=True)
    included_component_scope: Mapped[str] = mapped_column(String(100))
    source_confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    mapping_confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    publication_status: Mapped[str] = mapped_column(String(30), index=True)


class FacilityProcedurePriceSummary(Base):
    __tablename__ = "facility_procedure_price_summaries"
    __table_args__ = (
        UniqueConstraint(
            "facility_id",
            "facility_location_id",
            "procedure_id",
            "payer_entity_id",
            "insurance_plan_entity_id",
            "service_setting",
            "included_component_scope",
            name="uq_facility_procedure_price_summary",
        ),
        Index("ix_price_summary_public", "procedure_id", "publication_status", "service_setting"),
        Index(
            "ix_price_summary_consumer_insurance",
            "procedure_id",
            "facility_location_id",
            "publication_status",
            "payer_entity_id",
            "insurance_plan_entity_id",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), index=True)
    facility_location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("facility_locations.id"), index=True
    )
    procedure_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("procedures.id"), index=True)
    payer_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payer_entities.id"), index=True
    )
    insurance_plan_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("insurance_plan_entities.id"), index=True
    )
    service_setting: Mapped[str] = mapped_column(String(40), index=True)
    included_component_scope: Mapped[str] = mapped_column(
        String(100), default="unknown", server_default="unknown"
    )
    cash_price_min: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    cash_price_max: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    cash_price_median: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    negotiated_price_min: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    negotiated_price_max: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    negotiated_price_median: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    record_count: Mapped[int] = mapped_column()
    source_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_files.id"))
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    publication_status: Mapped[str] = mapped_column(String(30), index=True)
    completeness_score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    notes: Mapped[str | None] = mapped_column(Text)


class FacilityProcedurePriceSummarySource(Base):
    __tablename__ = "facility_procedure_price_summary_sources"
    __table_args__ = (
        UniqueConstraint("summary_id", "source_file_id", name="uq_summary_source_file"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    summary_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("facility_procedure_price_summaries.id", ondelete="CASCADE"), index=True
    )
    source_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_files.id"), index=True)
    observation_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PriceAuditRun(Base):
    """A reproducible, append-only public-price audit execution."""

    __tablename__ = "price_audit_runs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    state: Mapped[str] = mapped_column(String(2), index=True)
    seed: Mapped[int] = mapped_column(default=4700)
    requested_sample_size: Mapped[int] = mapped_column()
    full_audit: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    filters: Mapped[dict[str, object]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), index=True)
    audit_version: Mapped[str] = mapped_column(String(30))
    result_counts: Mapped[dict[str, object] | None] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PriceAuditResult(Base):
    """Immutable evidence and outcome for one public observation audit."""

    __tablename__ = "price_audit_results"
    __table_args__ = (
        UniqueConstraint("run_id", "observation_id", name="uq_price_audit_observation"),
        Index("ix_price_audit_result_status", "audit_status", "audited_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("price_audit_runs.id", ondelete="CASCADE"), index=True
    )
    observation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("facility_procedure_price_observations.id"), index=True
    )
    summary_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("facility_procedure_price_summaries.id"), index=True
    )
    record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hospital_price_records.id"), index=True
    )
    source_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_files.id"), index=True)
    audit_status: Mapped[str] = mapped_column(String(40), index=True)
    source_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    normalized_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    difference: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    semantic_checks: Mapped[dict[str, object]] = mapped_column(JSON)
    provenance_checks: Mapped[dict[str, object]] = mapped_column(JSON)
    evidence: Mapped[dict[str, object]] = mapped_column(JSON)
    audit_version: Mapped[str] = mapped_column(String(30))
    audited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InsuranceNetworkEntity(TimestampMixin, Base):
    """A payer network, distinct from a payer brand and insurance product."""

    __tablename__ = "insurance_network_entities"
    __table_args__ = (
        UniqueConstraint("payer_entity_id", "normalized_name", name="uq_network_payer_name"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    payer_entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payer_entities.id"), index=True)
    canonical_name: Mapped[str] = mapped_column(String(500))
    normalized_name: Mapped[str] = mapped_column(String(500), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class ProviderDirectorySource(Base):
    """Versioned official source metadata for network observations."""

    __tablename__ = "provider_directory_sources"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    payer_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payer_entities.id"), index=True
    )
    insurance_plan_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("insurance_plan_entities.id"), index=True
    )
    insurance_network_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("insurance_network_entities.id"), index=True
    )
    state: Mapped[str | None] = mapped_column(String(2), index=True)
    source_name: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str] = mapped_column(String(2048))
    source_type: Mapped[str] = mapped_column(String(60))
    machine_readable: Mapped[bool] = mapped_column(Boolean, default=False)
    api_available: Mapped[bool] = mapped_column(Boolean, default=False)
    authentication_required: Mapped[bool] = mapped_column(Boolean, default=False)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    freshness_days: Mapped[int] = mapped_column(default=30)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class NetworkParticipationObservation(Base):
    """Historical, plan/network-specific participation evidence; never an inferred claim."""

    __tablename__ = "network_participation_observations"
    __table_args__ = (
        Index("ix_network_observation_lookup", "facility_id", "status", "observed_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("provider_directory_sources.id"), index=True
    )
    payer_entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payer_entities.id"), index=True)
    insurance_plan_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("insurance_plan_entities.id"), index=True
    )
    insurance_network_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("insurance_network_entities.id"), index=True
    )
    facility_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("facilities.id"), index=True)
    facility_location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("facility_locations.id"), index=True
    )
    state: Mapped[str] = mapped_column(String(2), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    source_provider_identifier: Mapped[str | None] = mapped_column(String(255))
    identifier_match_evidence: Mapped[dict[str, object]] = mapped_column(JSON)
    source_evidence: Mapped[dict[str, object]] = mapped_column(JSON)
    normalized_evidence: Mapped[dict[str, object]] = mapped_column(JSON)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    review_status: Mapped[str] = mapped_column(String(30), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source_effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PriceSourceOverlapAnalysis(Base):
    __tablename__ = "price_source_overlap_analyses"
    __table_args__ = (
        UniqueConstraint(
            "left_source_file_id", "right_source_file_id", name="uq_price_source_overlap_pair"
        ),
        Index("ix_price_source_overlap_classification", "classification"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), index=True)
    left_source_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_files.id"))
    right_source_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_files.id"))
    left_location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("facility_locations.id"))
    right_location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("facility_locations.id"))
    classification: Mapped[str] = mapped_column(String(60), index=True)
    metrics: Mapped[dict[str, object]] = mapped_column(JSON)
    evidence: Mapped[dict[str, object]] = mapped_column(JSON)
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PricingHealthScore(Base):
    __tablename__ = "pricing_health_scores"
    __table_args__ = (UniqueConstraint("facility_id", name="uq_pricing_health_facility"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), index=True)
    source_discovery_score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    download_score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    parse_score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    mapping_score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    payer_normalization_score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    anomaly_score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    freshness_score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    price_coverage_score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    overall_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), index=True)
    details: Mapped[dict[str, object]] = mapped_column(JSON)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PricingReviewAudit(Base):
    __tablename__ = "pricing_review_audits"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(50), index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    action: Mapped[str] = mapped_column(String(50))
    reason: Mapped[str] = mapped_column(Text)
    reviewed_by: Mapped[str] = mapped_column(String(255))
    before_state: Mapped[dict[str, object]] = mapped_column(JSON)
    after_state: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PriceChangeSnapshot(Base):
    __tablename__ = "price_change_snapshots"
    __table_args__ = (
        Index(
            "ix_price_change_facility_procedure",
            "facility_id",
            "procedure_id",
            "snapshot_at",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"), index=True)
    facility_location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("facility_locations.id"), index=True
    )
    procedure_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("procedures.id"), index=True)
    payer_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payer_entities.id"), nullable=True
    )
    service_setting: Mapped[str] = mapped_column(String(50))
    included_component_scope: Mapped[str] = mapped_column(
        String(100), default="unknown", server_default="unknown"
    )
    previous_cash_median: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    current_cash_median: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    cash_change_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    previous_negotiated_median: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    current_negotiated_median: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    negotiated_change_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    previous_import_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("import_runs.id"), nullable=True
    )
    current_import_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("import_runs.id"), nullable=True
    )
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
