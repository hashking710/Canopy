from canopy_agent.compliance_rules.base import HomeGrowRules, PlantLimit, PurchaseLimit, RetailRules, StateComplianceRules

RULES = StateComplianceRules(
    state_code="IL",
    state_name="Illinois",
    platform="metrc",
    platform_confidence="secondary_source",  # cannabis.illinois.gov's official seed-to-sale tracking page,
    # fetched directly, gives an exact phased migration schedule off BioTrackTHC (all licensees transitioned
    # by June 17 2025; BioTrack decommissioned, METRC official as of July 1 2025) — a real agency page, but
    # 8 Ill. Adm. Code §1300.10's own definition of "Cannabis Plant Monitoring System" is deliberately
    # vendor-agnostic and names neither METRC nor BioTrackTHC, so this can't reach primary_source via reg text
    tagging_trigger_kind="size",
    tagging_trigger_value=(
        "individual tag required once any part of the plant reaches 16 inches in height (soil/growing "
        "medium to highest point); below that, plants may be grouped under a single batch tag"
    ),
    tagging_trigger_confidence="primary_source",  # 8 Ill. Adm. Code §1300.1020, read directly (effective
    # date May 1, 2026 per the fetched text — current post-METRC-migration rule, not stale BioTrack-era text)
    deadline_kind="pre_destruction_notice_days",
    deadline_value=7,
    deadline_confidence="primary_source",  # 8 Ill. Adm. Code §1300.810(b), read directly: "A cultivation
    # center, craft grower, or infuser shall provide the Department and ISP a minimum of 7 days' notice
    # prior to rendering the product unusable and disposing of the product."
    reconciliation_cadence_days=7,
    reconciliation_confidence="primary_source",  # 8 Ill. Adm. Code §1300.180(b), read directly: "Upon
    # commencing business, each cultivation center shall conduct a physical weekly inventory of cannabis
    # stock" (corroborated by near-identical text at §1300.102(d)(7)); §1300.180(d) separately requires an
    # annual comprehensive inventory
    testing_required_for_solvent_extracts=True,
    testing_confidence="primary_source",  # 8 Ill. Adm. Code §1300.700, regulation text read directly
    testing_note=(
        "§1300.700 sets 'residue solvent test' limits (differentiated for products intended for "
        "inhalation vs. not) as part of mandatory pre-sale batch testing; a batch that fails other tests "
        "may still be used to make a CO2- or solvent-based extract, but 'the CO2 or solvent based extract "
        "must still pass all required tests' before it can be sold."
    ),
    home_grow=HomeGrowRules(
        recreational_allowed=False,
        recreational_limit=None,
        medical_allowed=True,
        medical_limit=PlantLimit(5, "per_residence", "only plants over 5in tall count toward the limit"),
        extended_medical_available=False,
        extended_medical_limit=None,
        extended_medical_note="No enhanced/caregiver cultivation tier identified.",
        caregiver_limit=None,
        caregiver_max_patients=None,
        geographic_gate=None,
        confidence="primary_source",  # 410 ILCS 705/10-5, read directly at ilga.gov (the earlier 404 was
        # transient — the ILCS page loaded fine on retry): confirms the medical-only, 5-plant/residence,
        # >5in-tall figures exactly as modeled, and confirms no adult-use home grow exists (patient-gated)
        notes="No adult-use home cultivation exists at all — commercial-only recreational market, confirmed directly against 410 ILCS 705/10-5.",
    ),
    retail=RetailRules(
        recreational_allowed=True,  # 68 Ill. Adm. Code Part 1291 ("Adult Use Cannabis Dispensing
        # Organizations"), read directly — legal adult-use RETAIL since 2020, despite NO adult-use home
        # cultivation (see home_grow above) — the two facts are independent, not conflated here
        recreational_purchase_limits=(
            PurchaseLimit(60, "grams_flower", "per_rolling_period", "410 ILCS 705/10-10(a), read directly: resident cumulative possession cap enforced continuously via track-and-trace against a standing limit, not reset daily/per-transaction — per_rolling_period is the closest schema fit; non-residents capped at 30g"),
            PurchaseLimit(10, "grams_concentrate", "per_rolling_period", "410 ILCS 705/10-10(a), read directly; non-residents capped at 5g"),
            PurchaseLimit(1000, "mg_thc_edible", "per_rolling_period", "410 ILCS 705/10-10(a), read directly; non-residents capped at 500mg"),
        ),
        recreational_min_age=21,  # 410 ILCS 705/10-10(a) and 68 Ill. Adm. Code 1291.301(a), both read
        # directly: "no persons under the age of 21 shall be allowed entry into a dispensing organization"
        medical_allowed=True,
        medical_purchase_limits=(
            PurchaseLimit(70.87, "grams_flower_equivalent", "per_rolling_period", "410 ILCS 130/10(a), read directly: \"'Adequate medical supply' means 2.5 ounces of usable cannabis during a period of 14 days\" (2.5oz = 70.87g), waiver-adjustable by a certifying provider"),
        ),
        medical_min_age=None,  # no statutory age floor found — minors are permitted as qualifying patients
        # with a parent/guardian caregiver (1291.301(a) carve-out; 410 ILCS 130/10(i) caregiver definition
        # explicitly covers parents of multiple minor patient-children; an official agency PDF confirms minor
        # patients are limited to cannabis-infused products only — secondary-sourced, not exhaustively
        # verified against every minor-specific provision)
        id_verification_required=True,
        id_verification_note=(
            "68 Ill. Adm. Code 1291.301(b)-(e), read directly (full Part 1291 text fetched via ilga.gov "
            "JCAR EntirePart endpoint): \"Each dispensing organization is responsible for checking and "
            "verifying customer identification prior to any customer entering the limited access area\"; "
            "\"shall use an electronic reader or electronic scanning device to scan a purchaser's "
            "government-issued identification if scanning is possible ... in accordance with Section 10-20 "
            "of the Act.\""
        ),
        pos_realtime_sync_required=True,
        pos_realtime_sync_note=(
            "68 Ill. Adm. Code 1291.310(a)-(c), read directly: \"The inventory Point of Sale System shall be "
            "real-time, web-based and accessible by the Department 24 hours a day, seven days a week\"; the "
            "State Verification System account documents \"Each sales transaction at the time of sale\"; "
            "dispensary \"shall use a point of sale system that establishes and maintains an interface with "
            "the State Verification System to track the sale of cannabis.\" The most explicit \"real-time\" "
            "language found across any state researched."
        ),
        confidence="primary_source",  # every fact read directly except the medical minor-patient carve-out
        # (secondary_source) — aggregate reflects that one soft spot
        notes="Purchase-limit period doesn't cleanly fit the schema's three per_transaction/per_day/per_rolling_period options — Illinois enforces a standing cumulative possession cap continuously via track-and-trace, not a cap that resets on a fixed cadence; per_rolling_period is the closest available fit, flagged here for a maintainer.",
    ),
    notes=(
        "Platform history, now confirmed directly (not just referenced in search "
        "results): cannabis.illinois.gov's official seed-to-sale tracking page gives "
        "an exact phased migration schedule off BioTrackTHC — transporters/labs "
        "Apr 1-18 2025, cultivators/infusers Apr 25-May 25 2025, all licensees "
        "transitioned by June 17 2025, BioTrack decommissioned and METRC official as "
        "of July 1 2025. Any integration work or historical data predating that "
        "window would have needed a BioTrack client, not a METRC one — confirms "
        "platform is a real per-state variable, not a safe assumption. Waste deadline "
        "is a pre-destruction NOTICE requirement to the Department and Illinois State "
        "Police (like Ohio's shape), not a post-destruction report — 7 days' advance "
        "notice, per §1300.810(b) read directly."
    ),
)
