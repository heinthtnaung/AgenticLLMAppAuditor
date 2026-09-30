"""Guards on the `chat-prompts` step: a folder of prompts alone, a manifest apart, same bytes."""

import json

import pytest

import chat_samples
from council_eval import commands

TWO_ITEMS = chat_samples.TWO_ITEMS


def run_step(tmp_path, out: str, manifest: str) -> None:
    """Run the step over two sample items, into a folder and a manifest under `tmp_path`."""
    dataset = tmp_path / "dataset.json"
    if not dataset.exists():
        chat_samples.dataset_file(tmp_path, TWO_ITEMS)
    commands.main(
        ["chat-prompts", "--dataset", str(dataset),
         "--out", str(tmp_path / out), "--manifest", str(tmp_path / manifest)]
    )


def export(tmp_path, name: str = "a"):
    """Export the prompts of two sample items, and give the folder and the manifest."""
    run_step(tmp_path, f"prompts-{name}", f"manifest-{name}.json")
    return tmp_path / f"prompts-{name}", tmp_path / f"manifest-{name}.json"


def test_the_folder_holds_one_prompt_per_item_and_order_and_nothing_else(tmp_path):
    out, _ = export(tmp_path)
    expected = chat_samples.prompts(TWO_ITEMS)
    assert sorted(path.name for path in out.iterdir()) == sorted(one.file for one in expected)
    assert (out / expected[1].file).read_text(encoding="utf-8") == expected[1].text


def test_the_manifest_names_each_file_s_advisory_order_id_and_version(tmp_path):
    _, manifest = export(tmp_path)
    entries = json.loads(manifest.read_text(encoding="utf-8"))["prompts"]
    first = chat_samples.prompts(TWO_ITEMS)[0]
    assert entries[0] == {
        "file": first.file, "advisory": "CVE-2026-0001", "order": "forward",
        "prompt_id": first.prompt_id, "prompt_sha256": first.sha256,
        "prompt_version": "chat-all-base-metrics-1", "bytes": len(first.text.encode("utf-8")),
    }
    assert [one["order"] for one in entries] == ["forward", "reversed"] * 2


def test_the_same_dataset_gives_the_same_bytes(tmp_path):
    first_out, first_manifest = export(tmp_path, "a")
    second_out, second_manifest = export(tmp_path, "b")
    assert first_manifest.read_bytes() == second_manifest.read_bytes()
    names = sorted(path.name for path in first_out.iterdir())
    first = [(first_out / one).read_bytes() for one in names]
    assert first == [(second_out / one).read_bytes() for one in names]


def test_the_step_says_how_many_prompts_and_bytes_and_that_the_manifest_is_not_pasted(
    tmp_path, capsys
):
    export(tmp_path)
    said = capsys.readouterr().out
    size = sum(len(one.text.encode("utf-8")) for one in chat_samples.prompts(TWO_ITEMS))
    assert f"4 prompts for 2 advisories, {size} bytes in all" in said
    assert "is not for pasting" in said


def test_a_folder_already_there_is_not_written_into(tmp_path):
    export(tmp_path)
    with pytest.raises(FileExistsError):
        run_step(tmp_path, "prompts-a", "other.json")


def test_a_manifest_already_there_is_not_rewritten_and_no_prompt_is_written(tmp_path):
    export(tmp_path)
    with pytest.raises(FileExistsError, match="manifest-a.json already exists"):
        run_step(tmp_path, "fresh", "manifest-a.json")
    assert not (tmp_path / "fresh").exists()


@pytest.mark.parametrize("manifest", ("prompts/manifest.json", "prompts/deeper/manifest.json"))
def test_a_manifest_inside_the_folder_of_prompts_is_refused_and_nothing_is_written(
    tmp_path, manifest
):
    with pytest.raises(ValueError, match=f"{manifest} would be written inside .*prompts, which"):
        run_step(tmp_path, "prompts", manifest)
    assert not (tmp_path / "prompts").exists()


def test_a_manifest_with_no_folder_to_go_in_leaves_no_prompt_folder_behind(tmp_path):
    with pytest.raises(FileNotFoundError, match="no folder exists to hold .*missing/manifest.json"):
        run_step(tmp_path, "prompts", "missing/manifest.json")
    assert not (tmp_path / "prompts").exists()
