"""The CVSS v3.1 Base metrics in the words a council member is asked to apply.

A member assesses one metric at a time and is given that metric's definition in
the prompt. `docs/COUNCIL.md` records why there is no retrieval layer: the
definitions are identical for every query and all eight cost roughly 2,700
tokens against a 32,768-token context, which makes them a constant to state
rather than a document to look up.

The wording is condensed from the CVSS v3.1 specification, section 2.1 and 2.3.
It is the member's whole authority on what a value means, so wording that drifts
from the specification is a measurement error and not a typo. `metrics.py` owns
which values are legal; this file owns what they mean, and a test holds the two
tables to each other.
"""

from dataclasses import dataclass
from typing import Mapping

from cvss.metrics import (
    ATTACK_COMPLEXITY,
    ATTACK_VECTOR,
    AVAILABILITY,
    CONFIDENTIALITY,
    INTEGRITY,
    PRIVILEGES_REQUIRED,
    SCOPE,
    USER_INTERACTION,
    metric_name,
)


@dataclass(frozen=True)
class MetricDefinition:
    """One Base metric explained: what it measures, and what each of its values means."""

    abbreviation: str
    measures: str
    value_meanings: Mapping[str, str]


DEFINITIONS: dict[str, MetricDefinition] = {
    ATTACK_VECTOR: MetricDefinition(
        ATTACK_VECTOR,
        "how remote from the vulnerable component an attacker can be and still exploit it.",
        {
            "N": (
                "Network. The vulnerable component is bound to the network stack and the "
                "attack is exploitable across a network, one or more routers away."
            ),
            "A": (
                "Adjacent. Bound to the network stack, but the attack is limited to a "
                "logically adjacent topology: the same physical or logical network, such as "
                "a local IP subnet, Bluetooth or Wi-Fi, or a limited administrative domain."
            ),
            "L": (
                "Local. Not bound to the network stack. The attacker works through read, "
                "write or execute capabilities on the machine, at a console or over a remote "
                "shell, or relies on another person to run something on their behalf."
            ),
            "P": (
                "Physical. The attacker must physically touch or manipulate the vulnerable "
                "component, such as by attaching to a port or removing a disk."
            ),
        },
    ),
    ATTACK_COMPLEXITY: MetricDefinition(
        ATTACK_COMPLEXITY,
        "what conditions beyond the attacker's control must hold for an exploit to work.",
        {
            "L": (
                "Low. No specialised conditions are needed. An attacker can expect repeatable "
                "success against the vulnerable component."
            ),
            "H": (
                "High. Success depends on conditions the attacker does not control: the target "
                "must be prepared or measured first, a protection such as address space "
                "randomisation must be defeated, a race must be won, or the attacker must "
                "already sit between two parties. The attack cannot be mounted at will."
            ),
        },
    ),
    PRIVILEGES_REQUIRED: MetricDefinition(
        PRIVILEGES_REQUIRED,
        "what privileges the attacker must already hold before the attack begins.",
        {
            "N": (
                "None. The attacker is unauthorised: no access to any setting or file is "
                "needed before the attack."
            ),
            "L": (
                "Low. Ordinary user privileges, typically reaching only settings and files "
                "owned by that user, or access to resources that are not sensitive."
            ),
            "H": (
                "High. Privileges giving significant control over the vulnerable component, "
                "such as administrative access to component-wide settings and files."
            ),
        },
    ),
    USER_INTERACTION: MetricDefinition(
        USER_INTERACTION,
        "whether a human other than the attacker must take part for the attack to succeed.",
        {
            "N": "None. The attack needs no participation from any other user.",
            "R": (
                "Required. Another user must do something first, such as open a file, follow "
                "a link, or install an update, before the vulnerability can be exploited."
            ),
        },
    ),
    SCOPE: MetricDefinition(
        SCOPE,
        "whether exploiting the vulnerable component affects resources it does not govern.",
        {
            "U": (
                "Unchanged. Only resources managed by the same security authority as the "
                "vulnerable component are affected. The vulnerable and impacted components "
                "are the same, or answer to the same authority."
            ),
            "C": (
                "Changed. The exploit reaches resources beyond the vulnerable component's "
                "own security authority: it escapes a sandbox, virtual machine or container, "
                "or a flaw in one component lets the attacker act on a different one."
            ),
        },
    ),
    CONFIDENTIALITY: MetricDefinition(
        CONFIDENTIALITY,
        "how much information the attacker gains access to that they should not have.",
        {
            "H": (
                "High. Total loss, or the disclosure of something whose loss is serious on "
                "its own, such as credentials, private keys or the whole contents of a store."
            ),
            "L": (
                "Low. Some information is disclosed, but the attacker does not choose what, "
                "or the amount is limited, and the loss is not serious on its own."
            ),
            "N": "None. No confidentiality is lost.",
        },
    ),
    INTEGRITY: MetricDefinition(
        INTEGRITY,
        "how much data the attacker can modify that they should not be able to.",
        {
            "H": (
                "High. Total loss of protection: the attacker can modify any data, or the "
                "modification they can make has a serious consequence on its own."
            ),
            "L": (
                "Low. Modification is possible, but the attacker does not control what is "
                "changed or how much, and the change is not serious on its own."
            ),
            "N": "None. No data can be modified.",
        },
    ),
    AVAILABILITY: MetricDefinition(
        AVAILABILITY,
        "how much of the affected component's service the attacker can take away.",
        {
            "H": (
                "High. Access is fully denied, or denied for as long as the attacker keeps "
                "attacking, or denied until somebody intervenes."
            ),
            "L": (
                "Low. Performance drops or service is interrupted, but even repeated "
                "exploitation does not deny service completely."
            ),
            "N": "None. Availability is unaffected.",
        },
    ),
}


def definition_of(abbreviation: str) -> MetricDefinition:
    """Give one Base metric's definition, refusing a metric nobody wrote one for."""
    # An abbreviation that is no Base metric at all is `cvss.metrics`'s refusal
    # to make, and it is the accurate one: nothing is missing here, the metric
    # does not exist. What is left for the guard below is the other case -- a
    # real metric this table has lost -- where the alternative is an
    # AttributeError on None two frames away from the cause.
    metric_name(abbreviation)
    definition = DEFINITIONS.get(abbreviation)
    if definition is None:
        raise ValueError(
            f"No council definition is written for {abbreviation!r}; "
            "a member cannot assess a metric it has not been told the meaning of"
        )
    return definition
