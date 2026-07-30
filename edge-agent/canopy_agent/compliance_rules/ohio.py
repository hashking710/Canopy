from canopy_agent.compliance_rules.base import HomeGrowRules, PlantLimit, PurchaseLimit, RetailRules, StateComplianceRules

RULES = StateComplianceRules(
    state_code="OH",
    state_name="Ohio",
    platform="metrc",
    platform_confidence="secondary_source",  # ORC 3796.07, read directly, only generically authorizes "an
    # electronic database" and permits contracting with "a separate entity" to run it — names no vendor;
    # confirmed-negative, not unexamined
    tagging_trigger_kind="size",
    tagging_trigger_value="12 inches in height, or transplant into vegetative/flowering-stage medium, whichever occurs first",
    tagging_trigger_confidence="primary_source",  # OAC 1301:18-5-06(A)(4)(c) (eff. 8/28/2025), read directly.
    # The rule originally cited for this (OAC 3796:2-2-04) has been RESCINDED — Ohio consolidated its
    # medical-only rule chapters (3796:2/3/4/6) into a new unified Title 1301:18 ("Division of Cannabis
    # Control") framework; 1301:18-5-06 is the direct successor, same substantive trigger, relocated.
    deadline_kind="no_deadline_found",
    deadline_value=None,
    deadline_confidence="primary_source",  # CORRECTION, not a renumbering artifact: the previously-cited
    # OAC 3796:6-3-14 (7 days' advance notice) no longer exists in the current Ohio Administrative Code —
    # confirmed via codes.ohio.gov's own "Number Not Found" response, not just a stale third-party mirror.
    # Its direct successor, OAC 1301:18-3-12 ("Waste Disposal," eff. 10/31/2024, all license types), read
    # directly in full, contains no advance-notice requirement anywhere — the obligation appears to have
    # been genuinely dropped in the consolidation, not just relocated. Worth a maintainer sanity-check
    # against the Division of Cannabis Control's own guidance before treating as fully certain, since a
    # requirement disappearing entirely (rather than moving) is the kind of finding worth a second look.
    reconciliation_cadence_days=7,
    reconciliation_confidence="primary_source",  # OAC 1301:18-5-06(A)(4)(d), read directly: "A registered
    # responsible party shall oversee a weekly inventory to ensure the physical inventory matches the
    # information documented in the cultivator's internal inventory system and state inventory tracking
    # system." (An annual comprehensive inventory is separately required as a license-renewal condition.)
    testing_required_for_solvent_extracts=True,
    testing_confidence="primary_source",  # OAC 3796:4-2-04, regulation text read directly and reconfirmed
    # current (unrescinded) as of this pass — the entire 3796:4-2 testing-lab chapter is still intact
    testing_note=(
        "OAC 3796:4-2-04, read directly: finished products containing a hydrocarbon-based extract must be "
        "tested for residual solvents (unless that extract was already tested upstream); CO2-based and "
        "other non-solvent extracts are explicitly exempt from residual solvent testing under this rule. "
        "Still written in exclusively 'medical marijuana' terminology (pre-dates the adult-use unification). "
        "STRENGTHENED FINDING, not just an open caveat: the complete current Title 1301:18 chapter index "
        "(1301:18-1 through -10) was fetched and checked in full — chapter 4 ('Manufacturing Practices, "
        "Administration, Testing, and Customer Sales') and chapter 7 ('Testing Laboratory Certification') "
        "are the only candidates, and neither specifies any analyte panel: Rule 1301:18-4-16 (Certificates "
        "of Analysis, read directly) requires labs to document tests performed but names no specific "
        "analytes, and chapter 7's four rules govern lab certification/accreditation/security only. OAC "
        "3796:4-2-04 is genuinely the only rule anywhere in Ohio's current administrative code that "
        "specifies which analytes must be tested — this isn't a migration-in-progress gap, it's a confirmed "
        "absence of any successor rule, so whether solvent testing applies identically to adult-use product "
        "remains unconfirmed from text alone rather than merely 'not yet found'."
    ),
    home_grow=HomeGrowRules(
        recreational_allowed=True,
        recreational_limit=PlantLimit(6, "per_person", "12 plants per residence; ORC 3796.04(A)(1), exact statutory text read directly"),
        medical_allowed=True,
        medical_limit=PlantLimit(6, "per_person", "no separate medical home-grow track — medical patients cultivate under the same adult-use rule"),
        extended_medical_available=False,
        extended_medical_limit=None,
        extended_medical_note="No enhanced/caregiver cultivation tier found.",
        caregiver_limit=None,
        caregiver_max_patients=None,
        geographic_gate=None,
        confidence="primary_source",  # ORC 3796.04(A)(1) read directly
        notes="",
    ),
    retail=RetailRules(
        recreational_allowed=True,  # ORC 3796.221 ("Rights of adult-use users") and OAC 1301:18-8-08
        # ("Dispensing Adult-Use Cannabis"), both read directly
        recreational_purchase_limits=(
            PurchaseLimit(2.5, "ounces_flower", "per_day", "OAC 1301:18-8-08(A)(2)(a), read directly: 'shall not dispense to an adult-use consumer more than ... 2.5 ounces of plant material' per day"),
            PurchaseLimit(15000, "mg_thc_edible", "per_day", "OAC 1301:18-8-08(A)(2)(b), read directly: total THC across all non-plant-material product categories capped at 15,000mg/day — not literally edibles-only, covers concentrates/infused products too"),
        ),
        recreational_min_age=21,  # OAC 1301:18-8-08(A)(1)(a), read directly: dispensary employee must confirm
        # "the individual is at least twenty-one years of age or older" before any sale
        medical_allowed=True,  # OAC 1301:18-8-09 ("Dispensing Medical Cannabis"), read directly
        medical_purchase_limits=(
            PurchaseLimit(10, "ounces_flower", "per_day", "OAC 1301:18-8-09(C)(1)(a), read directly: registered PATIENT limit, 'ten ounces of medical cannabis plant material' per day"),
            PurchaseLimit(60000, "mg_thc_edible", "per_day", "OAC 1301:18-8-09(C)(1)(b), read directly: registered patient, total THC content up to 60,000mg/day"),
            PurchaseLimit(2.5, "ounces_flower", "per_day", "OAC 1301:18-8-09(C)(2)(a), read directly: registered CAREGIVER limit (buying on a patient's behalf) — same 2.5oz/day as adult-use, lower than the patient's own 10oz cap"),
            PurchaseLimit(15000, "mg_thc_edible", "per_day", "OAC 1301:18-8-09(C)(2)(b), read directly: registered caregiver, 15,000mg THC/day"),
        ),
        medical_min_age=18,  # OAC 1301:18-8-09(A)(1)(a), read directly: "the individual is a patient at
        # least eighteen years of age or older or a caregiver at least twenty-one years of age or older." A
        # minor CAN be a registered patient (secondary-sourced: a minor enrolls via a 21+ caregiver who
        # transacts on their behalf) but cannot personally walk up to the counter and buy — this field
        # records the walk-in-counter age floor, not the minimum age to be a patient at all.
        id_verification_required=True,
        id_verification_note=(
            "OAC 1301:18-8-08(A)(1) (adult-use) and 1301:18-8-09(A)(1) (medical), both read directly: dispensary "
            "employee must review a 'valid, government-issued photographic identification containing the "
            "individual's date of birth' and confirm age, ID-matches-person, and (medical only) registered "
            "patient/caregiver status."
        ),
        pos_realtime_sync_required=True,
        pos_realtime_sync_note=(
            "Genuinely mixed answer, not a clean yes — OAC 1301:18-8-06(B), read directly, sets a general "
            "baseline for ALL dispensary sales: inventory must be recorded 'contemporaneously' 'from the time "
            "of receipt until distribution or disposal.' OAC 1301:18-8-09(D)(2) makes this explicit for medical "
            "purchases ABOVE 2.5oz/15,000mg: 'contemporaneously with the transaction.' But 1301:18-8-09(D)(1) "
            "carves out standard/smaller medical transactions (at or below that threshold): only 'by close of "
            "business of the date of the transaction' — same-day batch, not real-time. The adult-use rule "
            "(1301:18-8-08) is silent on timing beyond 'documented in the state inventory tracking system.' "
            "Net: real-time sync is the baseline expectation, but not every transaction is contemporaneously "
            "required — don't assume every Ohio sale syncs instantaneously."
        ),
        confidence="primary_source",  # every fact above read directly from OAC 1301:18-8-06/-08/-09 —
        # verified via raw HTML pulled with curl (WebFetch's own summarization was truncating quotes)
        notes=(
            "The medical purchase-limit and age facts don't reduce to one number per category — Ohio splits "
            "patient vs. caregiver limits (patient: 10oz/60,000mg; caregiver: 2.5oz/15,000mg, same as "
            "adult-use), the same 'doesn't reduce to a single figure' pattern PlantLimit already anticipates."
        ),
    ),
    notes=(
        "Ohio underwent a major statutory renumbering (former Chapter 3780 "
        "repealed, replaced by Chapter 3796) effective March 2026, and this pass "
        "found a SECOND, larger restructuring underway on top of that: Ohio is "
        "actively consolidating its medical-only rule chapters (3796:2/3/4/6) into "
        "a new unified Title 1301:18 ('Division of Cannabis Control') framework — "
        "still in progress, so some chapters (e.g. 3796:4-2 testing) remain "
        "independently current while others (waste, tagging) have already fully "
        "migrated. This is not just a renumbering: Ohio's waste-destruction rule "
        "genuinely changed substance in the migration — the old rule required 7 "
        "days' advance notice before destroying; the new one (OAC 1301:18-3-12) "
        "does not. Home-grow limits (ORC 3796.04(A)(1)) were re-confirmed current "
        "and unaffected by either restructuring."
    ),
)
