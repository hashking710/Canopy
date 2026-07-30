from canopy_agent.compliance_rules.base import HomeGrowRules, PlantLimit, PurchaseLimit, RetailRules, StateComplianceRules

RULES = StateComplianceRules(
    state_code="AZ",
    state_name="Arizona",
    platform="none",
    platform_confidence="secondary_source",  # converged independently across several industry vendor sites
    tagging_trigger_kind="no_trigger_found",
    tagging_trigger_value=(
        "R9-17-316 and R9-18-314 (dispensary/establishment inventory control, read directly) require only "
        "batch-level documentation (batch number, seeds/cuttings planted, plants grown to maturity, "
        "disposal records) — never an individual plant tag or RFID"
    ),
    tagging_trigger_confidence="primary_source",  # Ariz. Admin. Code R9-17-316 and R9-18-314, read directly
    deadline_kind="no_deadline_found",
    deadline_value=None,
    deadline_confidence="primary_source",  # R9-17-316 and R9-18-314 read directly: disposal must be
    # documented (date, method, reason, agent) but no deadline by which disposal must occur is stated
    reconciliation_cadence_days=30,
    reconciliation_confidence="primary_source",  # R9-17-316(D)/R9-18-314(D), read directly: "conduct and
    # document an audit of the inventory ... at least once every 30 calendar days" — framed as a GAAP-style
    # inventory audit, not explicitly a physical plant headcount the way Colorado's rule is; treat as the
    # closest primary-sourced analog rather than an exact match in kind
    testing_required_for_solvent_extracts=True,
    testing_confidence="primary_source",  # Ariz. Admin. Code R9-17-317.01 and R9-17-404.03, regulation text read directly
    testing_note=(
        "R9-17-317.01 requires every batch of medical marijuana/marijuana product to be tested per "
        "R9-17-404.03, R9-17-404.04, and Table 3.1 before sale/dispensing; R9-17-404.03 establishes "
        "'residual solvents' as a required chemical-analyte category with its own acceptance criteria. "
        "Table 3.1 itself (which lists which analytes apply to which product type) was not obtained "
        "directly, so the concentrate-specific analyte list is inferred rather than confirmed verbatim."
    ),
    home_grow=HomeGrowRules(
        recreational_allowed=True,
        recreational_limit=PlantLimit(6, "per_person", "12 plants per household cap; no distance restriction (Prop 207)"),
        medical_allowed=True,
        medical_limit=PlantLimit(12, "per_patient", "AMMA — legal ONLY if living more than 25 miles from a licensed dispensary"),
        extended_medical_available=False,
        extended_medical_limit=None,
        extended_medical_note=(
            "RESOLVED: no enhanced/hardship cultivation tier exists in the AMMA. A designated caregiver's "
            "cultivation allowance is not a distinct higher ceiling — A.R.S. §36-2801(1)(b), read directly, "
            "grants a caregiver the same 12-plant allowance as a qualifying patient, but 'for each patient "
            "assisted,' up to the 5-patient cap in §36-2801(5)(d). This is per-patient replication of the "
            "base limit (so a caregiver serving 5 patients could have up to 60 plants total, split across "
            "each patient's own 12-plant allowance), not a separate enhanced category like Colorado's "
            "numbered Extended Plant Count program."
        ),
        caregiver_limit=PlantLimit(12, "per_patient", "A.R.S. §36-2801(1)(b) — same 12-plant allowance as a patient, replicated once per patient assisted"),
        caregiver_max_patients=5,  # A.R.S. §36-2801(5)(d), read directly: "not more than five qualifying patients"
        geographic_gate="Medical home cultivation is legal only for patients/caregivers living more than 25 miles from a licensed dispensary (AMMA) — this excludes most Phoenix/Tucson-area patients.",
        confidence="primary_source",  # A.R.S. §36-2852(A)(2) (recreational), §36-2801/§36-2804.02 (medical +
        # 25-mile gate), all read directly at azleg.gov — every figure here confirmed against statute text
        notes="",
    ),
    retail=RetailRules(
        recreational_allowed=True,  # A.R.S. §36-2852(A), read directly at azleg.gov — governs adult (21+) possession/purchase
        recreational_purchase_limits=(
            PurchaseLimit(1.0, "ounces_flower", "per_transaction", "A.R.S. §36-2852(A)(1), read directly: \"one ounce or less of marijuana\" — a possession-limit statute doubling as the de facto purchase cap; Arizona has no separate retailer-side \"shall not sell more than X\" regulation the way CA/CO do"),
            PurchaseLimit(5.0, "grams_concentrate", "per_transaction", "A.R.S. §36-2852(A)(1), read directly: \"not more than five grams ... in the form of marijuana concentrate\" — a sub-limit within, not additional to, the 1oz total"),
        ),
        recreational_min_age=21,  # A.R.S. §36-2852(A), read directly: "at least twenty-one years of age"
        medical_allowed=True,  # A.R.S. §36-2801/§36-2806.02, read directly — AMMA dispensing framework
        medical_purchase_limits=(
            PurchaseLimit(2.5, "ounces_flower", "per_rolling_period", "A.R.S. §36-2801 'allowable amount' definition + §36-2806.02(A)(3), read directly: a qualifying patient may not obtain more than 2.5oz of usable marijuana from dispensaries in any rolling 14-day period. Concentrates count toward this SAME combined cap per State v. Jones, 246 Ariz. 452 (2019) (secondary-sourced, not read directly) — ADHS has adopted no official flower-to-concentrate conversion ratio, so unlike AZ's own recreational statute there's no separate gram-based concentrate sub-limit here"),
        ),
        medical_min_age=None,  # §36-2801 defines "qualifying patient" with no age floor; a minor can qualify
        # with two physician certifications and a custodial parent/guardian who consents in writing and
        # controls acquisition/dosage (secondary-sourced — a direct fetch of §36-2804.02's minor-patient
        # subsection didn't return that text; worth a follow-up confirmation pass)
        id_verification_required=True,
        id_verification_note=(
            "Medical: A.R.S. §36-2806.02(A)(1)-(2), read directly: dispensary agent must verify \"the "
            "registry identification card ... is valid\" and that \"each person presenting a registry "
            "identification card is the person identified on\" it — primary_source. Recreational: §36-2854"
            "(A)(6), read directly, only delegates rulemaking for acceptable ID forms (cross-referencing "
            "§4-241) — the actual \"agent must verify\" duty came from a secondary source, not confirmed at "
            "this specific subsection."
        ),
        pos_realtime_sync_required=False,
        pos_realtime_sync_note=(
            "Medical: True, primary_source — A.R.S. §36-2806.02(B), read directly: \"Before dispensing "
            "marijuana ... a dispensary agent shall ... enter\" sale info into \"the verification system\" — "
            "entry required BEFORE dispensing, i.e. real-time/at-sale. Recreational: False, secondary_source "
            "— §36-2854(A)(4), read directly, only requires a tracking system \"at all points of cultivation, "
            "manufacturing and sale\" with no real-time/at-time-of-sale language, consistent with this "
            "project's existing cultivation-side finding that Arizona has NO state-mandated seed-to-sale "
            "platform at all. The overall field below is False because it can't uniformly claim True across "
            "both markets — see this note for the real medical/recreational split."
        ),
        confidence="secondary_source",  # most figures are primary_source; the recreational ID-verification
        # duty clause, the medical age-floor minor-patient provision, and the Jones/no-conversion-ratio
        # nuance are secondary — aggregate reflects those real gaps rather than rounding up
        notes="Medical and recreational answers genuinely differ for id_verification/pos_realtime_sync (schema has one field per state) — see each field's *_note for the actual split rather than a single blended number.",
    ),
    notes=(
        "Most consequential platform finding of this research pass: Arizona has "
        "NO state-mandated seed-to-sale software at all. Licensees self-report "
        "using their own systems; the state's 'Marijuana Licensing Management "
        "System' only handles the patient/caregiver registry and dispensary "
        "sales-history verification, not plant-level traceability. There is no "
        "METRC or BioTrack integration surface to build against for Arizona — "
        "any future compliance_sync implementation for this state would need an "
        "entirely different design than the METRC-shaped interface this project "
        "currently has."
    ),
)
