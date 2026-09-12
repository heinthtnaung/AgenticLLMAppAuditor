"""What the web UI may ask for, and what it may not.

Deliberately free of FastAPI, so the refusals can be tested on a clean checkout
where the web extra is not installed -- and so the rules live somewhere a reader
can find them without reading routing code.

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

# What a target may be. `main.py` takes a path too, but a path arrives from a
# browser as text the server would resolve against its own filesystem, which is
# a different and much larger permission than "clone this public repository".
REQUIRED_SCHEME = "https://"


@dataclass(frozen=True)
class AuditRequest:
    """One audit the UI asked for."""

    url: str
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
        return said

    def to_argv(self) -> list[str]:
        """The command line this request means, for `main.build_parser`.

        Built for the real parser rather than assembled into a Namespace by
        hand: the parser owns the defaults, and a flag added to it later would
        leave a hand-built Namespace stale with nothing to say so.
        """
        argv = [self.url.strip()]
        argv += [flag for field, flag in PASS_THROUGH_FLAGS.items()
                 if getattr(self, field)]
        if self.compare_models and self.cloud_model.strip():
            argv += ["--cloud-model", self.cloud_model.strip()]
        return argv
