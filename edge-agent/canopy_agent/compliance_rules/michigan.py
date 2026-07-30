from canopy_agent.compliance_rules.base import HomeGrowRules, PlantLimit, PurchaseLimit, RetailRules, StateComplianceRules

RULES = StateComplianceRules(
    state_code="MI",
    state_name="Michigan",
    platform="metrc",
    platform_confidence="secondary_source",  # state calls it "statewide monitoring system"; industry sources ID it as METRC
    tagging_trigger_kind="size",
    tagging_trigger_value="exceeds 8in x 8in canopy (R 420.303(2))",
    tagging_trigger_confidence="primary_source",  # R 420.303(2), read directly (exact subsection, tightened
    # from the earlier vague "R 420.303-area rules"): "A cultivator shall tag each individual plant that is
    # greater than 8 inches in height ... or more than 8 inches in width" — size-based, not phase-based
    deadline_kind="no_deadline_found",
    deadline_value=None,
    deadline_confidence="primary_source",  # R 420.211 read directly: requires recording destruction, but no hour/day deadline
    reconciliation_cadence_days=None,
    reconciliation_confidence="could_not_verify",  # STRENGTHENED NEGATIVE FINDING: a full-text read of the
    # CRA's complete current administrative rules (R 420.1-R 420.1004, fetched via curl+pdftotext after a
    # bare request was blocked by Akamai — a browser User-Agent header got the real PDF) found no
    # reconciliation-cadence requirement anywhere. R 420.203, R 420.206, R 420.206a, R 420.210, R 420.211,
    # R 420.502, and R 420.503 were all read directly; full-text search across the whole document for
    # "reconcile," "physical inventory," "audit"+"inventory," "discrepanc-," "cycle count," and "stock count"
    # found nothing. If this requirement exists in Michigan law at all, it is not in the R 420 rules text —
    # this is now a real negative finding from a complete read, not just an unresearched gap.
    testing_required_for_solvent_extracts=True,
    testing_confidence="primary_source",  # Mich. Admin. Code R. 420.305(7), regulation text read directly
    testing_note=(
        "R 420.305(7), read directly: 'A laboratory shall conduct residual solvent testing on batches of "
        "marihuana concentrates and marihuana-infused products.' The specific solvent list and action "
        "limits are published separately by the agency rather than in the rule text itself."
    ),
    home_grow=HomeGrowRules(
        recreational_allowed=True,
        recreational_limit=PlantLimit(12, "per_residence", "MCL 333.27955"),
        medical_allowed=True,
        medical_limit=PlantLimit(12, "per_patient", "MCL 333.26424 — 12 plants if no caregiver is designated"),
        extended_medical_available=False,
        extended_medical_limit=None,
        extended_medical_note="No enhanced/extended medical tier found beyond the caregiver structure below.",
        caregiver_limit=PlantLimit(12, "per_patient", "MCL 333.26424 (primary source) — 12 plants per patient served"),
        caregiver_max_patients=5,  # MCL 333.26426(d), read directly (raw text from the Legislature's own
        # compiled-law PDF, legislature.mi.gov/documents/mcl/pdf/mcl-Initiated-Law-1-of-2008.pdf, fetched via
        # curl+pdftotext): "each qualifying patient can have not more than 1 primary caregiver, and a primary
        # caregiver may assist not more than 5 qualifying patients" — upgraded from an AI-summarized WebFetch
        geographic_gate=None,
        confidence="primary_source",  # both the 12-plants-per-patient figure (MCL 333.26424) and the
        # 5-patient caregiver cap (MCL 333.26426(d)) are now confirmed via raw statute text, read directly
        notes=(
            "The 12-plants-per-patient caregiver figure is primary-sourced (MCL "
            "333.26424, text read directly). The 'max 5 patients per caregiver' cap "
            "is MCL 333.26426(d), not MCL 333.26424 as an earlier pass had it — "
            "confirmed via the Michigan Legislature's own compiled-law PDF, read "
            "directly: 'a primary caregiver may assist not more than 5 qualifying "
            "patients with their medical use of marihuana.'"
        ),
    ),
    retail=RetailRules(
        recreational_allowed=True,  # R 420.505/506, read directly, explicitly regulate sales under the
        # MRTMA (adult-use) — confirmed via rule text, not just "there's a market"
        recreational_purchase_limits=(
            PurchaseLimit(2.5, "ounces_flower", "per_transaction", "R 420.506(3), read directly: \"prohibited from making a sale ... that exceeds 2.5 ounces\" per transaction to an adult 21+"),
            PurchaseLimit(15, "grams_concentrate", "per_transaction", "R 420.506(3), read directly: \"Not more than 15 grams of marihuana may be in the form of marihuana concentrate\" (part of the same 2.5oz transaction cap, not additive)"),
        ),
        recreational_min_age=21,  # R 420.506(3)/R 420.505(1)(c), read directly: "bears a photographic image
        # and proof that the individual is 21 years of age or older, under the MRTMA"
        medical_allowed=True,  # R 420.505/506, read directly, explicitly regulate sales under the MMFLA (medical)
        medical_purchase_limits=(
            PurchaseLimit(2.5, "ounces_flower", "per_day", "R 420.506(1)-(2), read directly: patient/caregiver-on-behalf-of-patient limited to 2.5oz per qualifying patient per day"),
            PurchaseLimit(10, "ounces_flower", "per_rolling_period", "R 420.506(2), read directly: 10oz/month total cap"),
        ),
        medical_min_age=None,  # no numeric floor found in R 420.505/506 — Michigan's MMFLA allows a minor
        # to be a registered qualifying patient via a registered primary caregiver, so there's no walk-in-
        # counter age floor the way adult-use has 21 (same "no clean single number" pattern as OH/OK/NV)
        id_verification_required=True,
        id_verification_note=(
            "R 420.505(1)(c), read directly: \"The marihuana customer presented his or her valid driver's "
            "license or government-issued identification card that bears a photographic image of the "
            "qualifying patient or primary caregiver, under the MMFLA; or bears a photographic image and "
            "proof that the individual is 21 years of age or older, under the MRTMA.\" R 420.505(3)(b) "
            "separately covers visiting (out-of-state) patients."
        ),
        pos_realtime_sync_required=True,
        pos_realtime_sync_note=(
            "No explicit timing word (\"immediately\"/\"real-time\"/\"within N hours\") found in R 420.505/506 "
            "despite a targeted search — R 420.505(2) only says sales locations \"shall enter all "
            "transactions ... in the statewide monitoring system,\" no deadline stated. However, R "
            "420.506(1)-(2) requires verifying in that same system, BEFORE completing a sale, that daily/"
            "monthly purchase limits aren't already exceeded — which functionally requires near-real-time "
            "data, even without an explicit stated deadline. Recommend treating this as inferred rather than "
            "stated outright; vendor/industry sites claim \"real time\" but that's marketing language, not "
            "rule text."
        ),
        confidence="secondary_source",  # allowed/limits/age/ID are primary_source; the POS-sync fact is only
        # inferred from a functional requirement, not an explicit stated rule — aggregate reflects that gap
        notes="Purchase-limit citation corrected from MCL 333.27955 (the possession/home-grow statute) to R 420.506 (the retailer-specific transaction-cap rule) — a different statute governs what a retailer may sell vs. what a person may possess.",
    ),
    notes=(
        "Waste: R 420.211 (primary source, read directly) requires destruction be "
        "recorded but sets no hour/day deadline for doing so — the deadline_kind "
        "above reflects a confirmed absence, not an unresearched gap. Two other, "
        "unrelated deadlines exist and must not be conflated with general waste "
        "reporting: R 420.804 sets a 24-hour deadline for theft/loss reporting "
        "(different obligation entirely), and R 420.214c requires destroying "
        "RETURNED product within 90 calendar days of the licensee becoming aware "
        "of it (a narrower scenario than general cultivation waste)."
    ),
)
