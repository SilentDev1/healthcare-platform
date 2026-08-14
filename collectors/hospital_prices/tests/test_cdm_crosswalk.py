"""Regression tests for the reviewed CDM description crosswalk.

Cases use the ACTUAL Concord Hospital-Laconia (CCN 300005) wording surfaced by the
mapping diagnostic. They assert two things equally: that genuine services resolve to
the correct standard code, and — critically for safety — that lookalike descriptions
(drugs, catheter brand names, different procedure variants) do NOT map. Candidate
discovery is not approval: a description match only counts when it is unambiguous.
"""

from collectors.hospital_prices.cdm_crosswalk import apply_cdm_crosswalk


def _resolve(description: str) -> tuple[str, str, float] | None:
    # code_type CDM is what triggers the crosswalk (Concord-Laconia's raw_code_type).
    return apply_cdm_crosswalk("7527989-CHLF", "CDM", description)


def _code(description: str) -> tuple[str, str]:
    """Resolved (code, system) for a description that must map; asserts non-None."""
    result = _resolve(description)
    assert result is not None, f"expected a mapping for {description!r}"
    return result[0], result[1]


# --- Real wording that SHOULD map to a canonical code ---------------------- #


def test_real_lab_wording_resolves() -> None:
    assert _code("Complete Blood Count with Differential") == ("85025", "CPT")
    assert _code("Basic Metabolic Panel") == ("80048", "CPT")
    assert _code("Lipid panel") == ("80061", "CPT")
    assert _code("Lipid Pnl") == ("80061", "CPT")
    assert _code("Hemoglobin A1c (Glycosylated)") == ("83036", "CPT")
    assert _code("Hemoglobin A1c POC") == ("83036", "CPT")
    assert _code("Urinalysis w Microscopy") == ("81001", "CPT")


def test_real_bone_density_axial_resolves() -> None:
    assert _code("BD Bone Density DEXA Axial Skeleton - BD Bone Dens") == ("77080", "CPT")


def test_real_colonoscopy_wording_resolves() -> None:
    assert _code("COLONOSCOPY") == ("45378", "CPT")
    assert _code("COLONOSCOPY AND BIOPSY") == ("45380", "CPT")
    assert _code("COLONOSCOPY & POLYPECTOMY") == ("45385", "CPT")


# --- Lookalikes that MUST NOT map (safety) --------------------------------- #


def test_dexamethasone_drug_does_not_map_to_bone_density() -> None:
    # The fix: 'dexa' must be word-bounded so it never matches 'dexamethasone'.
    assert _resolve("dexAMETHasone 0.5 mg Tab") is None
    assert _resolve("dexamethasone 0.1% Ophth Soln 5 mL") is None
    assert _resolve("ciprofloxacin-dexamethasone Otic Susp 7.5 mL") is None


def test_lipid_drug_does_not_map_to_lipid_panel() -> None:
    assert _resolve("fat emulsion, IV 20% SMOFlipid 100 ml Premix") is None
    assert _resolve("perflutren (lipid microspheres) IV Susp 1.5 mL") is None


def test_catheter_brand_does_not_map_to_mri() -> None:
    # 'MRINER' catheter brand contains 'mri' but is not an MRI procedure.
    assert _resolve("CATH ANGIO 110CM 5FR MRINER BRNSTN CRV DRTN HDRPH") is None
    assert _resolve("CATH BLNDIL 1.5MM 142CM 12MM RPDX ELONGATE TIP MRI") is None


def test_unlisted_colonoscopy_variants_do_not_map_to_diagnostic() -> None:
    # Different CPTs we do not map — anchored patterns must not catch them.
    assert _resolve("COLONOSCOPY W/BALLOON DILAT") is None
    assert _resolve("COLONOSCOPY W/BAND LIGATION") is None
    assert _resolve("COLONOSCOPY SUBMUCOUS NJX") is None
