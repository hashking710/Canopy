from dataclasses import dataclass
from typing import Literal

# Three-level confidence, matching how the underlying research was actually delivered —
# collapsing this into a boolean loses real information (a "could not verify" fact and
# a "corroborated by three independent industry blogs" fact are very different, and
# conflating them is exactly the failure mode that produced this project's original
# wrong compliance claim: a secondary-sourced figure presented with no confidence
# marker at all, read by a future maintainer as simply "true").
Confidence = Literal["primary_source", "secondary_source", "could_not_verify"]


@dataclass(frozen=True)
class PlantLimit:
    """One plant-count figure for a specific grower category and counting unit —
    these do NOT reduce to a single number per state: limits are per-person in some
    states, per-residence in others, and the two aren't interchangeable (e.g.
    California's adult-use limit is 6 plants *per residence*, not per adult living
    there)."""

    count: float
    unit: Literal["per_person", "per_residence", "per_patient", "per_caregiver"]
    note: str = ""


@dataclass(frozen=True)
class HomeGrowRules:
    """
    Plant-count rules for non-commercial growers — home/recreational, medical patient,
    enhanced/'extended' medical, and caregiver cultivation. Tracked entirely separately
    from licensed commercial cultivation (below): these growers are not part of the
    state's commercial track-and-trace system at all, so they need a much lighter
    compliance check (a legal plant-count limit against a live count) rather than the
    tagging/waste-deadline/reconciliation machinery commercial licensees are subject to.
    This is also the intended default/free tier — commercial multi-site operations are
    the ones that actually need the heavier machinery below.
    """

    recreational_allowed: bool
    recreational_limit: PlantLimit | None

    medical_allowed: bool
    medical_limit: PlantLimit | None

    # An enhanced/"extended" cultivation allowance above the standard medical limit —
    # e.g. Colorado's physician-recommendable Extended Plant Count (statutory ceiling
    # 99 plants), or California's physician-discretion language with no hard ceiling.
    # Not every state has this category at all.
    extended_medical_available: bool
    extended_medical_limit: PlantLimit | None
    extended_medical_note: str

    # A designated caregiver cultivating on behalf of one or more patients — often a
    # different (usually higher) limit than a single patient's own allowance, and
    # sometimes capped by how many patients one caregiver may serve.
    caregiver_limit: PlantLimit | None
    caregiver_max_patients: float | None

    # Some states gate home cultivation on distance from a licensed dispensary (e.g.
    # Nevada/Arizona: only legal 25+ miles from one) — this excludes most growers in
    # major metro areas and is genuinely load-bearing, not a footnote.
    geographic_gate: str | None

    confidence: Confidence
    notes: str


@dataclass(frozen=True)
class PurchaseLimit:
    """One retail purchase-limit figure — like PlantLimit, these do NOT reduce to a
    single number per state: the unit varies (flower-equivalent grams is the most
    common basis, but concentrate and edible-THC-mg sub-limits are common too), and
    the period varies (a single-transaction cap vs. a rolling/daily cap are different
    obligations a retailer's POS has to enforce differently)."""

    amount: float
    unit: Literal[
        "grams_flower_equivalent", "grams_flower", "grams_concentrate", "mg_thc_edible", "ounces_flower",
        "grams_edible_product",  # some states (e.g. Oklahoma, OAC 442:10-5-12(a)) cap edibles by product
        # WEIGHT, not THC content — genuinely a different unit from mg_thc_edible, not a rounding choice
    ]
    period: Literal["per_transaction", "per_day", "per_rolling_period"]
    note: str = ""


@dataclass(frozen=True)
class RetailRules:
    """
    Retail/dispensary-side rules — a genuinely different regulatory surface from
    cultivation above: what a *customer* may walk out with, not what a *licensee* may
    grow. Deliberately scoped to the load-bearing facts a retail operation actually
    needs to not break the law at the point of sale, same "capture what's operationally
    decisive, not an exhaustive legal treatise" philosophy as HomeGrowRules — full
    packaging/labeling/advertising regimes exist in every state and are not modeled
    here, only what gates a sale: who may buy, how much, and what must happen at the
    register.
    """

    recreational_allowed: bool
    recreational_purchase_limits: tuple[PurchaseLimit, ...]
    recreational_min_age: int | None

    medical_allowed: bool
    medical_purchase_limits: tuple[PurchaseLimit, ...]
    medical_min_age: int | None

    # Whether ID/age verification at the point of sale is an explicit regulatory
    # requirement (as opposed to just common sense/store policy) — usually is, but the
    # exact standard (government ID only vs. any of several accepted forms, whether a
    # scanner/verification-system is mandated) varies enough to be worth a citation.
    id_verification_required: bool | None
    id_verification_note: str

    # The retail-specific "seed-to-sale" question: must a sale be recorded in the
    # state's track-and-trace system in real time (at/near the moment of sale), or is
    # some deferred/batch reporting cadence acceptable? This is the fact that actually
    # constrains how a POS integration has to behave, not just whether one exists.
    pos_realtime_sync_required: bool | None
    pos_realtime_sync_note: str

    confidence: Confidence
    notes: str


@dataclass(frozen=True)
class StateComplianceRules:
    """
    METRC's — and more broadly, each state's cannabis track-and-trace regime's — actual
    behavior is configured per state, not a single fixed ruleset. Deep re-verification
    (see docs/architecture.md) found the diversity goes well beyond "different numbers":
    some states don't use METRC at all (Arizona: no state platform; Illinois: BioTrackTHC
    until a 2025 migration), plant tagging is triggered by physical size in some states
    (Michigan, possibly Colorado) rather than growth phase (California), and the waste/
    destruction "deadline" isn't even the same *kind* of obligation everywhere — some
    states require a report within N hours/days of occurrence (California), some require
    advance notice *before* destruction happens (Ohio, Illinois), some require destruction
    within N days *after* logging it (Maryland), and some have no deadline in the primary
    regulation text at all (Michigan, Oklahoma, Colorado, Missouri, as far as this
    project's research could find). A single hardcoded shape can't represent that
    honestly, so `deadline_kind` is a proper set of shapes, not just a number.

    Every major fact carries its own `Confidence` rather than one blended flag — a state
    can be solidly sourced on one fact and unverified on another.
    """

    state_code: str
    state_name: str

    platform: Literal["metrc", "biotrack", "leaf_data_systems", "state_built", "none", "unknown"]
    platform_confidence: Confidence

    tagging_trigger_kind: Literal[
        "phase",  # tagging triggered by growth stage, e.g. CA: flowering
        "size",  # tagging triggered by plant dimensions, e.g. CO: exceeds 15in x 15in
        "immediate",  # every plant individually tagged at/near creation, no phase or size threshold at
        # all — a real, distinct shape (e.g. MD, MA: tag "as soon as practical"/on all plants and clones),
        # not the same as "unknown" just because it doesn't fit the phase/size mold
        "no_trigger_found",  # primary regulation text checked; no individual-plant-tagging requirement
        # exists there at all (e.g. AZ: only batch-level inventory documentation is required) — a
        # confirmed absence, same distinction deadline_kind already draws with no_deadline_found
        "unknown",  # not yet researched to either confirm a trigger or its absence
    ]
    tagging_trigger_value: str  # e.g. "flowering", or "exceeds 15in x 15in canopy", or "" if unknown
    tagging_trigger_confidence: Confidence

    deadline_kind: Literal[
        "hours_after_occurrence",  # report within N hours of the event (e.g. CA: 24)
        "business_days_after_occurrence",  # report within N business days of the event
        "pre_destruction_notice_days",  # must notify the state >= N days BEFORE destroying
        "destroy_by_days_after_logging",  # must actually destroy within N days of logging it
        "no_deadline_found",  # primary regulation text checked; no deadline exists there
        "unknown",  # not yet researched to either confirm a figure or its absence
    ]
    deadline_value: float | None  # None for no_deadline_found / unknown
    deadline_confidence: Confidence

    reconciliation_cadence_days: float | None
    reconciliation_confidence: Confidence

    # Whether this state's regulations require lab testing (residual solvents
    # specifically, sometimes bundled with potency/contaminant testing) before a
    # solvent-extracted concentrate (BHO, CO2, ethanol) can be sold/transferred —
    # a real legal gate that solventless (rosin) and flower are often exempt from or
    # held to a lighter standard. None = not yet researched to a yes/no answer.
    testing_required_for_solvent_extracts: bool | None
    testing_confidence: Confidence
    testing_note: str  # what's actually tested, and citation

    home_grow: HomeGrowRules
    retail: RetailRules

    notes: str  # top-level citations/caveats not already captured in a more specific field
