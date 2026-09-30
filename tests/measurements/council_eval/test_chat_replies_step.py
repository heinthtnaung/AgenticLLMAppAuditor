"""Guards on the `chat-replies` step: two passes the other steps read unchanged, or nothing."""

import shutil
import socket

import pytest

import chat_samples
from council_eval import chat_replies_step, commands
from council_eval.chat_reply import read_chat_reply
from council_eval.chat_reply_file import RefusedReply, read_saved_reply

FIXTURES = (chat_samples.FORWARD_FIXTURE, chat_samples.REVERSED_FIXTURE)


@pytest.fixture(autouse=True)
def no_git(monkeypatch):
    """Record a fixed commit, so these tests run in an export with no git repository."""
    monkeypatch.setattr(chat_replies_step, "git_output", chat_samples.no_git)


def imported(tmp_path, extra: dict[str, str] | None = None):
    """Import the two fixtures, and any extra replies, and give the dataset and both passes."""
    folder = tmp_path / "replies"
    folder.mkdir()
    for one in FIXTURES:
        shutil.copy(one, folder / one.name)
    for name, text in (extra or {}).items():
        chat_samples.write_reply(folder, name, text)
    dataset = chat_samples.dataset_file(tmp_path)
    forward, reversed_ = tmp_path / "forward.jsonl", tmp_path / "reversed.jsonl"
    commands.main(
        ["chat-replies", "--dataset", str(dataset), "--replies", str(folder),
         "--forward-out", str(forward), "--reversed-out", str(reversed_)]
    )
    return dataset, forward, reversed_


def printed(capsys, *argv: str) -> list[str]:
    """Run one step and give what it printed, a line each."""
    commands.main(list(argv))
    return capsys.readouterr().out.splitlines()


def test_the_fixtures_answer_the_sample_advisory_s_two_prompts():
    named = [read_chat_reply(read_saved_reply(one)).prompt_id for one in FIXTURES]
    assert named == [one.prompt_id for one in chat_samples.prompts()], (
        "the chat prompt's words moved: re-save the fixtures' prompt_id from `chat-prompts`"
    )


def test_the_import_says_what_it_wrote_what_it_cannot_show_and_what_it_counted(tmp_path, capsys):
    imported(tmp_path)
    said = capsys.readouterr().out
    assert "2 replies of 'fixture-model (hand-written, not a measurement)'" in said
    assert "not the local council's member-base-metric-3" in said
    assert "web browsing: not checked" in said
    assert "weights, temperature and seed unknown" in said
    assert f"  forward pass: 8 calls written to {tmp_path / 'forward.jsonl'}" in said
    assert f"  reversed pass: 8 calls written to {tmp_path / 'reversed.jsonl'}" in said
    rows = [line.split() for line in said.splitlines()]
    assert ["reversed", "6", "4", "2", "1", "1", "1"] in rows
    assert ["AV", "0", "1", "0"] in rows


def test_score_reads_a_pasted_pass_unchanged_and_prints_its_limits(tmp_path, capsys):
    dataset, forward, _ = imported(tmp_path)
    capsys.readouterr()
    out = printed(capsys, "score", "--dataset", str(dataset), "--replies", str(forward))
    assert "  prompt_version: chat-all-base-metrics-1" in out
    assert "  temperature: unknown" in out
    assert f"ROSTER {chat_samples.FIXTURE_MODEL}  (1 items)" in out
    member_row = [line.split()[-7:] for line in out if line.startswith(chat_samples.FIXTURE_MODEL)]
    assert ["S", "0", "1", "0", "0", "0", "U"] in member_row


def test_order_checked_and_grades_read_the_two_passes_unchanged(tmp_path, capsys):
    dataset, forward, reversed_ = imported(tmp_path)
    capsys.readouterr()
    pair = ("--dataset", str(dataset), "--forward", str(forward), "--reversed", str(reversed_))
    checked = printed(capsys, "order-checked", *pair)
    assert f"ROSTER {chat_samples.FIXTURE_MODEL}, order-checked  (1 items)" in checked
    rows = [line.split()[-5:] for line in checked if line.startswith(chat_samples.FIXTURE_MODEL)]
    assert ["AV", "0", "1", "0", "0"] in rows
    graded = printed(capsys, "grades", *pair)
    assert "  prompt_version: chat-all-base-metrics-1+reversed-1" in graded


def test_the_same_replies_give_the_same_passes_byte_for_byte(tmp_path):
    (tmp_path / "one").mkdir()
    (tmp_path / "two").mkdir()
    _, *first = imported(tmp_path / "one")
    _, *second = imported(tmp_path / "two")
    assert [one.read_bytes() for one in first] == [one.read_bytes() for one in second]


def test_a_reply_that_says_it_searched_the_web_is_imported_like_any_other(tmp_path, capsys):
    # A known gap, asserted so that closing it turns this red: nothing in a
    # reply's words is read for browsing, so a chat that searched is not caught.
    browsed = read_saved_reply(chat_samples.FORWARD_FIXTURE).reply.replace(
        "Here is my assessment", "I searched the web and found the published score. Here it is"
    )
    folder = tmp_path / "replies"
    folder.mkdir()
    chat_samples.write_reply(folder, "forward.txt", chat_samples.HEADER + browsed)
    shutil.copy(chat_samples.REVERSED_FIXTURE, folder / "reversed.txt")
    dataset = chat_samples.dataset_file(tmp_path)
    commands.main(
        ["chat-replies", "--dataset", str(dataset), "--replies", str(folder),
         "--forward-out", str(tmp_path / "f.jsonl"), "--reversed-out", str(tmp_path / "r.jsonl")]
    )
    assert (tmp_path / "f.jsonl").exists()


def test_a_refused_reply_leaves_neither_pass_written(tmp_path):
    stray = {"stray.txt": chat_samples.saved_text("ffffffffffffffff")}
    with pytest.raises(RefusedReply, match="^stray.txt: names PROMPT-ID"):
        imported(tmp_path, stray)
    assert not (tmp_path / "forward.jsonl").exists()
    assert not (tmp_path / "reversed.jsonl").exists()


def test_a_folder_holding_anything_but_replies_is_refused(tmp_path):
    with pytest.raises(ValueError, match="holds notes.md; a replies folder holds replies only"):
        imported(tmp_path, {"notes.md": "a note"})


def test_a_pass_already_written_is_not_rewritten(tmp_path):
    (tmp_path / "reversed.jsonl").write_text("an earlier pass", encoding="utf-8")
    with pytest.raises(FileExistsError, match="reversed.jsonl already exists"):
        imported(tmp_path)
    assert not (tmp_path / "forward.jsonl").exists()


def test_a_pass_with_no_folder_to_go_in_leaves_the_other_pass_unwritten(tmp_path):
    dataset = chat_samples.dataset_file(tmp_path)
    folder = chat_samples.answer_both(tmp_path / "replies")
    forward, reversed_ = tmp_path / "forward.jsonl", tmp_path / "missing" / "reversed.jsonl"
    with pytest.raises(FileNotFoundError, match="no folder exists to hold .*missing/reversed"):
        commands.main(
            ["chat-replies", "--dataset", str(dataset), "--replies", str(folder),
             "--forward-out", str(forward), "--reversed-out", str(reversed_)]
        )
    assert not forward.exists()


def test_one_file_for_both_passes_is_refused(tmp_path):
    dataset = chat_samples.dataset_file(tmp_path)
    same = str(tmp_path / "both.jsonl")
    with pytest.raises(ValueError, match="name one path twice"):
        commands.main(
            ["chat-replies", "--dataset", str(dataset), "--replies", str(tmp_path),
             "--forward-out", same, "--reversed-out", same]
        )


def test_an_empty_folder_is_refused(tmp_path):
    dataset = chat_samples.dataset_file(tmp_path)
    (tmp_path / "empty").mkdir()
    with pytest.raises(ValueError, match="holds no replies"):
        commands.main(
            ["chat-replies", "--dataset", str(dataset), "--replies", str(tmp_path / "empty"),
             "--forward-out", str(tmp_path / "f"), "--reversed-out", str(tmp_path / "r")]
        )


def test_no_step_of_the_chat_path_opens_a_connection(tmp_path, capsys, monkeypatch):
    def refuse(*given, **named):
        """Fail any attempt to open a connection."""
        raise AssertionError("a chat step tried to reach the network")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    dataset, forward, reversed_ = imported(tmp_path)
    commands.main(["chat-prompts", "--dataset", str(dataset), "--out", str(tmp_path / "p"),
                   "--manifest", str(tmp_path / "m.json")])
    commands.main(["score", "--dataset", str(dataset), "--replies", str(forward)])
    commands.main(["order-checked", "--dataset", str(dataset), "--forward", str(forward),
                   "--reversed", str(reversed_)])
