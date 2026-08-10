from collections.abc import Generator
from pathlib import Path

import pytest

from collectors.hospital_prices.config import hospital_price_settings


@pytest.fixture(scope="session", autouse=True)
def isolate_hospital_price_archives(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[None, None, None]:
    """Keep fixture pipeline archives out of durable local provenance storage."""
    original = hospital_price_settings.hospital_price_raw_dir
    hospital_price_settings.hospital_price_raw_dir = Path(
        tmp_path_factory.mktemp("hospital-price-archives")
    )
    try:
        yield
    finally:
        hospital_price_settings.hospital_price_raw_dir = original
