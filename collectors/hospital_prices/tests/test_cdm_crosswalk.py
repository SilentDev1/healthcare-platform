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


def test_penile_prosthesis_does_not_map_to_chest_xray() -> None:
    # 'CXR' must be word-bounded so it never matches inside '700CXR' (a penile
    # prosthesis model). Real chest x-rays still resolve via chest-2-view wording.
    assert _resolve("PROS PENL AMS 700CXR MS PMP 12CM INFL PRECNCT CYL") is None
    assert _resolve("PROS PENL AMS 700CXR TENACIO 10CM 3 PC PRECNCT INF") is None
    assert _code("XR Chest 2 Views") == ("71046", "CPT")
    assert _code("PF-X-RAY EXAM CHEST 2 VIEWS") == ("71046", "CPT")


def test_esophageal_surgery_does_not_map_to_egd() -> None:
    # 'esophago' is too broad (esophagostomy/esophagomyotomy/esophagoscopy are not
    # an upper endoscopy). Genuine EGDs resolve via the word-bounded 'egd'.
    assert _resolve("PF-Closure of esophagostomy or fistula; cervical approach") is None
    assert _resolve("PF-Esophagomyotomy abdominal") is None
    assert _resolve("Esophagoscopy flexible transnasal diag w/brush/wash") is None
    assert _code("PF-Egd biopsy single/multiple") == ("43235", "CPT")
    assert _code("PF-Egd dilate stricture") == ("43235", "CPT")


def test_fetal_and_pulmonary_stress_do_not_map_to_cardiac_stress() -> None:
    # Fetal non-stress (59025), fetal contraction stress (59020) and pulmonary
    # stress testing are not the cardiac stress test (93015).
    assert _resolve("Fetal non-stress test single gestation(NST) 59025") is None
    assert _resolve("Fetal contraction stress test 59020") is None
    assert _resolve("Non Stress Test (NST), Twin #2") is None
    assert _resolve("PF-PULMONARY STRESS TESTING") is None
    assert _code("ECHO STRESS TEST W/O CONTRAST (STRESS ECHO)") == ("93015", "CPT")
    assert _code("PF-Cardiac drug stress test") == ("93015", "CPT")


def test_revision_arthroplasty_does_not_map_to_primary_replacement() -> None:
    # A revision (or dislocation treatment) is a different procedure/price than the
    # primary total joint replacement.
    assert _resolve("PF-Revision of total knee arthroplasty, w/ or w/o allograft") is None
    assert _resolve("PF-Revision of total hip arthroplasty; both components") is None
    assert _resolve("PF-Closed treatment of post hip arthroplasty dislocation") is None
    assert _code("PF-Total knee arthroplasty") == ("27447", "CPT")
    assert _code("PF-Total hip arthroplasty") == ("27130", "CPT")


def test_sti_thinprep_and_cpap_do_not_map_to_pap_smear() -> None:
    # 'thin prep' alone catches STI tests run on ThinPrep media; 'pap test' inside
    # 'CPAP Test' catches sleep studies. Both must be excluded; real paps resolve.
    assert _resolve("N. gonorrhoeae, Thin Prep") is None
    assert _resolve("Trichomonas vaginalis, Thin Prep") is None
    assert _resolve("Split Night PSG/CPAP Test 95811") is None
    assert _code("Screening Pap Smear Q0091") == ("88175", "CPT")
    assert _code("_SPI 88142 AP Bill Cyto Gyn Thin Prep Screening bilat") == ("88175", "CPT")


def test_drug_and_supply_lines_never_map_to_a_procedure() -> None:
    # Dosage-form / strength signals mean a drug or supply, never a procedure. This
    # catches drug-name collisions the description patterns cannot distinguish, e.g.
    # 'DEXA' as an abbreviation for dexamethasone vs a DEXA bone-density scan.
    assert _resolve("DEXA 4MG TAB") is None
    assert _resolve("DEXAMETHASONE 4 MG TABLET") is None
    assert _resolve("TOBRA/DEXAMETH OPTH SUSP 2.5ML") is None
    assert _resolve("LISDEXAMFETAMIN 40MG CAP") is None
    assert _resolve("CIPROFLOXACIN-DEXAMETHASONE OTIC SUSPENSION") is None
    # Genuine DEXA scans (no dosage form / strength) still resolve.
    assert _code("DEXA Axial Bone Density") == ("77080", "CPT")
    assert _code("BD Bone Density DEXA Axial Skeleton") == ("77080", "CPT")
