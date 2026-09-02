from canopy_agent.compliance_rules.base import HomeGrowRules, PlantLimit, PurchaseLimit, RetailRules, StateComplianceRules

RULES = StateComplianceRules(
    state_code="NJ",
    state_name="New Jersey",
    platform="metrc",
    platform_confidence="secondary_source",  # METRC's own partner page and multiple industry vendor pages
    # (Distru, BioTrack's own NJ competitor-comparison page) converge on METRC as the CRC-designated system,
    # and N.J.A.C. 17:30-9.7/9.13, read directly, require use of a "Commission-designated inventory management
    # system" — but, the same pattern already established for CA/IL/NY in this dataset, the regulation text
    # itself never names METRC by vendor, so this can't reach primary_source via reg text alone
    tagging_trigger_kind="unknown",
    tagging_trigger_value="",
    tagging_trigger_confidence="could_not_verify",  # Genuinely could not confirm this pass, not a guess
    # rounded to a plausible value. N.J.A.C. 17:30-10 (cultivator premises rules) was checked directly and
    # contains no tagging-trigger language; 17:30-10.5 references plant tags only in the context of "single
    # serving" demarcation for a different product category, not a cultivation-stage trigger; general search
    # results describe "METRC plant tags" as the designated tag type but never state WHEN an individual tag
    # (vs. a batch/lot-level tag) becomes required — no height threshold, flowering trigger, or "immediate"
    # confirmation was found anywhere in fetchable N.J.A.C. 17:30 text this pass. Flagged for a maintainer
    # with direct N.J.A.C. access (some fetches of nj.gov's own rule PDFs returned unparseable binary/
    # compressed content via this project's tooling) rather than guessed at.
    deadline_kind="business_days_after_occurrence",
    deadline_value=10,
    deadline_confidence="primary_source",  # N.J.A.C. 17:30-9.14(e), read directly: "Within 10 business days
    # after destroying or disposing of the cannabis, the license holder or former license holder shall notify
    # the Commission, in writing, of the amount of cannabis destroyed or disposed of." A genuinely different
    # shape from Illinois/Ohio's pre-destruction NOTICE model — New Jersey notifies the Commission AFTER
    # destruction has already happened, not before. (A separate, narrower rule — 17:30-9.14, same section —
    # also requires unused inventory to be destroyed within 72 hours of a license expiring/being revoked; that's
    # a different scenario from routine cultivation waste and isn't what deadline_value models here.)
    reconciliation_cadence_days=30,
    reconciliation_confidence="primary_source",  # N.J.A.C. 17:30-9.13(a), read directly: "(4) Update product
    # inventories on at least a daily basis" and "(5) Conduct a monthly inventory audit of cultivating
    # cannabis, and stored usable and unusable cannabis" — plus a separate "(6) comprehensive annual inventory
    # audit." The daily figure is an update cadence, not a full reconciliation; monthly is the closest match
    # to this project's reconciliation_cadence_days semantics, same interpretive choice already made for IL/MD/MA.
    testing_required_for_solvent_extracts=True,
    testing_confidence="secondary_source",  # N.J.A.C. 17:30-19.4, read directly, requires labs to test
    # "according to the Cannabis Regulatory Commission's Testing Guidance" and an AHP monograph — it does NOT
    # itself name residual solvents; that specific analyte requirement lives only in the incorporated CRC
    # Testing Guidance document (nj.gov/cannabis, a PDF this project's tooling could not reliably parse this
    # pass), the same "the incorporated document carries the substance, not the regulation text" pattern
    # already established for Maryland in this dataset
    testing_note=(
        "N.J.A.C. 17:30-19.4 delegates the actual analyte panel to the Commission's own 'Testing Guidance' "
        "document rather than stating it in the regulation text. Multiple secondary sources (lab vendor pages, "
        "law-firm summaries) converge on residual solvents being a required analyte for concentrates/vapes — "
        "not in serious doubt substantively, but not independently confirmed against the primary incorporated "
        "document this pass, hence secondary_source rather than primary."
    ),
    home_grow=HomeGrowRules(
        recreational_allowed=False,
        recreational_limit=None,
        medical_allowed=False,
        medical_limit=None,
        extended_medical_available=False,
        extended_medical_limit=None,
        extended_medical_note="No home cultivation exists in any form — see notes.",
        caregiver_limit=None,
        caregiver_max_patients=None,
        geographic_gate=None,
        confidence="secondary_source",  # the no-home-grow-at-all finding converges strongly across many
        # independent secondary sources (law-firm summaries, cannabis-policy trackers, dispensary FAQ pages,
        # all citing N.J.S.A. 2C:35-5 treating unlicensed cultivation as manufacturing regardless of quantity)
        # but this project did not itself directly fetch and read N.J.S.A. 2C:35-5 or the CREAMM Act's home-
        # cultivation-silence this pass — a confirmed-negative worth a primary-source read to fully close out
        notes=(
            "New Jersey is one of a small number of adult-use-legal states (alongside Washington — see "
            "washington.py if added — and, per some trackers, Illinois for recreational users) that permits "
            "NO home cultivation at all, for either recreational or medical use — the CREAMM Act legalized "
            "possession and licensed retail but deliberately did not create any grow-your-own allowance, and "
            "unlicensed cultivation of any amount remains chargeable under N.J.S.A. 2C:35-5 (graded 3rd-degree "
            "felony under 10 plants, 2nd-degree 10-49 plants, per multiple converging secondary sources). "
            "Several legislative bills to add home cultivation have been introduced but none had passed as of "
            "this research pass (Sept 2026)."
        ),
    ),
    retail=RetailRules(
        recreational_allowed=True,  # nj.gov/cannabis/adult-personal/, the CRC's own official consumer page,
        # read directly
        recreational_purchase_limits=(
            PurchaseLimit(1.0, "ounces_flower", "per_transaction", "nj.gov/cannabis/adult-personal/, read directly (official CRC page): \"up to the equivalent of 28.35 grams or 1 ounce of usable cannabis\" per transaction"),
            PurchaseLimit(4.0, "grams_concentrate", "per_transaction", "nj.gov/cannabis/adult-personal/, read directly: \"4 grams of solid cannabis concentrates or resin, or the equivalent of 4 grams of concentrate in liquid form\""),
            PurchaseLimit(1000.0, "mg_thc_edible", "per_transaction", "nj.gov/cannabis/adult-personal/, read directly: \"1000 mg of multiple ingestible cannabis-infused products\"; categories may be combined proportionally in one transaction rather than stacking independently, per the same page"),
        ),
        recreational_min_age=21,  # nj.gov/cannabis/adult-personal/, read directly: "New Jersey residents or
        # visitors - 21 years and older" may purchase
        medical_allowed=True,  # N.J.A.C. 17:30 Subchapter 6 and the Jake Honig Compassionate Use Medical
        # Cannabis Act (as amended by "Jake's Law"), a parallel registered-patient dispensing channel
        medical_purchase_limits=(
            PurchaseLimit(85.05, "grams_flower_equivalent", "per_rolling_period", "3oz/30-day figure widely reported (secondary-sourced, converging across multiple sources) as the current limit following 'Jake's Law,' which raised the prior 2oz/month cap to 3oz/month; terminally-ill/hospice patients are reportedly exempt from any monthly cap entirely (also secondary-sourced) — this project did not independently re-fetch the exact current N.J.S.A. 24:6I-7 text this pass"),
        ),
        medical_min_age=None,  # no hard walk-in floor found — minors access the medical program via a
        # registered caregiver, the same "no clean single number" pattern found in several other states in
        # this dataset (secondary-sourced, not independently confirmed against N.J.A.C. 17:30 patient-
        # provisions text this pass)
        id_verification_required=True,
        id_verification_note=(
            "nj.gov/cannabis/adult-personal/, read directly: 'Dispensary personnel will need to see a "
            "government-issued identification card to ensure purchasers are 21 years or older,' with an "
            "explicit note that the dispensary may NOT retain copies of the ID or keep purchase records "
            "beyond what's needed for that single transaction — a real, distinct privacy-protective rule "
            "not seen phrased this explicitly in other states in this dataset."
        ),
        pos_realtime_sync_required=True,
        pos_realtime_sync_note=(
            "N.J.A.C. 17:30-14.3, read directly, requires dispensary staff to log ID/age verification in a "
            "record 'available for inspection by the Commission' but does NOT itself state a 'real-time' or "
            "'at time of sale' timing requirement — that language ('real time inventory management system') "
            "appears only in CRC/METRC marketing and guidance material, not the regulation text checked "
            "directly. N.J.A.C. 17:30-9.7/9.13 require daily inventory updates and monthly reconciliation "
            "(see reconciliation_cadence_days above), which functionally implies frequent syncing but doesn't "
            "textually mandate real-time-at-sale the way Illinois's or New York's rule text does — treating "
            "this as True but inferred/functional rather than an explicit textual guarantee, the same "
            "distinction this dataset already draws for Michigan."
        ),
        confidence="secondary_source",  # adult-use purchase limits/age/ID are primary_source (official CRC
        # consumer page, read directly); medical purchase-limit exact figure, medical_min_age, and the
        # inferred-not-explicit POS-sync finding are all secondary_source — aggregate reflects those real gaps
        notes="",
    ),
    notes=(
        "New Jersey's most operationally distinctive fact in this dataset: NO home "
        "cultivation exists at all, for either adult-use or medical patients — see "
        "home_grow.notes. The waste-destruction deadline is also a distinct shape "
        "from every other state modeled so far — a POST-destruction notification "
        "requirement (10 business days AFTER, N.J.A.C. 17:30-9.14(e)) rather than "
        "Illinois/Ohio's pre-destruction notice or Maryland's destroy-by-N-days-after- "
        "logging pattern. The individual-plant tagging trigger could not be confirmed "
        "this pass (see tagging_trigger_confidence) — several official nj.gov PDF rule "
        "documents returned unparseable/compressed content to this project's fetch "
        "tooling; a maintainer with better PDF access should revisit N.J.A.C. 17:30-10 "
        "directly rather than trust a guessed value."
    ),
)
