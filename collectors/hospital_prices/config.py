from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class HospitalPriceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    # Raw on-disk download cap. Raised to 3 GB so large academic-system MRFs (e.g. UMass
    # Memorial, other multi-hundred-MB CSV/JSON files) are not rejected before parsing;
    # streamed with a bounded digest so memory stays flat regardless of file size.
    hospital_price_max_bytes: int = Field(3_000_000_000, gt=0)
    hospital_price_max_expanded_bytes: int = Field(4_000_000_000, gt=0)
    # Ceiling for archives parsed by streaming member bytes on demand (never
    # materialized on disk). Larger than the on-disk cap because streaming keeps
    # memory bounded; still a hard backstop against zip bombs / runaway files.
    hospital_price_max_streaming_expanded_bytes: int = Field(8_000_000_000, gt=0)
    hospital_price_max_archive_files: int = Field(5, ge=1, le=100)
    hospital_price_connection_timeout_seconds: float = Field(15, gt=0, le=120)
    hospital_price_read_timeout_seconds: float = Field(300, gt=0, le=600)
    hospital_price_part_file_suffix: str = ".part"
    hospital_price_max_redirects: int = Field(5, ge=0, le=10)
    hospital_price_http_retries: int = Field(2, ge=0, le=5)
    # Larger batch → fewer per-batch commits → faster import of very dense hospitals.
    hospital_price_batch_size: int = Field(2000, ge=10, le=5000)
    hospital_price_parser_version: str = "1.0.0"
    # Some hospital sites (Tufts Medicine, Sturdy, Holyoke) front their CMS-mandated PUBLIC
    # standard-charges files with a WAF that 403s non-browser user agents. These files are
    # legally required to be publicly accessible; present a common browser UA so the public
    # file downloads. This is not authentication bypass — no credentials, no private data.
    hospital_price_user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    hospital_price_raw_dir: Path = Path("data/raw/hospital_prices/nh")
    hospital_price_profiling_enabled: bool = False
    hospital_price_profiling_milestone_rows: int = Field(1000, ge=100, le=50000)
    hospital_price_checkpoint_enabled: bool = True
    hospital_price_checkpoint_interval: int = Field(1, ge=1, le=100)
    # Optional soft wall-clock budget for a single import invocation. 0 disables it
    # (unchanged behavior). When set, the importer stops cleanly at the next
    # committed-batch boundary once exceeded, marks the run INTERRUPTED, and leaves
    # the checkpoint active so a later invocation resumes — used to finish very
    # large MRFs across several runs well before a platform task timeout hard-kills
    # the process. Never re-imports already-committed rows.
    hospital_price_import_soft_deadline_seconds: int = Field(0, ge=0)


hospital_price_settings = HospitalPriceSettings()
