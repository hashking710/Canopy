from canopy_agent.compliance_rules.base import HomeGrowRules, PlantLimit, PurchaseLimit, RetailRules, StateComplianceRules

RULES = StateComplianceRules(
    state_code="NY",
    state_name="New York",
    platform="metrc",
    platform_confidence="secondary_source",  # NY completed a phased migration OFF BioTrack ONTO METRC during
    # this project's 2026 research window (OCM's own bulletins, e.g. cannabis.ny.gov/system/files/documents/
    # 2025/08/sts-bulletin-08-05-25.pdf, gave a credentialing deadline of 12/17/2025 and further inventory/
    # testing-status deadlines through 3/31/2026, all now passed as of this Sept-2026 research pass) — but 9
    # NYCRR 125.8(a), read directly, only requires "a real-time electronic inventory tracking system" and
    # never names METRC by name in the regulation text itself, the same "regulation text is deliberately
    # vendor-agnostic" pattern already established for CA/IL in this dataset — so platform identity is only
    # ever secondary-sourced (agency bulletins, METRC's own partner page) even though it's not in doubt
    tagging_trigger_kind="phase",
    tagging_trigger_value="flowering, or moved to the designated canopy area, whichever happens first — same two-trigger shape as California",
    tagging_trigger_confidence="primary_source",  # 9 NYCRR 123.4(a)(5), read directly: "A lot plant tag shall
    # be applied to each individual cannabis plant as specified in this subdivision at the time the plant is
    # moved to the designated canopy area or begins flowering."
    deadline_kind="no_deadline_found",
    deadline_value=None,
    deadline_confidence="primary_source",  # 9 NYCRR 125.11, read directly: requires disposal of expired/
    # damaged/contaminated cannabis, weighing/recording/entering into the tracking system "prior to mixing and
    # disposal," and 5-year recordkeeping — but states no hour/day deadline for when destruction must occur,
    # and no advance-notice-to-the-state requirement either
    reconciliation_cadence_days=30,
    reconciliation_confidence="primary_source",  # 9 NYCRR 125.8(d), read directly: requires "conducting a
    # monthly inventory audit of all cannabis and cannabis products" plus a separate annual audit; significant
    # discrepancies (a license-type-specific 2-5% variance threshold) must be reported to OCM within 24 hours
    testing_required_for_solvent_extracts=True,
    testing_confidence="primary_source",  # 9 NYCRR 130.22(c), read directly: contaminant testing "shall
    # include, but not be limited to ... residual solvents" for "cannabis product or medical cannabis, and any
    # other intermediates or forms" — unlike some other states in this dataset (e.g. MA, NY's own text draws
    # no explicit solventless/non-solvent exemption; applies the same panel across forms as written
    testing_note=(
        "9 NYCRR 130.22(c), read directly: residual solvents are one of an enumerated list of required "
        "test analytes (alongside microorganisms, metals, mycotoxins, pesticides, terpenoids, etc.) for "
        "'cannabis product or medical cannabis, and any other intermediates or forms.' No solventless-product "
        "carve-out found in this subsection's text specifically — worth a follow-up check against OCM's "
        "separately-published testing-limits documents (e.g. cannabis.ny.gov's periodically-revised "
        "'Cannabis Testing Limits' PDF) for whether an exemption exists there instead."
    ),
    home_grow=HomeGrowRules(
        recreational_allowed=True,
        recreational_limit=PlantLimit(3, "per_person", "residence cap of 6 mature + 6 immature total regardless of occupant count"),
        medical_allowed=True,
        medical_limit=PlantLimit(3, "per_patient", "same 3 mature + 3 immature figure as adult-use, same residence cap structure"),
        extended_medical_available=False,
        extended_medical_limit=None,
        extended_medical_note="No enhanced/extended medical cultivation tier found beyond the caregiver provision below.",
        caregiver_limit=PlantLimit(3, "per_patient", "same 3+3 allowance as a patient, replicated once per patient served, subject to the same 6+6 residence cap"),
        caregiver_max_patients=4,  # 9 NYCRR 115.2(k), read directly: "a designated caregiver may grow on
        # behalf of, but no more than, four certified patients at a time"
        geographic_gate=None,
        confidence="primary_source",  # 9 NYCRR 115.3(c)-(d) (adult-use: 3+3 per person, 6+6 per residence)
        # and 9 NYCRR 115.2(d)-(e),(k) (medical: identical 3+3/6+6 structure, plus the 4-patient caregiver
        # cap), all read directly. CORRECTED a search-summary discrepancy this pass: one aggregator claimed
        # "12 plants per household" for adult-use, but the directly-fetched regulation text unambiguously
        # says 6 mature + 6 immature (12 total, which is likely the source of the aggregator's flattened
        # figure) — the 6-mature-and-6-immature framing is trusted here as the literal regulation text.
        notes="Both adult-use (9 NYCRR Part 115, effective 2024) and medical (9 NYCRR 115.2) home cultivation are legal in New York, structurally identical in shape (3+3 per grower, 6+6 per residence) — a real difference from neighboring New Jersey, which permits no home cultivation of either kind (see new_jersey.py).",
    ),
    retail=RetailRules(
        recreational_allowed=True,  # 9 NYCRR 123.10, read directly, governs "Retail Dispensary Operations"
        recreational_purchase_limits=(
            PurchaseLimit(3.0, "ounces_flower", "per_transaction", "Penal Law §222.05, read directly at nysenate.gov (NY's own official legislature site): adults 21+ may lawfully possess/purchase/obtain up to 3 ounces of cannabis; 9 NYCRR 123.10, read directly, cross-references this by prohibiting a dispensary sale that would cause a buyer to exceed 'possession limits established by article 222 of the Penal Law' rather than restating a number itself — the two sources together give a primary_source-strength per-transaction figure"),
            PurchaseLimit(24.0, "grams_concentrate", "per_transaction", "Penal Law §222.05, read directly: up to 24 grams of concentrated cannabis, same cross-reference mechanism via 9 NYCRR 123.10 as the flower figure above; flower and concentrate purchases combine proportionally rather than stacking independently per OCM consumer guidance (secondary-sourced for that specific combination mechanic)"),
        ),
        recreational_min_age=21,  # 9 NYCRR 123.10, read directly: "No retail dispensary shall sell, deliver,
        # or give away ... any cannabis or cannabis product to any individual, actually or seemingly under the
        # age of twenty-one (21) years of age"
        medical_allowed=True,  # 9 NYCRR Part 115/120 and the Cannabis Law's medical program provisions,
        # read directly, establish a parallel registered-organization dispensing channel
        medical_purchase_limits=(
            PurchaseLimit(70.87, "grams_flower_equivalent", "per_rolling_period", "Widely reported (secondary-sourced — could not independently re-fetch the exact current codified figure post the 2023 merger of the former DOH medical program into OCM) as a 60-day supply per the certifying practitioner's recommendation, or 3oz flower/24g concentrate, whichever is greater; modeled here at the 3oz-equivalent (70.87g) floor since that's the better-sourced number, but the 60-day-supply mechanic is the actual operative ceiling in most cases and isn't captured by a single gram figure"),
        ),
        medical_min_age=None,  # no hard walk-in-counter age floor found — a patient under 18 accesses medical
        # cannabis only via a registered caregiver (21+, or the minor's own parent/guardian), consistent with
        # the "no clean single number" pattern this project has already found in OH/OK/MI/NV (secondary-sourced
        # via patient-advocacy/vendor pages, not a direct statute fetch this pass)
        id_verification_required=True,  # 9 NYCRR 123.10, read directly: "Retail dispensary staff shall
        # inspect the individual's identification and determine the individual's age to validate that the
        # individual is twenty-one (21) years of age or older" — enumerates driver's license, passport,
        # military ID, and IDNYC as acceptable forms
        id_verification_note="9 NYCRR 123.10, read directly (see above); medical side uses OMH/OCM registry-ID-card verification instead, not independently re-confirmed at its own specific citation this pass.",
        pos_realtime_sync_required=True,
        pos_realtime_sync_note=(
            "9 NYCRR 123.10, read directly: 'Each sales transaction record shall be sent to the Office's "
            "inventory tracking system, real-time, in a manner as determined by the Office' — one of the "
            "more explicit 'real-time' clauses found across states in this dataset, on par with Illinois's."
        ),
        confidence="secondary_source",  # adult-use purchase limits/age/ID/POS-sync are primary_source; the
        # medical purchase-limit exact figure and medical_min_age are secondary_source (post-2023-merger
        # citation uncertainty) — aggregate reflects that real gap rather than rounding up
        notes="",
    ),
    notes=(
        "New York is the clearest 'phase-triggered tagging, explicit real-time POS "
        "language, no waste deadline' combination found in this dataset — structurally "
        "closest to California on tagging and to Illinois on POS-sync explicitness, "
        "despite being a distinct platform migration (BioTrack->METRC, completed on a "
        "different 2025/2026 timeline than Illinois's own BioTrack migration). The "
        "medical program's exact current purchase-limit citation is the weakest link "
        "here — New York folded its former Department of Health medical program into "
        "OCM/the Cannabis Law framework, and this pass could not cleanly re-derive "
        "which title (9 NYCRR vs. the historical 10 NYCRR 1004) now controls that "
        "specific figure; flagged for a maintainer rather than guessed at."
    ),
)
