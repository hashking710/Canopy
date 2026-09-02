from canopy_agent.compliance_rules.base import HomeGrowRules, PlantLimit, PurchaseLimit, RetailRules, StateComplianceRules

RULES = StateComplianceRules(
    state_code="FL",
    state_name="Florida",
    platform="biotrack",
    platform_confidence="secondary_source",  # Fla. Stat. §381.986(8)(d), read directly at flsenate.gov,
    # establishes a "Department STS Tracking System" (defined only as "the computer software seed-to-sale
    # tracking system established, maintained, and controlled by the department") without naming a vendor —
    # the same "regulation/statute text is deliberately vendor-agnostic" pattern already established for
    # CA/IL/NY in this dataset. BioTrack's own site and Cannabis Business Times both report BioTrack won the
    # state's vendor selection; a notable divergence from most other East Coast states in this dataset (NY,
    # NJ, MD, MA all use METRC) — Florida is the one state here confirmed NOT on METRC.
    tagging_trigger_kind="unknown",
    tagging_trigger_value="",
    tagging_trigger_confidence="could_not_verify",  # Fla. Admin. Code R. 64ER24-2 ("MMTC STS Tracking System
    # Procedures") was read directly and contains no plant-tagging-trigger language at all — only product-
    # dispensation and route-of-administration recording rules. A search for a cultivation-specific rule
    # (e.g. a "64-4.2xx" cultivation-inventory-control chapter analogous to other states' cultivator rules)
    # did not surface a fetchable primary source stating whether Florida gates individual plant tags on a
    # size threshold, a growth-phase transition, or tags every plant immediately — genuinely unresolved this
    # pass, not a guess rounded to a plausible value.
    deadline_kind="pre_destruction_notice_days",
    deadline_value=3,
    deadline_confidence="primary_source",  # Fla. Admin. Code R. 64-4.207 ("MMTC Marijuana Waste Management
    # and Disposal"), read directly: "An MMTC must provide a minimum of 72 hours' notice in the MMTC's
    # seed-to-sale tracking system prior to rendering the Marijuana Waste unusable and unrecognizable or
    # irretrievable." 72 hours = 3 days, converted here to match this project's day-denominated
    # pre_destruction_notice_days field; the rule itself is stated in hours, not days — a maintainer building
    # an hour-precision reminder should use 72h rather than round to "3 days." Same pre-destruction-notice
    # SHAPE as Illinois/Ohio/Nevada, distinct from New Jersey's post-destruction-notification shape.
    reconciliation_cadence_days=None,
    reconciliation_confidence="could_not_verify",  # Fla. Admin. Code R. 64ER24-1/64ER24-2 (MMTC Seed-to-Sale
    # Tracking System Integration/Procedures rules), both read directly, were checked specifically for a
    # physical-inventory reconciliation cadence and found none — but unlike Michigan's "STRENGTHENED NEGATIVE
    # FINDING" (a confirmed full-text search of the complete rule set), this pass only checked the two most
    # likely rule chapters, not Florida's complete 64-4 chapter — treat as a real open gap, not a confirmed
    # absence, and worth a more exhaustive follow-up before treating "no reconciliation requirement" as settled.
    testing_required_for_solvent_extracts=True,
    testing_confidence="primary_source",  # Fla. Stat. §381.986(8)(e)11.d, read directly at flsenate.gov (the
    # Florida Senate's own official statute portal): MMTCs must "[t]est the processed marijuana using a
    # medical marijuana testing laboratory before it is dispensed," and the department "shall determine by
    # rule which contaminants must be tested for" — explicitly including residual-solvent testing obligations
    # triggered when an MMTC "process[es] marijuana with hydrocarbon solvents or other solvents or gases
    # exhibiting potential toxicity to humans."
    testing_note=(
        "Fla. Stat. §381.986(8)(e)11.d, read directly: the statute itself frames this as a rule-delegation "
        "('the department shall determine by rule ... which contaminants must be tested for'), naming "
        "'Residual Solvents' as one of an enumerated 'Contaminants Unsafe for Human Consumption' category "
        "(alongside microbes, mycotoxins, heavy metals, agricultural agents, filth) per emergency-rule text "
        "found via secondary sources — the exact current numbered rule carrying the analyte-specific ppm "
        "thresholds (successor to the 64-4.320-range emergency rules) was not independently re-fetched this pass."
    ),
    home_grow=HomeGrowRules(
        recreational_allowed=False,
        recreational_limit=None,
        medical_allowed=False,
        medical_limit=None,
        extended_medical_available=False,
        extended_medical_limit=None,
        extended_medical_note="No home cultivation exists in any form, even for registered medical patients — see notes.",
        caregiver_limit=None,
        caregiver_max_patients=None,
        geographic_gate=None,
        confidence="secondary_source",  # the no-home-grow-at-all finding (for BOTH recreational and medical)
        # converges strongly across many independent secondary sources (law-firm summaries, patient-advocacy
        # pages, dispensary FAQ pages), all citing Fla. Stat. §893.13(1)(a) as criminalizing unlicensed
        # cultivation with no medical-patient exception — Florida's medical program is fully vertically
        # integrated through licensed MMTCs with no home-grow carve-out anywhere. This project did not itself
        # directly fetch and read §893.13(1)(a) this pass — a confirmed-negative worth a primary-source read
        # to fully close out, same caveat as New Jersey's equivalent finding.
        notes=(
            "Florida remains medical-only as of this research pass (Sept 2026): a 2024 constitutional "
            "amendment (Amendment 3) got 56% voter support but fell short of the 60% supermajority Florida "
            "requires, and a follow-up 2026 citizen-initiative signature drive (Smart & Safe Florida) was "
            "confirmed (Ballotpedia, CBS News Miami, both read via search) to have fallen roughly 100,000 "
            "signatures short of qualifying for the November 2026 ballot. No home cultivation exists for "
            "medical patients either — Florida's program is fully vertically-integrated through licensed "
            "MMTCs (Medical Marijuana Treatment Centers), a structural difference from every other state in "
            "this dataset except New Jersey."
        ),
    ),
    retail=RetailRules(
        recreational_allowed=False,  # confirmed-negative: no adult-use licensing framework exists anywhere
        # in Fla. Stat. §381.986 or F.A.C. Chapter 64-4; see home_grow.notes for the 2024/2026 ballot history
        recreational_purchase_limits=(),
        recreational_min_age=None,
        medical_allowed=True,  # Fla. Stat. §381.986 and F.A.C. Chapter 64-4 (Compassionate Use), read
        # directly, establish the MMTC dispensing framework
        medical_purchase_limits=(
            PurchaseLimit(2.5, "ounces_flower", "per_rolling_period", "Fla. Admin. Code R. 64ER22-8, read directly: '35-day supply limit for marijuana in a form for smoking shall not exceed 2.5 ounces' — this is the SMOKABLE-FLOWER-SPECIFIC sub-limit, on its own 35-day cycle, distinct from the non-smoking routes below which run on a 70-day cycle"),
            PurchaseLimit(4200.0, "mg_thc_edible", "per_rolling_period", "Fla. Admin. Code R. 64ER22-8, read directly: edible route capped at 60mg THC/day = 4,200mg THC per 70-day period. Florida's dosing regime is genuinely multi-route rather than one flat number: inhalation (vaporization) separately allows 350mg THC/day = 24,500mg/70 days, and oral capsules/tinctures allow 200mg THC/day = 14,000mg/70 days, with an aggregate 24,500mg-THC/70-day ceiling across all non-smoking routes combined. This project's schema records one PurchaseLimit per unit/period, consistent with how Missouri's multi-tier plant allowance was handled (record the best-fit figure, document the fuller structure here rather than force it into extra fields)."),
        ),
        medical_min_age=None,  # no hard walk-in-counter age floor found — Fla. Stat. §381.986, per secondary
        # sources (this project did not independently re-fetch the exact minor-patient subsection this pass),
        # requires a second physician's written concurrence for a patient under 18, and a minor patient
        # accesses/purchases only via a registered caregiver (21+, FL resident) — the same "no clean single
        # number" pattern already established for several other states in this dataset
        id_verification_required=True,
        id_verification_note=(
            "Fla. Admin. Code R. 64-4.011, per secondary sources (not independently re-fetched this pass — "
            "citation given by multiple converging patient-advocacy/MMTC pages), requires all patients and "
            "caregivers to hold a Medical Marijuana Use Registry identification card, checked alongside a "
            "government-issued photo ID at the point of sale — a registry-card model, not a generic-ID-only "
            "model, similar in shape to Oklahoma's OMMA-card standard."
        ),
        pos_realtime_sync_required=None,
        pos_realtime_sync_note=(
            "COULD NOT VERIFY either way. Fla. Admin. Code R. 64ER24-1/64ER24-2, both read directly, require "
            "an MMTC's Internal STS Tracking System to integrate with the Department STS Tracking System via "
            "API 'in accordance with specified timeframes,' and to provide the department all required data "
            "within 48 hours of a request — but no 'real-time'/'at time of sale' language was found in either "
            "rule, and 48-hours-on-request is a materially weaker standard than the explicit real-time clauses "
            "found in e.g. Illinois/Missouri/New York. Left as None/could_not_verify rather than guessing "
            "either direction — a maintainer should check F.A.C. 64-4.221 (a related dispensing-operations "
            "rule not independently fetched this pass) before relying on either answer."
        ),
        confidence="secondary_source",  # medical purchase-limit figures and testing citation are
        # primary_source; medical_min_age, id_verification's exact rule citation, and pos_realtime_sync (left
        # unresolved) are all secondary_source-or-weaker — aggregate reflects those real gaps
        notes="No adult-use retail exists at all (recreational_allowed=False) — see home_grow.notes for the 2024/2026 legalization-attempt history.",
    ),
    notes=(
        "Florida is the one state in this dataset confirmed to use BioTrack rather "
        "than METRC, and the one state (alongside New Jersey) confirmed to have NO "
        "home cultivation in any form, even for medical patients — a fully vertically-"
        "integrated MMTC model. Two fields are left genuinely unresolved rather than "
        "guessed at: the individual-plant tagging trigger (tagging_trigger_kind) and "
        "the reconciliation cadence (reconciliation_cadence_days) — both "
        "could_not_verify, not no_deadline_found/no_trigger_found, because this "
        "project could not complete an exhaustive enough read of F.A.C. Chapter 64-4 "
        "to confirm an absence the way Michigan's reconciliation finding did. A "
        "maintainer with more complete access to Florida's administrative code should "
        "close these out before treating this state's compliance data as fully reliable."
    ),
)
