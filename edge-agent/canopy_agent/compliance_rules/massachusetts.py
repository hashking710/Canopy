from canopy_agent.compliance_rules.base import HomeGrowRules, PlantLimit, PurchaseLimit, RetailRules, StateComplianceRules

RULES = StateComplianceRules(
    state_code="MA",
    state_name="Massachusetts",
    platform="metrc",
    platform_confidence="secondary_source",  # in use since 2018 per industry sources
    tagging_trigger_kind="immediate",
    tagging_trigger_value="935 CMR 500.105(8)(e) — plant tags attached to all plants and clones, not gated by a growth-stage or size transition",
    tagging_trigger_confidence="primary_source",  # 935 CMR 500.105(8)(e), read directly: "A Marijuana
    # Establishment shall attach plant tags to all Marijuana, Clones, and plants ... using a Seed-to-sale
    # methodology" — no untagged-batch-then-tagged-at-a-threshold model, same "immediate" shape as Maryland
    deadline_kind="no_deadline_found",
    deadline_value=None,
    deadline_confidence="primary_source",  # 935 CMR 500.105(12) read directly — no waste-specific deadline
    # found there. RE-CONFIRMED against the current 935 CMR 500 PDF (dated 4/24/2026, fetched via curl +
    # pdftotext after WebFetch couldn't parse it directly): subsection (12)(a)-(d) read in full, still no
    # hour/day deadline anywhere — the "couldn't rule out a recent amendment" caveat from a prior pass is
    # now closed.
    reconciliation_cadence_days=30,
    reconciliation_confidence="primary_source",  # 935 CMR 500.105(8)(c)(2), read directly: "Conduct a
    # monthly inventory of Marijuana in the process of cultivation and finished, stored Marijuana" (8)(c)(3)
    # separately requires a comprehensive annual inventory ("monthly", not a literal 30-day figure).
    # Re-confirmed verbatim-unchanged against the current 4/24/2026 PDF revision.
    testing_required_for_solvent_extracts=True,
    testing_confidence="secondary_source",  # CCC Protocol for Sampling and Analysis of Finished Marijuana Products, §7.5, read directly — not the CMR text itself
    testing_note=(
        "935 CMR 500.160 (read directly) requires testing for contaminants but does not itself name "
        "residual solvents; the Commission's incorporated Protocol document, §7.5 (read directly), fills "
        "that in: 'residual solvents testing is required only for Cannabis resins and concentrates where "
        "solvents have been used in the production process' — a licensee is not required to test for "
        "residual solvents if it can document no solvents were used."
    ),
    home_grow=HomeGrowRules(
        recreational_allowed=True,
        recreational_limit=PlantLimit(6, "per_person", "12 plants per household cap"),
        medical_allowed=False,
        medical_limit=None,
        extended_medical_available=True,
        extended_medical_limit=None,
        extended_medical_note=(
            "A 'Hardship Cultivation Registration' exists as the enhanced/patient-adjacent category "
            "(935 CMR 501.027, read directly) — yield-based ('cultivate a limited number of plants "
            "sufficient to maintain a 60-day Supply'), not a plant count, so it doesn't fit this project's "
            "count-based model. Without the registration, patients are capped at 12 flowering + 12 "
            "vegetative plants (excluding clones), also per 501.027. CONFIRMED (was previously unverified): "
            "the CCC's own official site states in present tense that 'The Commission has not yet "
            "implemented the Hardship Cultivation Registration program' — it remains non-operational."
        ),
        caregiver_limit=None,
        caregiver_max_patients=None,
        geographic_gate=None,
        confidence="secondary_source",  # the program's existence/shape (935 CMR 501.027) is primary-sourced;
        # its current non-operational status is confirmed only via the CCC's official webpage (agency
        # page, not codified regulation text), so the aggregate stays secondary_source
        notes="No standard medical home-grow track exists — medical patients use licensed dispensaries (MTCs) or the adult-use allowance above.",
    ),
    retail=RetailRules(
        recreational_allowed=True,  # 935 CMR 500 (adult-use regime), read directly
        recreational_purchase_limits=(
            PurchaseLimit(2, "ounces_flower", "per_day", "CORRECTED this pass: the prior '1oz, confirmed against a 4/24/2026 PDF' finding was overtaken by events roughly contemporaneously — Gov. Healey signed H.5350 ('An Act Modernizing the Commonwealth's Cannabis Laws') on 4/19/2026, and the Cannabis Control Commission's own Bulletin No. 1 (masscannabiscontrol.com, dated 4/17/2026, read directly) states the possession/purchase limit for adults 21+ 'increases from 1 ounce to 2 ounces, or its equivalent in Marijuana concentrate, as the result of a licensed sale or gifting,' effective immediately upon signature per the official mass.gov press release ('Governor Healey Signs Cannabis Reform Legislation'). Treated as primary_source: this is the Commission's own official bulletin implementing an enacted, signed law, not a search-summary or vendor blog — but the underlying CMR 500.140 text itself may not be reprinted yet, since the Commission's bulletin explicitly says new regulations codifying the conversion standards are still to be promulgated; a maintainer should re-confirm 935 CMR 500.140's literal text once that rulemaking completes"),
            PurchaseLimit(10, "grams_concentrate", "per_day", "CCC Bulletin No. 1 (4/17/2026), read directly: '2 ounces of Marijuana flower should be understood to be equivalent to ... 10 grams of active THC in Marijuana concentrate' — doubled from the prior 5g figure, same primary_source basis as the flower limit above"),
            PurchaseLimit(1000, "mg_thc_edible", "per_day", "CCC Bulletin No. 1 (4/17/2026), read directly: '...1,000 mg of active THC in edibles' — doubled from the prior 500mg figure, same primary_source basis as the flower limit above"),
        ),
        recreational_min_age=21,  # 935 CMR 500.140(2)(a), read directly: "An individual shall not be
        # admitted to the Premises, unless the Marijuana Retailer has verified that the individual is 21
        # years of age or older"
        medical_allowed=True,  # 935 CMR 501 (medical regime), read directly — note this differs from the
        # home_grow section above (medical_allowed=False there means no home-CULTIVATION track; retail
        # medical purchasing is a separate, real, legal channel)
        medical_purchase_limits=(
            PurchaseLimit(10, "ounces_flower", "per_rolling_period", "935 CMR 501.002 & 501.140(3), read directly: \"60-day Supply ... which is ten ounces,\" provider-adjustable, MTC may not dispense beyond it in any 60-day window"),
        ),
        medical_min_age=None,  # 935 CMR 501 definitions, read directly, explicitly contemplate patients
        # "younger than 18 years old who has been diagnosed by two Massachusetts ... physicians"; such a
        # patient "cannot enter an MTC without their Caregiver" (§501.140(2)(a)(4)) and needs no separate ID
        # (§501.140(2)(a)(3)) — the caregiver themselves must be 21+
        id_verification_required=True,
        id_verification_note=(
            "Adult-use: 935 CMR 500.140(2)(a)-(b) & (4)(a), read directly: ID inspected both on entry and "
            "again at point-of-sale; retailer 'shall refuse to sell Marijuana to any Consumer who is unable "
            "to produce valid proof of government-issued identification.' Medical: 935 CMR 501.140(2)(a), "
            "read directly: Registration Card + govt ID inspected on entry (driver's license, govt ID card, "
            "military ID, passport accepted)."
        ),
        pos_realtime_sync_required=True,
        pos_realtime_sync_note=(
            "935 CMR 500.105(8)(b), read directly (applies to retailers via §500.140(1)'s incorporation): "
            "'Real-time inventory shall be maintained as specified by the Commission.' §500.140(3)(c), read "
            "directly: retailer 'shall demonstrate that it has a point-of-sale system that does not allow "
            "for a transaction in excess of the limit' — operationally requires the POS to know the "
            "customer's running daily total in real time to block over-limit sales. The medical side "
            "(§501.140(5)) uses an identical POS structure by cross-reference. The 'real-time' language "
            "attaches to inventory generically rather than a standalone 'record every sale within N seconds' "
            "clause, but combined with the transaction-blocking requirement this is a solid finding."
        ),
        confidence="primary_source",  # every fact read directly from the current 935 CMR 500/501 PDFs or, for
        # the 2026 purchase-limit increase, the CCC's own official bulletin implementing signed legislation —
        # see the flower-limit field's note for the full correction story
        notes="",
    ),
    notes=(
        "935 CMR 500.105, read directly: no waste-specific reporting deadline "
        "found. That section does set a 24-hour deadline, but for reporting an "
        "'unusual discrepancy in weight, count, or inventory' — a different "
        "obligation than routine waste destruction, not the same rule. Waste "
        "destruction requires witnessing and 3-year recordkeeping (structurally "
        "similar to this project's existing witnessed_by field) — CORRECTED this "
        "pass: the witness requirement is now 1 agent, not 2. 500.105(12)(d) in the "
        "current (4/24/2026) regulation text reads 'A Marijuana Establishment Agent "
        "shall witness...' (singular); a CCC bulletin corroborates this was a "
        "deliberate 2026 Regulatory Reform ('Licensees may reduce the number of "
        "Registered Agents from two to one for waste disposal witnessing,' eff. Jan "
        "2, 2026) — Cornell LII's mirror still shows the old 2-agent text and is "
        "stale. Tagging-trigger model RESOLVED in a prior pass (was previously the "
        "most significant open question for this state): Massachusetts does not use "
        "California's untagged-batch-then-individually-tagged-at-a-phase-transition "
        "model, nor Michigan/Missouri's size-threshold model — 500.105(8)(e), read "
        "directly, requires plant tags on all plants and clones with no threshold "
        "gating when tagging kicks in, the same 'immediate' shape found in Maryland."
    ),
)
