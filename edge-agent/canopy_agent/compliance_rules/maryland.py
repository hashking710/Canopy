from canopy_agent.compliance_rules.base import HomeGrowRules, PlantLimit, PurchaseLimit, RetailRules, StateComplianceRules

RULES = StateComplianceRules(
    state_code="MD",
    state_name="Maryland",
    platform="metrc",
    platform_confidence="secondary_source",  # agency doc references "METRC green waste entries"; not COMAR text itself
    tagging_trigger_kind="immediate",
    tagging_trigger_value=(
        "COMAR 14.17.10.03(C)(4) — as soon as practical after plant creation, each plant is assigned a "
        "unique identifier and batch, then tagged"
    ),
    tagging_trigger_confidence="primary_source",  # COMAR 14.17.10.03(C)(4), read directly: "For each plant,
    # as soon as practical, a grower shall: create a unique identifier ...; assign each plant to a batch;
    # enter information ... into the seed-to-sale tracking system; create a tag ...; and securely attach the
    # tag to a plant container or plant" — no untagged-batch-then-tagged-at-a-threshold model, unlike CA/CO
    deadline_kind="no_deadline_found",
    deadline_value=None,
    deadline_confidence="primary_source",  # COMAR 14.17.10.05 (growers) and 14.17.11.16 (processors, nearly
    # identical text), both read directly, contain no day-count at all — destruction timing is left to each
    # licensee's own SOP. CORRECTION from a prior pass: the previously-modeled "7 days after logging" figure
    # traces only to MMCC Bulletin 2019-017, titled specifically for licensed DISPENSARIES and dated Jan 2020
    # — predating the 2023 Cannabis Reform Act's restructuring into the current COMAR 14.17/MCA regime. Its
    # applicability to growers (the actor this project's WasteEvent model represents) was never established,
    # and the currently-codified grower-specific text sets no deadline — treat "7 days" as unconfirmed/likely
    # inapplicable here rather than the state's real rule for cultivation waste.
    reconciliation_cadence_days=30,
    reconciliation_confidence="primary_source",  # COMAR 14.17.10.03(C)(5), read directly: "At least monthly,
    # conduct a physical inventory of the stock and compare the physical inventory of stock with the stock
    # reflected in [the] seed-to-sale tracking system." ("at least monthly", not a literal 30-day figure)
    testing_required_for_solvent_extracts=True,
    testing_confidence="secondary_source",  # STRENGTHENED CITATION (still secondary_source): COMAR
    # 14.17.10.03(D)(4)/(D)(5)(d), the grower-chapter's own quality-control section, read directly, requires
    # "independent testing of the batch in accordance with the criteria set forth in COMAR 14.17.08.05A" and
    # a certificate of analysis "as specified in COMAR 14.17.08.05" before transfer to a dispensary — a
    # materially more specific, grower-linked chain than the generic 14.17.06.02(B) "comply with guidance"
    # catch-all a prior pass cited. COMAR 14.17.08.05(B)(3)/(B)(5), also read directly, requires labs to test
    # "in accordance with the Administration's Technical Authority" and report "whether the batch or lot is
    # within action limits ... as required by the Technical Authority." Still stops short of primary_source:
    # this chain names "Technical Authority" for testing generally, but never states "residual solvent"
    # specifically or singles out solvent-extracted concentrates — that specific fact still lives exclusively
    # in the incorporated Technical Authority document itself, not the COMAR text.
    testing_note=(
        "MCA's Technical Authority document (Residual Solvents section + Appendix A Table 1) requires a "
        "'Residual Solvent Test' for solvent-based concentrates before transfer to a dispensary. COMAR "
        "14.17.10.03(D) and 14.17.08.05(B), read directly, require testing 'in accordance with the "
        "Administration's Technical Authority' generally, but neither names residual solvents specifically — "
        "the document carries the actual substance here, not the COMAR text."
    ),
    home_grow=HomeGrowRules(
        recreational_allowed=True,
        recreational_limit=PlantLimit(2, "per_residence", "Md. Crim. Law §5-601.2 — flat cap regardless of how many adults 21+ reside there"),
        medical_allowed=True,
        medical_limit=PlantLimit(4, "per_residence", "Md. Alcoholic Beverages & Cannabis Art. §36-302(b) — a qualifying patient's own allowance, not '2 additional' stacked on the adult-use cap; if 2+ patients share a residence, still capped at 4 total there"),
        extended_medical_available=False,
        extended_medical_limit=None,
        extended_medical_note="No separate enhanced tier found beyond the caregiver provisions below.",
        caregiver_limit=None,  # CORRECTION: the previously-modeled 36-plant figure could not be traced to
        # any current codified provision. GAB Art. §36-302, read in full (subsections (a)-(i)), authorizes
        # cultivation only for the qualifying patient themselves (see medical_limit) — a caregiver's role as
        # described is limited to obtaining/administering cannabis on the patient's behalf, not growing it.
        # No caregiver cultivation allowance was found in COMAR 14.17 either. Left as None (rather than a
        # guessed number) per this project's bias toward honest gaps over a plausible-looking wrong figure.
        caregiver_max_patients=5,  # GAB Art. §36-302(d), read directly: "A caregiver may serve not more than
        # five qualifying patients at any time" — about caregiver service generally, not a cultivation figure
        geographic_gate=None,
        confidence="secondary_source",  # recreational (2/residence) and medical-patient (4/residence)
        # figures are primary-sourced (see above); caregiver_max_patients is too — but caregiver_limit is a
        # confirmed gap (no cultivation allowance found for caregivers at all), so the aggregate stays
        # secondary_source until that's resolved one way or the other by a maintainer
        notes="Superseded prior citation (Criminal Law §§5-101, 5-601, 5-601.1 — pre-2023-reform statutes): the operative provisions today are Crim. Law §5-601.2 (adult-use) and Alcoholic Beverages & Cannabis Art. §36-302 (medical patient + caregiver), both read directly at mgaleg.maryland.gov.",
    ),
    retail=RetailRules(
        recreational_allowed=True,  # COMAR 14.17.12.04 (dispensary chapter, distinct from the grower chapter
        # 14.17.10 already researched), read directly, explicitly governs "Dispensing Adult-Use Cannabis" (§B)
        recreational_purchase_limits=(
            PurchaseLimit(1.5, "ounces_flower", "per_day", "COMAR 14.17.12.04.B(7), read directly, cross-checked against Md. Crim. Law §5-101(u) 'personal use amount' (exact match) — combined limits, maxing one category forecloses any other"),
            PurchaseLimit(12, "grams_concentrate", "per_day", "COMAR 14.17.12.04.B(7), read directly; vaporizing devices weighed as concentrate"),
            PurchaseLimit(750, "mg_thc_edible", "per_day", "COMAR 14.17.12.04.B(7), read directly; also capped at 100mg/container, 10mg/serving per §B(9)(f)"),
        ),
        recreational_min_age=21,  # COMAR 14.17.12.04.B(5), read directly: "At the point of sale, a
        # dispensary agent shall verify that the consumer is 21 years old or older using the consumer's
        # government-issued photo identification"
        medical_allowed=True,  # COMAR 14.17.12.04 §A ("Dispensing Medical Cannabis"), read directly
        medical_purchase_limits=(
            PurchaseLimit(120, "grams_flower_equivalent", "per_rolling_period", "30-day-supply default per COMAR 14.17.12.04.A(4), structure read directly — but the exact 120g/36g-THC figure is sourced only to an MCA agency FAQ (cannabis.maryland.gov), NOT confirmed in codified COMAR/statute text, which only says a provider may certify a different amount if 30 days' worth is inadequate"),
        ),
        medical_min_age=None,  # no age floor found in fetched COMAR text — minors permitted via a
        # parent/guardian-designated caregiver (secondary-sourced via web search of MCA guidance, not
        # directly fetched primary statute; a future pass should verify against Md. ABC Article §36-303 directly)
        id_verification_required=True,
        id_verification_note=(
            "COMAR 14.17.12.04.B(1)-(3), read directly: government-issued photo ID with birthdate required; "
            "enumerated acceptable IDs (state driver's license, US/foreign passport, passport card, "
            "non-driver photo ID, military ID, tribal card); STUDENT ID EXPLICITLY EXCLUDED. §C(1) ties this "
            "to statute: 'in accordance with Alcoholic Beverages and Cannabis Article, §36-1101(a).' Medical "
            "patients additionally need an Administration-issued patient/caregiver ID number (§A(1))."
        ),
        pos_realtime_sync_required=True,
        pos_realtime_sync_note=(
            "Mixed evidence — recommend True but the COMAR text never uses the words 'real-time' the way "
            "Illinois's rule does. §C(2), read directly: dispensary 'shall use the seed-to-sale tracking "
            "system to track its stock ... from the time it is received ... to the time it is delivered or "
            "dispensed.' §A(2)/§B(4): agent must log into the Administration data network via unique login "
            "BEFORE any distribution and verify eligibility. §A(8): dispensing 'shall be recorded ... as a "
            "sale of medical cannabis using the seed-to-sale tracking system' (implicitly at/near time of "
            "sale, not explicitly 'real-time'). An official MCA guidance PDF (agency doc, secondary) "
            "references live METRC querying for compliance."
        ),
        confidence="secondary_source",  # recreational purchase limits/age/ID are primary_source; medical
        # purchase-limit exact amount, medical min age, and the "real-time" framing of POS sync are all
        # secondary_source — several figures trace only to agency guidance, not codified text
        notes="",
    ),
    notes=(
        "Waste deadline CORRECTED this pass: the current codified text (COMAR "
        "14.17.10.05 for growers, 14.17.11.16 for processors, both read directly) "
        "sets no deadline at all for cultivation waste — see deadline_confidence's "
        "comment for why the previously-modeled 7-day figure (sourced from a 2019 "
        "dispensary-specific bulletin) shouldn't be trusted for growers. Tagging is "
        "an 'immediate' trigger (every plant tagged at/near creation), a third "
        "distinct shape from CA's phase-triggered and CO's size-triggered models — "
        "see tagging_trigger_kind."
    ),
)
