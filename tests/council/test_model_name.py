"""Guards on reading a model's name: its own name after the last "/", and any tag after that."""

import pytest

from council.model_name import family_of, last_part


@pytest.mark.parametrize(
    ("model", "own_name", "family"),
    [
        ("llama3.2", "llama3.2", "llama3.2"),
        ("qwen2.5:7b-instruct", "qwen2.5:7b-instruct", "qwen2.5"),
        ("library/qwen2.5:7b", "qwen2.5:7b", "qwen2.5"),
        ("myregistry:5000/model", "model", "model"),
        ("myregistry:5000/team/gemma4:latest", "gemma4:latest", "gemma4"),
    ],
    ids=["plain", "tagged", "namespaced", "registry-with-port", "registry-namespace-and-tag"],
)
def test_the_family_is_the_own_name_without_registry_namespace_or_tag(model, own_name, family):
    assert last_part(model) == own_name
    assert family_of(model) == family


def test_a_registry_s_port_is_never_read_as_a_tag_so_the_registry_is_no_family():
    # `split(":")[0]` gave "myregistry": every model it serves was one family.
    assert family_of("myregistry:5000/model") != "myregistry"
