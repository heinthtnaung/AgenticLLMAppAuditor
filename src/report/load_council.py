"""Reading a saved report's council records back into the projection a run carried.

The inverse of `report.json_council`. A council that settled a vector reads back as
a `CouncilAssessment`, one that ran and settled none as a `CouncilWithoutVector`,
and a finding the council was not put to as a `CouncilNotAsked`; a finding of a run
with no council carries no council block, and reads back as no entry at all. The
vector's base score is recomputed by the renderers from the vector, so nothing
here reads it.
"""

from typing import Any, Mapping

from report.council_record import (
    CouncilAssessment,
    CouncilNotAsked,
    CouncilOutcome,
    CouncilWithoutVector,
    MemberIdentity,
    MemberSaid,
    MetricEscalation,
    MetricRuling,
    Outcome,
    ReadingOrder,
    SaidKind,
)
from report.load_json import as_list, as_object, require


def council_from(advisory_id: str, block: Any) -> CouncilOutcome | None:
    """Read one finding's council record, or None where no council ran on the audit."""
    if block is None:
        return None
    where = f"council[{advisory_id}]"
    if not require(block, "ran", where):
        return CouncilNotAsked(advisory_id, str(require(block, "because", where)))
    return ran_council(advisory_id, block, where)


def ran_council(advisory_id: str, block: Mapping[str, Any], where: str) -> CouncilOutcome:
    """Read a council that ran: an assessment with a vector, or one that settled none."""
    rulings = tuple(ruling_from(one, where) for one in as_list(block.get("metrics") or [], where))
    single = bool(require(block, "single_assessor", where))
    if block.get("vector") is not None:
        return CouncilAssessment(
            advisory_id, str(block["vector"]), single, rulings,
            nothing_cross_checked=bool(block.get("nothing_cross_checked")),
        )
    return CouncilWithoutVector(
        advisory_id, single, metric_names(block, "unresolved_metrics"),
        metric_names(block, "contested_metrics"), rulings,
    )


def metric_names(block: Mapping[str, Any], key: str) -> tuple[str, ...]:
    """Read a council's list of metric names back, in the order the record keeps them."""
    return tuple(str(one) for one in (block.get(key) or []))


def ruling_from(block: Mapping[str, Any], where: str) -> MetricRuling:
    """Read one metric's ruling: what the chairman decided, and every member behind it."""
    said = tuple(member_said_from(one, where) for one in as_list(block.get("members") or [], where))
    return MetricRuling(
        metric=str(require(block, "metric", where)),
        outcome=Outcome(require(block, "outcome", where)),
        said=said,
        value=block.get("value") or "",
        basis=block.get("basis") or "",
        confidence=block.get("confidence") or "",
        fallback_source=block.get("fallback_source") or "",
        escalation=escalation_from(block.get("escalation"), where),
        same_evidence_different_reading=bool(block.get("same_evidence_different_reading")),
    )


def escalation_from(block: Any, where: str) -> MetricEscalation | None:
    """Read what the escalation model said of a metric the council left open, or None for none."""
    if block is None:
        return None
    return MetricEscalation(
        prior=Outcome(require(block, "prior_outcome", f"{where}.escalation")),
        said=member_said_from(block, f"{where}.escalation"),
    )


def member_said_from(block: Mapping[str, Any], where: str) -> MemberSaid:
    """Read what one member said about one metric, and who it was."""
    return MemberSaid(
        member=member_identity_from(block, where),
        kind=SaidKind(require(block, "said", where)),
        value=block.get("value") or "",
        evidence=block.get("evidence") or "",
        confidence=block.get("confidence") or "",
        verified=bool(block.get("evidence_verified")),
        reason=block.get("reason") or "",
        order_values=order_values_from(block.get("orders"), where),
        declined_in=reading_orders(block.get("declined_in")),
        unverified_in=reading_orders(block.get("unverified_in")),
    )


def member_identity_from(block: Mapping[str, Any], where: str) -> MemberIdentity:
    """Read which member spoke, and enough of it to reconstruct the roster."""
    return MemberIdentity(
        name=str(require(block, "member", where)),
        provider=str(require(block, "provider", where)),
        model=str(require(block, "model", where)),
        family=str(require(block, "family", where)),
        ran_local=bool(require(block, "ran_local", where)),
        prompt_version=str(require(block, "prompt_version", where)),
        reversed_prompt_version=block.get("reversed_prompt_version") or "",
    )


def order_values_from(block: Any, where: str) -> tuple[str, ...]:
    """Read an order-sensitive member's two values, or nothing for any other kind of reply."""
    if block is None:
        return ()
    orders = as_object(block, f"{where}.orders")
    return str(require(orders, "in_order", f"{where}.orders")), str(
        require(orders, "reversed", f"{where}.orders")
    )


def reading_orders(names: Any) -> tuple[ReadingOrder, ...]:
    """Read the orders a member did something in, or nothing where it was asked the options once."""
    if names is None:
        return ()
    return tuple(ReadingOrder(one) for one in names)
