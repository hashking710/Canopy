from canopy_agent.compliance_rules.base import HomeGrowRules, PlantLimit, PurchaseLimit, RetailRules, StateComplianceRules

RULES = StateComplianceRules(
    state_code="CA",
    state_name="California",
    platform="metrc",
    platform_confidence="secondary_source",  # confirmed absence, not just unexamined: §15000/§15049 (read
    # directly) refer only to "the track and trace system... established by the Department" — DCC
    # regulation text deliberately never names METRC or any vendor, so this can't be upgraded via reg text
    # alone; vendor identity is corroborated only via METRC's own marketing + county government pages
    tagging_trigger_kind="phase",
    tagging_trigger_value="flowering, or moved to the designated canopy area, whichever happens first",
    tagging_trigger_confidence="primary_source",  # Cal. Code Regs. tit. 4, §15048.4(a)(3), read directly:
    # "A plant tag shall be applied to each individual plant ... at the time the plant is moved to the
    # designated canopy area or begins flowering" — a second trigger condition beyond flowering alone
    deadline_kind="hours_after_occurrence",
    deadline_value=24,
    deadline_confidence="primary_source",  # Cal. Code Regs. tit. 4, §15049(b)(5), regulation text read directly
    reconciliation_cadence_days=30,
    reconciliation_confidence="primary_source",  # Cal. Code Regs. tit. 4, §15051(a)(1), read directly: "The
    # licensee shall review the information recorded in the track and trace system at least once every 30
    # calendar days to ensure its accuracy" — reconciling on-hand inventory against system records
    testing_required_for_solvent_extracts=True,
    testing_confidence="primary_source",  # Cal. Code Regs. tit. 4, §15718(a),(d), regulation text read directly
    testing_note=(
        "Residual solvents and processing chemicals testing required on every cannabis product batch; "
        "a batch failing (exceeding Category I/II action levels) 'shall not be released for retail sale' "
        "(§15718(d)). Applies broadly to cannabis products, which includes solvent-extracted concentrates."
    ),
    home_grow=HomeGrowRules(
        recreational_allowed=True,
        recreational_limit=PlantLimit(6, "per_residence", "Health & Safety Code §11362.2 — per residence, not per adult living there"),
        medical_allowed=True,
        medical_limit=PlantLimit(6, "per_patient", "6 mature + 12 immature plants standard allowance — H&S Code §11362.77(a)"),
        extended_medical_available=True,
        extended_medical_limit=None,
        extended_medical_note=(
            "No hard statutory ceiling — a physician may recommend more than the "
            "standard 6/12 split if 'consistent with the patient's [medical] needs' "
            "(H&S Code §11362.77(b), read directly — corrected citation from an "
            "earlier pass's §11362.71, which is registry-card eligibility "
            "definitions, not the plant-count provision). Not a fixed enhanced "
            "tier like Colorado's numbered EPC program, just physician discretion."
        ),
        caregiver_limit=None,
        caregiver_max_patients=None,
        geographic_gate=None,
        confidence="primary_source",  # H&S Code §11362.2(a)(3) (recreational, 6/residence) and §11362.77(a)-(b)
        # (medical, 6 mature + 12 immature + physician-discretion override), both read directly at
        # leginfo.legislature.ca.gov — California's official statute portal
        notes="Recreational: H&S Code §11362.2(a)(3), read directly: \"Not more than six living plants may be planted, cultivated, harvested, dried, or processed within a single private residence... at one time.\" Medical: §11362.77(a)-(b), read directly.",
    ),
    retail=RetailRules(
        recreational_allowed=True,  # Cal. Code Regs. tit. 4, §15404(a), read directly from the official DCC
        # PDF: "A licensed retailer shall only sell adult-use cannabis goods to individuals who are at least
        # 21 years of age"
        recreational_purchase_limits=(
            PurchaseLimit(28.5, "grams_flower", "per_day", "§15409(a)(1), read directly: non-concentrated cannabis"),
            PurchaseLimit(8.0, "grams_concentrate", "per_day", "§15409(a)(2), read directly, including concentrate contained in cannabis products"),
        ),
        recreational_min_age=21,  # §15404(a), read directly
        medical_allowed=True,  # §15404(b), read directly: "shall only sell medicinal cannabis goods to
        # individuals who are at least 18 years of age and possesses a valid physician's recommendation"
        medical_purchase_limits=(
            PurchaseLimit(8.0, "ounces_flower", "per_day", "§15409(b)(1), read directly: dried mature flower or 'the plant conversion as provided in Health and Safety Code section 11362.77'; §15409(c) allows a physician recommendation to override with a documented different amount, §15409(d) bars combining the (a) and (b) limits"),
        ),
        medical_min_age=18,  # §15404(b), read directly
        id_verification_required=True,
        id_verification_note=(
            "§15404(a)-(c), read directly: retailer 'shall only sell ... after confirming the customer's age "
            "and identity by inspecting a valid form of identification,' with (c) listing three acceptable "
            "ID categories (government photo ID, military ID, passport)."
        ),
        pos_realtime_sync_required=False,
        pos_realtime_sync_note=(
            "Cal. Code Regs. tit. 4, §15049(b), read directly from the official DCC PDF: 'Each of the "
            "following activities shall be recorded in the track and trace system within 24 hours of "
            "occurrence,' and (b)(8) explicitly lists 'Sale or donation of cannabis or cannabis products' as "
            "one of those activities — the SAME 24-hour-deadline pattern already established for California's "
            "waste-destruction reporting in the cultivation section (§15049(b)(5)), confirming it's a uniform "
            "24-hour standard across all eight listed activities, not real-time-at-sale. A genuine, "
            "well-sourced correction to any assumption that CA requires live POS sync."
        ),
        confidence="primary_source",  # every fact above read directly from the official DCC-hosted
        # consolidated regulations PDF (cdn.cannabis.ca.gov, Revised Jan. 1, 2026 edition)
        notes="",
    ),
    notes=(
        "This project previously asserted a universal '3 business days' waste "
        "deadline sourced from cannlytics-engine's METRC client code — that figure "
        "did not hold up against the actual regulation text and has been replaced "
        "with the verified 24-hour figure above."
    ),
)
