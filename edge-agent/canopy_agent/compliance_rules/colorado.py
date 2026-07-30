from canopy_agent.compliance_rules.base import HomeGrowRules, PlantLimit, PurchaseLimit, RetailRules, StateComplianceRules

RULES = StateComplianceRules(
    state_code="CO",
    state_name="Colorado",
    platform="metrc",
    platform_confidence="secondary_source",
    tagging_trigger_kind="size",
    tagging_trigger_value=(
        "no longer 'Immature Plant'/'Genetic Material' — exceeds 15in x 15in (changed from 8in x 8in by "
        "SB24-076 in 2024; the old 8in figure is stale, not just under-confirmed)"
    ),
    tagging_trigger_confidence="primary_source",  # 1 CCR 212-3, Rule 3-805(D)(2), read directly: "An
    # Inventory Tracking System tag must be physically attached to every Regulated Marijuana plant being
    # cultivated that is greater than fifteen inches tall or wide" — confirms tagging IS keyed to this size
    # threshold, and that SB24-076 (2024) moved the definition into statute (C.R.S. §44-10-103) and raised
    # it from 8in to 15in; also confirmed against the current 1 CCR 212-3-1-115 definitions text. Citation
    # chain closed with the primary source of the change itself: SB24-076's enrolled/signed bill text
    # (leg.colorado.gov, downloaded and read via pdftotext), Section 1, shows the actual redline — "'Immature
    # plant' means a nonflowering marijuana plant that is no taller than [eight->FIFTEEN] inches and no wider
    # than [eight->FIFTEEN] inches" — amending C.R.S. §44-10-103(18), signed by Gov. Polis, June 2024.
    deadline_kind="no_deadline_found",
    deadline_value=None,
    deadline_confidence="primary_source",  # Rule 3-230 read directly — no deadline found
    reconciliation_cadence_days=1,
    reconciliation_confidence="primary_source",  # Rule 3-805(E)(1) read directly: daily reconciliation at close of business, required
    testing_required_for_solvent_extracts=True,
    testing_confidence="primary_source",  # 1 CCR 212-3-4-120 (Contaminant Testing) read directly
    testing_note=(
        "Rule 4-120, read directly: 'Production Batches of Solvent-Based Medical Marijuana Concentrate, "
        "Solvent-Based Retail Marijuana Concentrate... must be tested by a Regulated Marijuana Testing "
        "Facility for residual solvent contamination.' Non-solvent concentrate is exempt from this specific "
        "requirement (though still subject to pesticide/potency testing)."
    ),
    home_grow=HomeGrowRules(
        recreational_allowed=True,
        recreational_limit=PlantLimit(6, "per_person", "max 3 flowering at a time; residential cap of 12/property regardless of occupant count"),
        medical_allowed=True,
        medical_limit=PlantLimit(6, "per_patient", "standard allowance"),
        extended_medical_available=True,
        extended_medical_limit=PlantLimit(99, "per_patient", "Extended Plant Count (EPC) — physician-recommendable, statutory ceiling"),
        extended_medical_note=(
            "RESOLVED (was previously flagged as an unresolved source conflict): an EPC does NOT override "
            "the residential cap. C.R.S. §25-1.5-106(8.5)(a.5)(I)-(II), read directly: a patient may not "
            "cultivate more than 12 plants at a residential property (up to 24 if registered per local law), "
            "and 'a patient who cultivates more marijuana plants than permitted ... shall locate his or her "
            "cultivation operation on a property, other than a residential property.' The mirrored caregiver "
            "provision, §25-1.5-106(8.6)(a)(I.6), says the same thing in caregiver terms. An EPC authorizes "
            "more plants in total, not more plants at the residence — the excess must move off-site."
        ),
        caregiver_limit=None,
        caregiver_max_patients=None,
        geographic_gate=None,
        confidence="primary_source",  # 6-per-person and 3-flowering-max: Colo. Const. Art. XVIII §16(3)(b);
        # 99-plant EPC ceiling: C.R.S. §25-1.5-106(8.6); 12-per-residence cap: C.R.S. §18-18-406(3)(a)(II)(A)
        # — all read directly. The 12-per-residence figure was previously only secondary-sourced under a
        # wrong hypothesis (assumed recodified into Title 44); it's actually in the Criminal Code, Title 18.
        notes=(
            "6-per-person and 3-flowering-max: Colo. Const. Art. XVIII §16(3)(b), read directly. 99-plant "
            "EPC ceiling: C.R.S. §25-1.5-106(8.6), read directly ('a primary caregiver shall not cultivate "
            "more than ninety-nine plants'). 12-per-residence cap CORRECTED this pass: it is NOT in Title 44 "
            "as previously hypothesized — it's C.R.S. §18-18-406(3)(a)(II)(A), read directly (Criminal Code): "
            "'Regardless of whether the plants are for medical or recreational use, it is unlawful ... to "
            "cultivate ... more than twelve marijuana plants on or in a residential property.' Added by "
            "HB17-1220 (2017), confirmed from the statute's own source note, not just a summary. This is ONE "
            "unified medical+recreational base rule — §18-18-406(3)(a)(II)(B) cross-references "
            "§25-1.5-106(8.5)(a.5)(I)/(8.6)(a)(I.5) by name as the medical-specific 24-plant exception to it "
            "(see extended_medical_note), not two separate statutes as previously modeled."
        ),
    ),
    retail=RetailRules(
        recreational_allowed=True,  # 1 CCR 212-3 Part 6 ("Retail Marijuana Store" rules), read directly
        recreational_purchase_limits=(
            PurchaseLimit(1.0, "ounces_flower", "per_transaction", "Rule 6-110(C)(1), read directly: 1oz flower 'or its equivalent'; Rule 6-110(C)(1) also defines 'single transaction' to include same-day multiple transfers that would exceed 1oz"),
            PurchaseLimit(8.0, "grams_concentrate", "per_transaction", "Rule 6-110(C)(2)(a), read directly: equivalency — 1oz flower = 8g concentrate"),
            PurchaseLimit(800.0, "mg_thc_edible", "per_transaction", "Rule 6-110(C)(2)(b), read directly: 1oz flower = '80 ten-milligram servings of THC' = 800mg total"),
        ),
        recreational_min_age=21,  # Rule 6-110(A)-(B), read directly
        medical_allowed=True,  # 1 CCR 212-3 Part 5 ("Medical Marijuana Store" rules), read directly
        medical_purchase_limits=(
            PurchaseLimit(2.0, "ounces_flower", "per_day", "Rule 5-125(A)(1)(a), read directly"),
            PurchaseLimit(8.0, "grams_concentrate", "per_day", "Rule 5-125(A)(1)(b), read directly, for patients 21+"),
            PurchaseLimit(2.0, "grams_concentrate", "per_day", "Rule 5-125(A)(1)(b), read directly, for patients 18-20"),
            PurchaseLimit(20000.0, "mg_thc_edible", "per_day", "Rule 5-125(A)(1)(c), read directly: 'Medical Marijuana Products containing a combined total of 20,000 mg'"),
        ),
        medical_min_age=None,  # Rule 3-710, read directly: "The term 'minor' ... means an individual under
        # the age of 18 for Medical Marijuana and under the age of 21 for Retail Marijuana," and Rule
        # 5-125(A)(3)(a)(iii)(D) directly references "The patient had a registry identification card prior to
        # 18 years of age" — confirms patients under 18 can be registered via a parent/guardian caregiver
        id_verification_required=True,
        id_verification_note=(
            "Rule 6-110(B), read directly: licensees 'must verify on TWO SEPARATE OCCASIONS that a Person is "
            "21 years of age or older' (once at entry, again before transfer), requiring 'valid "
            "government-issued photo identification.' Medical uses registry-ID-card verification instead."
        ),
        pos_realtime_sync_required=True,
        pos_realtime_sync_note=(
            "Genuine asymmetry, confirmed by full-text-searching the entire ~49,000-line official rules PDF "
            "for 'real time' (only 3 hits total): Medical = True, primary_source — Rule 5-125(C)(2), read "
            "directly, exact quote: 'At the time of the sale to the patient the Medical Marijuana Store and "
            "its Employee Licensee shall record the sale in real time in the Inventory Tracking System.' "
            "Retail = could NOT confirm equivalent explicit language — Rule 6-110 (the retail-store parallel "
            "to 5-125) and the shared Inventory Tracking System rules (3-805, 3-810, 3-820) were read in "
            "full; none contains 'real time' or an explicit at-time-of-sale clause for retail specifically. "
            "The closest retail obligation is the already-cited Rule 3-805(E)(1) daily close-of-business "
            "reconciliation. Overall value is True on the strength of the medical rule and the shared "
            "platform, but retail specifically is architecturally implied, not textually confirmed."
        ),
        confidence="secondary_source",  # age/ID/purchase-limit figures are primary_source; the retail-side
        # (not medical-side) POS-sync claim is architecturally implied rather than textually confirmed —
        # aggregate reflects that one real gap
        notes="",
    ),
    notes=(
        "Rule 3-805(E)(1), read directly: 'A Licensee must reconcile all "
        "on-premises and in-transit Regulated Marijuana inventories each day in "
        "the Inventory Tracking System at the close of business.' This is the "
        "strongest-sourced fact found for Colorado in this research pass — trust "
        "it more than the other fields here."
    ),
)
