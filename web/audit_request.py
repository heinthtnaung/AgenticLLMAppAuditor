"""What the web UI may ask for, and what it may not.

Deliberately free of FastAPI, so the refusals can be tested on a clean checkout
where the web extra is not installed -- and so the rules live somewhere a reader
can find them without reading routing code.

**Who ran the audit is deliberately not a field here.** `options` is stored as
exactly this dataclass so that a re-run is exact, and a name is an option of
nothing: the parser has nowhere to put it, and replaying options that carried
one would re-run the audit *as someone else*. It travels beside the request and
lands on the run record, which is where who-and-when belongs.

**A request here is not the same thing as a command line.** `main.py` puts the
two consequential options behind flags on the grounds that a flag is something a
reader sees in the command they typed; a checkbox posted by a page is not that.
So the page states what each one costs, `to_argv` never invents one that was not
asked for, and the README says plainly that this endpoint has no authentication.
"""

from dataclasses import dataclass

# The flags this wrapper is willing to pass through, mapped to the option the
# command line spells. Named here rather than built from the request's own
# field names: a field added to the dataclass should not silently become a
# command-line flag.
PASS_THROUGH_FLAGS = {
    "semantic_probe": "--semantic-probe",
    "draft_key": "--draft-key",
    "compare_models": "--compare-models",
}

# Options that carry a value rather than being present or absent. Named for the
# same reason the booleans are -- a field added to the dataclass should not
# silently become a command-line option -- and named as a set rather than a
# third hand-written branch in `to_argv`, which is where two of these already
# were heading.
PASS_THROUGH_VALUES = {
    "model": "--model",
    "cloud_model": "--cloud-model",
}

# A value option that only means something alongside another. `--cloud-model`
# names the hosted arm, which exists only under `--compare-models`.
REQUIRES = {"cloud_model": "compare_models"}

# What a target may be. `main.py` takes a path too, but a path arrives from a
# browser as text the server would resolve against its own filesystem, which is
# a different and much larger permission than "clone this public repository".
REQUIRED_SCHEME = "https://"


@dataclass(frozen=True)
class AuditRequest:
    """One audit the UI asked for."""

    url: str
    # A model this machine has pulled, or "" for the configured one. Empty is
    # not stored as a name: absent and "chose the default" are the same fact,
    # and the artifact records whichever model actually answered either way.
    model: str = ""
    semantic_probe: bool = False
    draft_key: bool = False
    compare_models: bool = False
    cloud_model: str = ""

    def refusals(self) -> list[str]:
        """Every reason this request will not be run, or an empty list."""
        said = []
        if not self.url.strip():
            said.append("no repository was given")
        elif not self.url.strip().startswith(REQUIRED_SCHEME):
            said.append(
                f"the repository must be an {REQUIRED_SCHEME} link. A filesystem "
                "path would be resolved against the server's own disk, which is a "
                "much larger permission than cloning a public repository")
        if self.cloud_model and not self.compare_models:
            said.append("a cloud model was named but model comparison is off")
        said += self._option_shaped_values()
        if self.model and not self._consults_a_model():
            said.append(
                "a local model was named but nothing here would consult one: an "
                "ordinary audit makes no model call. Turn on the semantic probe, "
                "a drafted key, or model comparison")
        return said

    def _option_shaped_values(self) -> list[str]:
        """Refuse a model name argparse would read as another option.

        These are the only two fields whose *text* reaches `main.build_parser`,
        and a value starting with `-` makes `parse_args` print usage and call
        `sys.exit`. `SystemExit` is a `BaseException`, so it escapes both
        `run_jobs`' catches: the worker thread dies, the slot is freed by the
        `finally`, and **the run row says `running` for ever** -- the state
        `run_record.INTERRUPTED` exists to clean up, which only happens when the
        store is next opened. A 400 naming the field is the honest answer, and
        the page's model picker is where this value comes from.
        """
        return [f"{field} may not start with '-': "
                f"the command line would read {getattr(self, field).strip()!r} as "
                "another option, not as a value"
                for field in PASS_THROUGH_VALUES
                if getattr(self, field).strip().startswith("-")]

    def _consults_a_model(self) -> bool:
        """Whether anything this request asked for actually calls a model."""
        return self.semantic_probe or self.draft_key or self.compare_models

    def to_argv(self) -> list[str]:
        """The command line this request means, for `main.build_parser`.

        Built for the real parser rather than assembled into a Namespace by
        hand: the parser owns the defaults, and a flag added to it later would
        leave a hand-built Namespace stale with nothing to say so.
        """
        argv = [self.url.strip()]
        argv += [flag for field, flag in PASS_THROUGH_FLAGS.items()
                 if getattr(self, field)]
        for field, option in PASS_THROUGH_VALUES.items():
            named = getattr(self, field).strip()
            needs = REQUIRES.get(field)
            if named and (needs is None or getattr(self, needs)):
                argv += [option, named]
        return argv
