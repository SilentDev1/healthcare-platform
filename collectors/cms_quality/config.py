from dataclasses import dataclass
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass(frozen=True)
class QualityDataset:
    key: str
    name: str
    dataset_id: str
    category: str
    selected_measure_ids: frozenset[str]
    source_url: str | None = None


class QualityCollectorSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    cms_quality_general_dataset_id: str = "xubh-q36u"
    cms_quality_hcahps_dataset_id: str = "dgck-syfz"
    cms_quality_readmissions_dataset_id: str = "632h-zaca"
    cms_quality_complications_dataset_id: str = "ynj2-r877"
    cms_quality_timely_care_dataset_id: str = "yv7e-xc69"
    cms_quality_general_source_url: str | None = None
    cms_quality_hcahps_source_url: str | None = None
    cms_quality_readmissions_source_url: str | None = None
    cms_quality_complications_source_url: str | None = None
    cms_quality_timely_care_source_url: str | None = None
    cms_quality_download_max_bytes: int = Field(250_000_000, gt=0)
    cms_quality_http_timeout_seconds: float = Field(120, gt=0, le=300)
    cms_quality_http_max_retries: int = Field(3, ge=0, le=10)
    cms_quality_parser_version: str = "1.1.0"
    cms_quality_raw_data_dir: Path = Path("data/raw/cms_quality")
    cms_quality_rejected_data_dir: Path = Path("data/rejected/cms_quality")

    def datasets(self) -> tuple[QualityDataset, ...]:
        return (
            QualityDataset(
                "overall_rating",
                "CMS Hospital General Information",
                self.cms_quality_general_dataset_id,
                "overall_rating",
                frozenset({"OVERALL_RATING"}),
                self.cms_quality_general_source_url,
            ),
            QualityDataset(
                "patient_experience",
                "CMS HCAHPS Hospital",
                self.cms_quality_hcahps_dataset_id,
                "patient_experience",
                frozenset({"H_HSP_RATING_STAR_RATING"}),
                self.cms_quality_hcahps_source_url,
            ),
            QualityDataset(
                "readmission",
                "CMS Unplanned Hospital Visits",
                self.cms_quality_readmissions_dataset_id,
                "readmission",
                frozenset({"READM_30_HF"}),
                self.cms_quality_readmissions_source_url,
            ),
            QualityDataset(
                "complications",
                "CMS Complications and Deaths",
                self.cms_quality_complications_dataset_id,
                "clinical_outcomes",
                frozenset({"MORT_30_AMI", "PSI_90"}),
                self.cms_quality_complications_source_url,
            ),
            QualityDataset(
                "timely_care",
                "CMS Timely and Effective Care",
                self.cms_quality_timely_care_dataset_id,
                "timely_care",
                frozenset({"OP_18B"}),
                self.cms_quality_timely_care_source_url,
            ),
        )


quality_settings = QualityCollectorSettings()
