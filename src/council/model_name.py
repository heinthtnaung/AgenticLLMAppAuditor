"""How Ollama names a model: an optional registry and namespace, its own name, an optional tag.

In `myregistry:5000/team/qwen2.5:7b` the registry is `myregistry:5000`, the
namespace `team`, the model's own name `qwen2.5` and its tag `7b`. **A tag is
only ever in the last part of the path**, so the ":" of a registry's port is
never read as one. Both readers of a name go through here -- the tag Ollama
assumes (`cli.model_identity.tagged`) and the family a member is guessed to be
of (`council.providers.ollama_member`) -- so the two cannot split a name apart
differently.
"""

PATH_SEPARATOR = "/"
TAG_SEPARATOR = ":"


def last_part(model: str) -> str:
    """Give the last part of a model's path: its own name, and its tag where it has one."""
    return model.rsplit(PATH_SEPARATOR, 1)[-1]


def family_of(model: str) -> str:
    """Guess a model's family from its own name, without its registry, namespace or tag."""
    return last_part(model).split(TAG_SEPARATOR, 1)[0]
