from canopy_agent.compliance_rules.base import HomeGrowRules, PlantLimit, PurchaseLimit, RetailRules, StateComplianceRules

RULES = StateComplianceRules(
    state_code="OK",
    state_name="Oklahoma",
    platform="metrc",
    platform_confidence="secondary_source",  # OMMA pages describe it; agency description, not codified rule text
    tagging_trigger_kind="size",
    tagging_trigger_value="12 inches in height",
    tagging_trigger_confidence="primary_source",  # OAC 442:10-4-5(f)(3)(D)-(E), read directly in the current
    # (July 11, 2026) OMMA Permanent Rules: "the inventory tracking system tag shall be securely fastened to
    # a lower supporting branch" "when the plant reaches twelve (12) inches in height." CORRECTION: the
    # previous "vegetative" phase-trigger value doesn't appear anywhere in the rule text — this is a bare
    # height threshold, not a growth-stage transition (structurally identical to Ohio's and Colorado's
    # size-based triggers, not the phase-based model the old value implied).
    deadline_kind="no_deadline_found",
    deadline_value=None,
    deadline_confidence="primary_source",  # OAC 442:10-5-10 (waste disposal), re-read directly in the
    # current (July 11, 2026) OMMA Permanent Rules — still no deadline; that rule covers disposal of
    # excluded plant parts (root balls, stems, fan leaves, seeds, stalks) and a 7-year recordkeeping
    # requirement, nothing else. LOOP CLOSED this pass: the cross-referenced statute is the Oklahoma Medical
    # Marijuana Waste Management Act, correctly cited as 63 O.S. §§428-430 (the earlier "§427a et seq." was
    # simply the wrong section number — likely traceable to editorial renumbering notes within the Act
    # itself, e.g. "editorially renumbered from § 427 ... to avoid duplication"). All 4 sections (§428 short
    # title, §428.1 definitions, §429 exempt-plant-parts disposal methods, §430 waste-disposal licensing +
    # rulemaking delegation) read directly, verbatim, via law.justia.com — none contains any destruction-
    # timing deadline. This is now a confirmed absence at BOTH the statute and OAC level, not a cross-
    # reference left unread.
    reconciliation_cadence_days=1,
    reconciliation_confidence="primary_source",  # OAC 442:10-4-5(f)(2), read directly in the current OMMA
    # Permanent Rules: "All commercial licensees must ensure all on-premises and in-transit medical
    # marijuana and medical marijuana product inventories are reconciled each day in the State inventory
    # tracking system at the close of business, if not already done."
    testing_required_for_solvent_extracts=True,
    testing_confidence="primary_source",  # OAC 442:10-8-1, regulation text read directly
    testing_note=(
        "OAC 442:10-8-1, read directly: concentrate production batch samples must be tested against a "
        "13-analyte residual solvent panel with ppm thresholds. An infused product made from a concentrate "
        "that already passed residual solvent testing is exempt from re-testing for that analyte group."
    ),
    home_grow=HomeGrowRules(
        recreational_allowed=False,
        recreational_limit=None,
        medical_allowed=True,
        medical_limit=PlantLimit(6, "per_patient", "6 mature + 6 seedling plants — 63 O.S. §420(A)(3)-(4), read directly (the earlier 403 was oscn.net's bot-check blocking automated fetches; confirmed via law.justia.com's verbatim statute mirror instead)"),
        extended_medical_available=False,
        extended_medical_limit=None,
        extended_medical_note="No enhanced/extended medical tier found.",
        caregiver_limit=PlantLimit(6, "per_patient", "Same 6+6 limit as a patient, replicable across patients served — 63 O.S. §427.11(A), read directly: possession/cultivation rights 'up to the sum of the possession limits for the patients under his or her care'"),
        caregiver_max_patients=5,
        geographic_gate=None,
        confidence="primary_source",  # 63 O.S. §420(A)(3)-(4),(K) and §427.11(A)-(B), all read directly via
        # law.justia.com (a verbatim statute mirror with matching session-law citations, used because
        # oscn.net — the state's own portal — blocks automated fetches with a Cloudflare bot-check); the
        # caregiver 5-patient cap is confirmed at §427.11(B) specifically, not just inferred
        notes="No adult-use program exists — Oklahoma voters rejected a recreational ballot measure in 2023; medical-only market.",
    ),
    retail=RetailRules(
        recreational_allowed=False,  # confirmed-negative, not unexamined: no adult-use licensing chapter
        # exists anywhere in Title 63 or OAC 442; a 2026 ballot drive (ORCA) failed to gather enough
        # signatures by the Nov 3, 2025 deadline (secondary-sourced: MJBizDaily, Cannabis Business Times)
        recreational_purchase_limits=(),
        recreational_min_age=None,
        medical_allowed=True,
        medical_purchase_limits=(
            PurchaseLimit(3, "ounces_flower", "per_transaction", "OAC 442:10-5-12(a), read directly: '3 ounces or 84.9 grams of marijuana' per single dispensary transaction"),
            PurchaseLimit(28.3, "grams_concentrate", "per_transaction", "OAC 442:10-5-12(a), read directly: '1 ounce or 28.3 grams of marijuana concentrate' per transaction"),
            PurchaseLimit(2037.6, "grams_edible_product", "per_transaction", "OAC 442:10-5-12(a), read directly: '72 ounces or 2,037.6 grams of edible medical marijuana products' per transaction — this is a cap on PRODUCT WEIGHT, not THC content, hence the grams_edible_product unit rather than mg_thc_edible"),
        ),
        medical_min_age=None,  # NOT a clean 18 — 63 O.S. §420(L), read directly: "All applicants for a
        # medical marijuana patient license shall be eighteen (18) years of age or older. A special
        # exception shall be granted to an applicant under the age of eighteen (18); however, these
        # applications shall be signed by two physicians and the parent or legal guardian of the applicant."
        # OAC 442:10-5-12(a) confirms the purchase mechanism for minors: "a single transaction ... with a
        # patient, OR THE PARENT(S) OR LEGAL GUARDIAN(S) IF PATIENT IS UNDER EIGHTEEN (18) YEARS OF AGE, or
        # caregiver." A minor patient's guardian transacts directly — no hard age floor exists to record here.
        id_verification_required=True,
        id_verification_note=(
            "OAC 442:10-5-12(c), read directly: dispensaries 'shall utilize an OMMA provided system to "
            "verify and ensure that all medical marijuana transactions are conducted with medical marijuana "
            "patient, caregiver, or commercial license holders,' checking name, license number, expiration "
            "date, and photo. Verified against the state's own OMMA patient/caregiver license card (with "
            "photo), NOT a general government ID like a driver's license — a meaningfully different standard "
            "from adult-use states."
        ),
        pos_realtime_sync_required=True,
        pos_realtime_sync_note=(
            "OAC 442:10-4-5(f)(1), read directly: 'At a minimum, commercial licensees shall track, update, "
            "and report inventory after each individual sale to the Authority in the State inventory tracking "
            "system' — a cleaner, stronger per-sale standard than Ohio's contemporaneous-with-carve-outs rule. "
            "Backstopped by (f)(2)'s daily close-of-business reconciliation requirement (the same rule already "
            "cited for reconciliation_cadence_days=1 in the cultivation section)."
        ),
        confidence="primary_source",  # every fact read directly from the current (July 11, 2026) OMMA
        # Permanent Rules PDF and 63 O.S. §420, both already verified current in the cultivation research pass
        notes=(
            "The edible purchase cap (OAC 442:10-5-12(a)) is denominated in grams of PRODUCT WEIGHT, not mg "
            "THC — genuinely a different unit than the mg_thc_edible figures other states use, not a rounding "
            "choice (see the schema's grams_edible_product unit, added for this exact case)."
        ),
    ),
    notes=(
        "The widely-repeated '24 hours' waste deadline figure for Oklahoma appears "
        "only in integrator marketing sites (Flourish, GrowerIQ, Cultivera) — a "
        "direct primary-source read of OAC 442:10-5-10 (re-confirmed current as of "
        "the July 11, 2026 OMMA Permanent Rules) found no deadline at all. Treat any "
        "'24 hour' claim for Oklahoma as unverified/likely wrong. Plausible origin "
        "found for the myth (a hypothesis, not confirmed): the only '24 hour' figure "
        "anywhere in the current OMMA rules text is OAC 442:10-5-13's loss/theft "
        "reporting deadline — a different obligation from waste destruction that may "
        "have been conflated with it."
    ),
)
