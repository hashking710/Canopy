from canopy_agent.compliance_rules.base import HomeGrowRules, PlantLimit, PurchaseLimit, RetailRules, StateComplianceRules

RULES = StateComplianceRules(
    state_code="MO",
    state_name="Missouri",
    platform="metrc",
    platform_confidence="secondary_source",
    tagging_trigger_kind="size",
    tagging_trigger_value="immature plant reaches 8 inches tall OR 8 inches wide (19 CSR 100-1.130(1)(E)1; term defined at 19 CSR 100-1.010(40))",
    tagging_trigger_confidence="primary_source",  # 19 CSR 100-1.130(1)(E)1, read directly: "All immature
    # plants at least eight (8) inches tall or eight (8) inches wide shall be tagged with traceability
    # information." Definition at 19 CSR 100-1.010(40): "'Immature plant' means a non-flowering marijuana
    # plant that is neither taller than eight (8) inches nor wider than eight (8) inches."
    deadline_kind="no_deadline_found",
    deadline_value=None,
    deadline_confidence="primary_source",  # 19 CSR 100-1.150 read directly — logging + 5-year retention required, no deadline
    reconciliation_cadence_days=30,
    reconciliation_confidence="primary_source",  # 19 CSR 100-1.130(1)(I), read directly: "Licensees must
    # provide to the department a monthly physical inventory report that includes all adjustments and
    # adjustment reasons and that demonstrates the physical inventory reconciles with the inventory recorded
    # in the state-wide track and trace system."
    testing_required_for_solvent_extracts=True,
    testing_confidence="primary_source",  # 19 CSR 100-1.110, regulation text read directly
    testing_note=(
        "19 CSR 100-1.110, read directly: mandatory pre-sale contaminant testing includes residual "
        "solvents, with a specific failure-threshold table (e.g. benzene >1 ppm, butanes >800 ppm, "
        "ethanol >1000 ppm). Failed residual-solvent results may be remediated via a purging process."
    ),
    home_grow=HomeGrowRules(
        recreational_allowed=True,
        recreational_limit=PlantLimit(6, "per_person", "flowering plants; registration-card-based (not an unconditional right); plus equal non-flowering allowances, see notes"),
        medical_allowed=True,
        medical_limit=PlantLimit(6, "per_person", "same limit as adult-use registration — Missouri doesn't split limits by registration type; plus equal non-flowering allowances, see notes"),
        extended_medical_available=False,
        extended_medical_limit=None,
        extended_medical_note="No separate enhanced tier beyond caregiver stacking below.",
        caregiver_limit=PlantLimit(24, "per_caregiver", "flowering plants, hard cap regardless of number of patients served; plus equal non-flowering allowances, see notes"),
        caregiver_max_patients=None,
        geographic_gate=None,
        confidence="primary_source",  # 19 CSR 100-1.040(5)(A) (6-plant unified figure) and (5)(J)2
        # (24-plant multi-patient caregiver cap), read directly at sos.mo.gov — the Division of Cannabis
        # Regulation's own promulgated rule, a stronger source for operational limits than the Constitution's
        # rulemaking-authority language previously cited
        notes=(
            "Cultivation is registration-card-based, open to 'consumer, patient, or primary caregiver' alike "
            "under one unified flowering-plant limit — 19 CSR 100-1.040(5)(A), read directly: up to 6 "
            "flowering plants (24 for a caregiver serving 2+ patients, per (5)(J)2). The rule also grants "
            "equal additional NON-flowering allowances not previously modeled here: 6 more plants >=14in "
            "tall/wide, plus 6 more <14in, per grower (24+24 for multi-patient caregivers) — so total "
            "plants-on-premises are effectively 3x the flowering-only figures above (18 total for "
            "individuals, 72 total for multi-patient caregivers). The PlantLimit fields above record only "
            "the flowering-plant figure, consistent with every other state in this file; the fuller "
            "allowance is noted here rather than modeled, since this project's schema is a single count per "
            "grower category, not a 3-tier breakdown."
        ),
    ),
    retail=RetailRules(
        recreational_allowed=True,  # 19 CSR 100-1.180(1)(A)6, read directly, explicitly distinguishes
        # "consumers" (recreational) from "qualifying patients or primary caregivers" (medical) as separate
        # buyer classes a dispensary sells to
        recreational_purchase_limits=(
            PurchaseLimit(3, "ounces_flower", "per_transaction", "19 CSR 100-1.180(2)(C)1, read directly: \"may not sell ... to a consumer more than three (3) ounces of dried, unprocessed marijuana, or its equivalent, in a single transaction\"; constitutional floor at Mo. Const. Art. XIV §2.4(1)(m) confirms 3oz as the minimum this may be set at"),
        ),
        recreational_min_age=21,  # 19 CSR 100-1.180(2)(D)2(C)(III), read directly: "All consumers are at
        # least twenty-one (21) years of age"
        medical_allowed=True,
        medical_purchase_limits=(
            PurchaseLimit(6, "ounces_flower", "per_rolling_period", "19 CSR 100-1.040, default absent a higher physician/NP-certified amount — 6oz/30-day period; the exact subsection designator for this figure could not be independently re-fetched as raw text (WebFetch summary only), treat the citation number as secondary_source-strength even though the 6oz/30-day figure itself is well corroborated"),
        ),
        medical_min_age=18,  # 19 CSR 100-1.180(2)(D)2(C)(I)-(II), read directly: "Patients ... are at least
        # eighteen (18) years of age or are emancipated individuals under the age of eighteen (18); or ...
        # Patients under the age of eighteen (18) have a primary caregiver who is making the acquisition on
        # their behalf" — a minor patient buys via caregiver, not a hard floor on who may BE a patient
        id_verification_required=True,
        id_verification_note=(
            "19 CSR 100-1.180(2)(D)2(C), read directly: dispensary must \"require production of a qualifying "
            "patient or primary caregiver identification card if applicable ... a valid (not expired) "
            "government-issued photo ID, and in the case of marijuana plant purchases, a cultivation "
            "identification card.\" Mo. Const. Art. XIV §2.7(4) separately limits what ELSE can be demanded: "
            "\"may not ... require a consumer to provide ... identifying information other than "
            "identification to determine the consumer's age.\""
        ),
        pos_realtime_sync_required=True,
        pos_realtime_sync_note=(
            "19 CSR 100-1.180(2)(D)2, read directly, explicit \"at the time of sale\" language: \"At the time "
            "of sale or distribution, licensees must— A. Verify through the state-wide track and trace system "
            "that— (I) Qualifying patients or primary caregivers ... are currently authorized ... (II) "
            "Consumers purchasing marijuana product do not exceed the purchase limits...\" and \"F. Record the "
            "disbursement of marijuana product ... in the state-wide track and trace system, even in "
            "instances where prices are discounted or waived.\" One of the clearest real-time-sync statements "
            "found across any state researched."
        ),
        confidence="primary_source",  # every fact above read directly except the exact medical
        # purchase-limit subsection designator (see that field's note) — aggregate reflects the one gap
        notes="",
    ),
    notes="",
)
