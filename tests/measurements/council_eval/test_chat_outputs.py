"""Guards on where the chat steps write: every output checked before anything is written."""

import pytest

import eval_samples  # noqa: F401  (puts the evaluation package on the path)
from council_eval.chat_outputs import refuse_inside, refuse_unwritable


def test_outputs_each_new_in_a_folder_that_is_there_pass(tmp_path):
    refuse_unwritable((tmp_path / "a.jsonl", tmp_path / "b.jsonl"))
    refuse_inside(tmp_path / "prompts", tmp_path / "manifest.json")


def test_one_path_named_twice_is_refused_however_it_is_spelled(tmp_path):
    with pytest.raises(ValueError, match="name one path twice"):
        refuse_unwritable((tmp_path / "a.jsonl", tmp_path / "x" / ".." / "a.jsonl"))


def test_an_output_already_there_is_refused(tmp_path):
    (tmp_path / "b.jsonl").write_text("", encoding="utf-8")
    with pytest.raises(FileExistsError, match="b.jsonl already exists"):
        refuse_unwritable((tmp_path / "a.jsonl", tmp_path / "b.jsonl"))


def test_an_output_with_no_folder_to_go_in_is_refused(tmp_path):
    with pytest.raises(FileNotFoundError, match="no folder exists to hold .*gone/b.jsonl"):
        refuse_unwritable((tmp_path / "a.jsonl", tmp_path / "gone" / "b.jsonl"))


# The last is inside only once resolved: `prompts` is not among its parents as written.
INSIDE = (
    "prompts/m.json", "prompts/a/b/m.json", "prompts/../prompts/m.json",
    "elsewhere/../prompts/m.json",
)


@pytest.mark.parametrize("inside", INSIDE)
def test_a_file_anywhere_inside_the_folder_kept_for_pasting_is_refused(tmp_path, inside):
    with pytest.raises(ValueError, match="which holds only what is safe to paste"):
        refuse_inside(tmp_path / "prompts", tmp_path / inside)


def test_a_file_beside_the_folder_whose_name_starts_the_same_is_not_inside_it(tmp_path):
    refuse_inside(tmp_path / "prompts", tmp_path / "prompts-manifest.json")
