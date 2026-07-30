from canopy_agent.compliance_rules.base import HomeGrowRules, PlantLimit, PurchaseLimit, RetailRules, StateComplianceRules

RULES = StateComplianceRules(
    state_code="NV",
    state_name="Nevada",
    platform="metrc",
    platform_confidence="secondary_source",
    tagging_trigger_kind="phase",
    tagging_trigger_value=(
        "Nevada defines 'mature cannabis plant' as one with flowers/buds readily observable by unaided "
        "visual examination (NCCR 1.245) — phase-based, unlike MI/MO's size-based 8in threshold. NCCR text "
        "does not explicitly state that reaching 'mature' is what triggers individual METRC tagging vs. "
        "batch tracking — that specific operational link isn't present in the primary regulation text"
    ),
    tagging_trigger_confidence="secondary_source",  # NCCR 1.245, read directly, confirms the phase-based
    # maturity definition itself; NCCR 6.082(4) and 4.050(1)(a)(4) reference plant tagging without stating
    # the trigger threshold in the regulation text — that operational detail appears to live in METRC's own
    # system requirements, external to NCCR, so the tagging-trigger claim specifically can't reach primary.
    # SECOND ATTEMPT made (checked ccb.nv.gov/guidance/ and metrc.com/faq/nevada-faq/ directly for a CCB
    # METRC user guide/bulletin that might state the trigger explicitly) — neither exists as a fetchable,
    # independently-verifiable primary/official document; a plausible-sounding claim only ever appeared in
    # aggregated search-snippet form, never on a page that could be confirmed directly. Genuinely
    # could-not-verify-further, not a missed source.
    deadline_kind="pre_destruction_notice_days",
    deadline_value=None,  # shape confirmed, but the rule specifies no minimum day-count — see comment below
    deadline_confidence="primary_source",  # NCCR 10.080(4), read directly: "A cannabis establishment shall
    # provide notice to the Board using the seed-to-sale tracking system before rendering unusable and
    # disposing of cannabis or cannabis products." No number of days is specified anywhere in the section —
    # re-confirmed against the current consolidated NCCR text (Rev. 03/23, amended through Jan 2023),
    # superseding the "current as of July 1 2020" version originally checked. The widely-repeated "24 hour"
    # figure for Nevada appears only in generic vendor marketing with no citable rule behind it — treat it
    # as unverified/likely wrong, same conclusion as Oklahoma's.
    reconciliation_cadence_days=90,
    reconciliation_confidence="primary_source",  # NCCR 6.080(8)(c), read directly: "Provide for quarterly
    # physical inventory counts to be performed by persons independent of the manufacturing process which
    # are reconciled to the perpetual inventory records. Significant variances must be documented,
    # investigated by management personnel and immediately reported to the Executive Director."
    testing_required_for_solvent_extracts=True,
    testing_confidence="primary_source",  # NAC 453D.780, regulation text read directly
    testing_note=(
        "NAC 453D.780, read directly: 'Extract of marijuana (solvent-based) made with any approved "
        "solvent' requires a 'Residual solvent test' with a tolerance limit of <500 ppm before release "
        "from the testing facility."
    ),
    home_grow=HomeGrowRules(
        recreational_allowed=True,
        recreational_limit=PlantLimit(6, "per_person", "12 plants per household; legal ONLY if living more than 25 miles from a licensed dispensary"),
        medical_allowed=True,
        medical_limit=PlantLimit(12, "per_patient", "combined pool shared by patient + caregiver together, not per-patient-alone — NRS 678C.200(3)(b); no mature/immature split; same 25-mile distance gate as adult-use"),
        extended_medical_available=False,
        extended_medical_limit=None,
        extended_medical_note="No enhanced tier found.",
        caregiver_limit=None,  # RESOLVED, real correction: no separate/additional caregiver cultivation
        # allowance exists in current law. The previously-modeled 18-plant figure has zero support anywhere
        # in current Nevada statute — see notes. The 12-plant medical_limit above IS the combined
        # patient+caregiver pool, not a patient-only figure with an additional caregiver allowance on top.
        caregiver_max_patients=None,  # RESOLVED: no numeric cap on patients-per-caregiver found anywhere in
        # current law (NRS 678C.270(2) restricts the *patient* to one caregiver at a time — the reverse
        # direction — not how many patients one caregiver may serve). The previously-assumed "1" was unconfirmed.
        geographic_gate="Both adult-use and medical home cultivation are legal only for residents living more than 25 miles from a licensed dispensary — this excludes nearly all of Clark and Washoe counties.",
        confidence="primary_source",  # RESOLVED this pass, both halves of a previously-active dispute now
        # settled with official .gov sourcing — see notes
        notes=(
            "CAREGIVER FIGURE DISPUTE RESOLVED: NRS 453A.200 (the section a prior pass read via a non-.gov "
            "mirror) really WAS repealed — confirmed via the Nevada Legislature's own official 'NRS "
            "Repealed/Replaced' table (leg.state.nv.us/NRSRepealed/R_R033.html): '453A.200 Repealed 2019 "
            "[Page 3896]', chapter 595, Statutes of Nevada 2019. Chapter 453A no longer exists; its "
            "successor is NRS Chapter 678C ('Medical Use of Cannabis'), confirmed via leg.state.nv.us's "
            "current NRS index. NRS 678C.200(3)(b), read directly (fetched 3x for consistency): a registry "
            "cardholder and designated primary caregiver must not 'collectively possess ... more than ... "
            "Twelve cannabis plants, irrespective of whether the cannabis plants are mature or immature' — "
            "the same combined 12-plant figure, now under live statutory text instead of a repealed section. "
            "Every section of current Chapter 678C mentioning 'caregiver' (checked: .040, .200, .210, .220, "
            ".230, .250, .260, .270, .310, .480) was read directly — none states a separate, additional, or "
            "higher plant allowance for a caregiver alone. The previously-modeled 18-plant figure has no "
            "support anywhere in current Nevada law and has been removed rather than repeated."
        ),
    ),
    retail=RetailRules(
        recreational_allowed=True,  # NRS Chapter 678D (adult use), live current chapter, confirmed
        recreational_purchase_limits=(
            PurchaseLimit(2.5, "ounces_flower", "per_transaction", "NRS 678B.550, read directly, effective 1/1/2024 per SB 277 (2023): \"shall not sell to a person, in any one transaction, more than 2.5 ounces of usable cannabis.\" CONFLICT FOUND, flagging rather than silently picking a side: NCCR 7.025 (the administrative rule, last codified in the Rev. 03/23 text this project has) still states an older 1 ounce figure — NRS 678B.550's 2.5oz is the current, controlling, statutorily superior figure (SB 277 postdates that NCCR revision), but the regulation text itself may not have been updated to match. Worth a follow-up check against the CCB's current NCCR PDF."),
            PurchaseLimit(7.1, "grams_concentrate", "per_transaction", "NRS 678B.550, read directly: \"or more than one-fourth of an ounce of concentrated cannabis\" (0.25oz ≈ 7.1g), effective 1/1/2024 per SB 277 — same stale-NCCR-text caveat as the flower figure above (NCCR 7.025 still shows an older 0.125oz/~3.5g figure)"),
        ),
        recreational_min_age=21,  # NRS 678B.545 and NCCR 7.020(1), both read directly
        medical_allowed=True,  # NRS Chapter 678C (medical use), live current chapter, confirmed
        medical_purchase_limits=(
            PurchaseLimit(2.5, "ounces_flower", "per_transaction", "Same substantive ceiling as adult-use (NRS 678C.200) — but see pos_realtime_sync_note: Nevada explicitly does NOT mandate POS-level enforcement of this limit for medical sales, an asymmetry with adult-use worth flagging"),
        ),
        medical_min_age=None,  # no fixed floor found — NRS 678C.070 confirms a "letter of approval" can be
        # issued to "an applicant who is under 10 years of age," i.e. minors of any age may qualify via
        # guardian consent; a caregiver must be 18+ (NRS 678C.040(1)(a)), but that's the caregiver, not the patient
        id_verification_required=True,
        id_verification_note=(
            "NRS 678B.545, read directly — a notably specific standard: \"the cannabis establishment agent "
            "shall verify the age of the consumer by checking a government-issued identification that "
            "contains a photograph of the consumer using an identification scanner which has been approved "
            "by an appropriate agent of the Board\" — mandates an APPROVED SCANNER, not just a visual ID "
            "check, matched by NCCR 7.015(1)/7.020 (acceptable ID types: driver's license, state ID, "
            "military ID, Merchant Mariner Credential, passport/green card, tribal ID)."
        ),
        pos_realtime_sync_required=True,
        pos_realtime_sync_note=(
            "NCCR 7.015, read directly, requires a cannabis establishment agent to enter amount/date-time/"
            "agent-registration-number/license-number into the inventory control system as a duty tied to "
            "each sale — but does NOT use an explicit \"immediately\"/\"at the time of sale\" adverb the way "
            "the parallel consumption-lounge rule (NCCR 15.015(4)) does for lounges. A real textual "
            "difference, not assumed equivalence — hence secondary_source rather than Missouri's stronger "
            "primary_source on this same fact. SEPARATE MEDICAL-SPECIFIC ASYMMETRY: NRS 678C.440(2), read "
            "directly: \"A medical cannabis dispensary may, but is not required to, track the purchases of "
            "cannabis for medical purposes by any person to ensure that the person does not exceed the legal "
            "limits ... The Board shall not adopt a regulation or in any other way require a medical cannabis "
            "dispensary to track the purchases of a person.\" So while the substantive limit is the same "
            "figure as adult-use, Nevada explicitly does NOT mandate POS enforcement of it for medical sales."
        ),
        confidence="secondary_source",  # age/ID facts are primary_source; but the purchase-limit figures
        # carry an unresolved statute-vs-regulation-text conflict, and the POS-sync fact lacks the explicit
        # "at time of sale" language found in other states — aggregate reflects both real gaps, not silence
        notes="",
    ),
    notes="",
)
