"""The roster: n members an operator added, and which of them this run may ask.

A Python object and not a file. `docs/COUNCIL.md` prints a YAML sketch and says
so in the first line of that section -- it shows what a reader would be editing,
not a schema to write against -- and the project has committed to no format. A
loader belongs with whatever format is chosen, not in the type it loads into.

**`egress` fails closed.** It is the hosted opt-in, off by default, and a hosted
member without it does not run. That is a refusal in code rather than a note in
a document, because what leaves the machine is not only an advisory: *which*
advisories you ask about, and when, describes the software you run. A skipped
member is reported as skipped -- a record that does not say where the text went
is not an audit record, and one that quietly omits a member is worse.
"""

from dataclasses import dataclass

from council.answer import MemberIdentity

OLLAMA_PROVIDER = "ollama"

SKIPPED_WITHOUT_EGRESS = "hosted, and egress was not opted in for it"


@dataclass(frozen=True)
class Member:
    """One model reached through one provider, as the operator configured it."""

    name: str
    provider: str
    model: str
    family: str
    runs_local: bool
    egress: bool = False

    def __post_init__(self) -> None:
        """Refuse a member a record could not name or reconstruct."""
        missing = [
            field
            for field in ("name", "provider", "model", "family")
            if not getattr(self, field)
        ]
        if missing:
            raise ValueError(f"A council member needs {', '.join(missing)}")
        refuse_non_boolean(self.name, "runs_local", self.runs_local)
        refuse_non_boolean(self.name, "egress", self.egress)

    def may_run(self) -> bool:
        """Say whether this run may ask this member, which a hosted one must opt into."""
        return self.runs_local or self.egress

    def identify(self, prompt_version: str) -> MemberIdentity:
        """Name this member on an answer, recording the prompt it was asked with."""
        return MemberIdentity(
            name=self.name,
            provider=self.provider,
            model=self.model,
            family=self.family,
            ran_local=self.runs_local,
            prompt_version=prompt_version,
        )


@dataclass(frozen=True)
class SkippedMember:
    """A member this run did not ask, and the reason the report has to carry."""

    member: Member
    reason: str


@dataclass(frozen=True)
class Roster:
    """The members an operator configured for one run, in the order they are asked."""

    members: tuple[Member, ...]

    def __post_init__(self) -> None:
        """Refuse a roster with nobody on it, or with two members a record cannot tell apart."""
        # n = 0 is a configuration error, not an empty council. Falling back to a
        # published vector and calling that an assessment is what the design
        # forbids by name.
        if not self.members:
            raise ValueError("A council needs at least one member; an empty roster cannot assess")
        refuse_repeated_names(self.members)


def members_to_ask(roster: Roster) -> tuple[Member, ...]:
    """Give the members this run may ask, refusing a run that can ask nobody."""
    asking = tuple(member for member in roster.members if member.may_run())
    if asking:
        return asking
    raise ValueError(
        "Every member of this roster is hosted without egress, so the run can ask nobody"
    )


def members_skipped(roster: Roster) -> tuple[SkippedMember, ...]:
    """Name the members `egress` stopped, so the report can say they were not asked.

    Only those. A member whose provider has no client here is also not asked, and
    `council.providers.unreachable_members` is what names both together.
    """
    return tuple(
        SkippedMember(member=member, reason=SKIPPED_WITHOUT_EGRESS)
        for member in roster.members
        if not member.may_run()
    )


def is_single_assessor(roster: Roster) -> bool:
    """Say whether `egress` leaves one member alone to answer, which is not a council."""
    # Asked rather than configured: a roster of three whose other two are hosted
    # without egress cross-checks nothing, and no reader should take
    # council-grade confidence from it. This ranges over egress alone; a run also
    # loses members whose provider has no client, so `CouncilRun.single_assessor`
    # is the stricter answer and the one a record should carry.
    return len(members_to_ask(roster)) == 1


def refuse_repeated_names(members: tuple[Member, ...]) -> None:
    """Refuse two members sharing a name, which no record could attribute apart."""
    names = sorted(member.name for member in members)
    repeated = sorted({name for name in names if names.count(name) > 1})
    if not repeated:
        return
    raise ValueError(f"{', '.join(repeated)} names more than one member of this roster")


def refuse_non_boolean(name: str, field: str, given: object) -> None:
    """Refuse a flag that is not a flag, which would make a refusal depend on truthiness."""
    if isinstance(given, bool):
        return
    raise TypeError(f"{name!r} must say {field} as true or false, not {type(given).__name__}")
