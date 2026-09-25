"""The pilot's 2 x 2 in prompts: the product's, with library guidance, reversed, or both.

The pilot could not tell a misreading from two other things: a scoring
convention the prompt never states, and list-order anchoring -- Llama named the
option listed last on AC, UI and S throughout. Each variant changes the
product's rendered prompt in the one way its name says, and nothing else:

- **library** adds a paragraph of the CVSS v3.1 User Guide's own guidance on
  scoring a vulnerability in a software library, after the metric's values.
- **reversed** lists each metric's values in the opposite order, in the
  definitions and in the reply's schema alike.

**The product's prompt is not touched.** A variant is made from the prompt the
product's runner built, by the client that sends it, so the rest of the path --
redaction, pinning, the quotation check, the chairman -- is the product's. Each
variant asks under its own prompt version, which its pass's header records, and
the request fingerprint is taken over the variant's own words, so a pass of one
cannot be replayed as another. The record a replay rebuilds still names the
product's version on each member, because the product's runner names it from
the prompt it built: which variant was asked is read off the pass, not the record.
"""

from dataclasses import dataclass, replace

from council.definitions import definition_of
from council.prompt import PROMPT_VERSION, MemberPrompt, value_lines

# The CVSS v3.1 User Guide, section 3.7, "Scoring Vulnerabilities in Software
# Libraries (and Similar)": its first paragraph word for word, without its last
# sentence. That sentence asks for the assumptions to be written down, and a
# reply has nowhere to put them but the quotation, which the check would refuse.
# The section's next paragraph names a metric value, so it is left out: this
# tests whether the convention is understood, not whether a value is copied.
LIBRARY_GUIDANCE = (
    "When scoring the impact of a vulnerability in a library, independent of any "
    "adopting program or implementation, the analyst will often be unable to take "
    "into account the ways in which the library might be used. While specific "
    "products using the library should generate CVSS scores specific to how they "
    "use the library, scoring the library itself requires assumptions to be made. "
    "The analyst should score for the reasonable worst-case implementation scenario."
)
LIBRARY_LEAD = "The CVSS v3.1 User Guide, on scoring vulnerabilities in software libraries:"
LIBRARY_BLOCK = f"\n\n{LIBRARY_LEAD}\n\n{LIBRARY_GUIDANCE}"

# The variants' own wording, versioned apart from the product's. Bump a suffix
# when its change is reworded; the product's version moves them all.
LIBRARY_SUFFIX = "+library-1"
REVERSED_SUFFIX = "+reversed-1"


class VariantMismatch(RuntimeError):
    """The product's prompt does not read as a variant expects, so it cannot be changed safely.

    Not a `ValueError`: the product's runner records one of those as a member
    that failed, and a variant that cannot be built must stop the pass instead.
    """


@dataclass(frozen=True)
class Variant:
    """One way of asking: the product's prompt, with library guidance, reversed options, or both."""

    name: str
    library: bool
    reversed_options: bool

    @property
    def prompt_version(self) -> str:
        """Name the question this variant asks: the product's version, and each change to it."""
        library = LIBRARY_SUFFIX if self.library else ""
        reversal = REVERSED_SUFFIX if self.reversed_options else ""
        return f"{PROMPT_VERSION}{library}{reversal}"

    @property
    def added_texts(self) -> tuple[str, ...]:
        """Give the reference text this variant adds to the prompt, which is no advisory's."""
        return (LIBRARY_LEAD, LIBRARY_GUIDANCE) if self.library else ()


BASELINE = Variant("baseline", library=False, reversed_options=False)
LIBRARY = Variant("library", library=True, reversed_options=False)
REVERSED = Variant("reversed", library=False, reversed_options=True)
LIBRARY_REVERSED = Variant("library-reversed", library=True, reversed_options=True)
VARIANTS = {one.name: one for one in (BASELINE, LIBRARY, REVERSED, LIBRARY_REVERSED)}


def variant_asked(prompt_version: str) -> Variant:
    """Find the variant that asks under a prompt version, refusing a version none asks under."""
    found = [one for one in VARIANTS.values() if one.prompt_version == prompt_version]
    if not found:
        known = ", ".join(one.prompt_version for one in VARIANTS.values())
        raise ValueError(f"no variant asks under {prompt_version!r}; these do: {known}")
    return found[0]


def variant_prompt(prompt: MemberPrompt, variant: Variant) -> MemberPrompt:
    """Give the prompt a variant asks in place of the product's, under the variant's version."""
    if prompt.version != PROMPT_VERSION:
        raise VariantMismatch(f"a variant changes {PROMPT_VERSION}, not {prompt.version}")
    values = tuple(definition_of(prompt.metric).value_meanings)
    lines = value_lines(prompt.metric)
    shown = "\n".join(in_order(lines, variant)) + (LIBRARY_BLOCK if variant.library else "")
    return replace(
        prompt,
        system=replaced_once(prompt.system, "\n".join(lines), shown),
        user=replaced_once(prompt.user, allowed(values), allowed(in_order(values, variant))),
        version=variant.prompt_version,
    )


def in_order(options: tuple[str, ...], variant: Variant) -> tuple[str, ...]:
    """Give a metric's options in the order a variant lists them."""
    return options[::-1] if variant.reversed_options else options


def allowed(values: tuple[str, ...]) -> str:
    """Give the reply schema's list of a metric's values, as the product renders it."""
    return f"one of {', '.join(values)} --"


def replaced_once(text: str, old: str, new: str) -> str:
    """Replace the one occurrence of `old`, refusing text holding it any other number of times."""
    found = text.count(old)
    if found != 1:
        raise VariantMismatch(f"the product's prompt holds {old[:40]!r} {found} times, not once")
    return text.replace(old, new)
