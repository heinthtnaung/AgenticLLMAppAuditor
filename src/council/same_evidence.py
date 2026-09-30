"""Two members quoting the same words of the advisory and reading different values from them.

A verified quotation proves the words are in the advisory, not that the value
read from them is right. Where two members' verified quotations are the same
words and their values differ, the evidence did not decide between them: one
sentence was read two ways, and a reader should see that.

**It is shown beside the council, never used by it.** Nothing in the council
reads this. The chairman has already ruled on the same replies, and its ruling
on a flagged metric is contested, since two verified quotations supporting
different values is what contested means. An escalation may still settle it,
and the flag stays, because it is about what the members read. Only members
count: the escalation model is not one.

**What "the same words" means.** Each quotation is folded as the quotation check
folds it (`council.evidence.normalise`: whitespace and typographic quotes, and
nothing that changes a word). Two are the same when one then equals the other or
appears inside it without cutting into a word: an end of the shorter that is a
word character may not sit beside another. Case is not folded, and the shorter
is matched as text, never as a pattern. So `network` is inside
`over the network.` and not inside `networks`, and `(PR:N)`, which begins and
ends with punctuation, is inside `privileges(PR:N)`.
"""

import re
from itertools import combinations
from typing import Sequence

from council.answer import MemberAnswer, MemberReply
from council.evidence import WORD_CHARACTER, is_quotation_from, normalise

# Where the shorter quotation begins or ends with a word character, no word
# character may sit just before or just after it: `path` is not in `paths`.
NO_WORD_BEFORE = r"(?<!\w)"
NO_WORD_AFTER = r"(?!\w)"


def read_differently(replies: Sequence[MemberReply], advisory_text: str) -> bool:
    """Say whether two members quoted the same verified words and read different values."""
    verified = [one for one in replies if is_verified_answer(one, advisory_text)]
    return any(
        one.value != other.value and same_words(one.evidence, other.evidence)
        for one, other in combinations(verified, 2)
    )


def is_verified_answer(reply: MemberReply, advisory_text: str) -> bool:
    """Say whether a reply is an answer whose quotation the advisory contains."""
    if not isinstance(reply, MemberAnswer):
        return False
    return is_quotation_from(reply.evidence, advisory_text)


def same_words(one: str, other: str) -> bool:
    """Say whether two quotations are the same words: one equal to, or inside, the other."""
    shorter, longer = sorted((normalise(one), normalise(other)), key=len)
    if not shorter:
        raise ValueError("A quotation with no text cannot be the same words as another")
    return re.search(whole_words(shorter), longer) is not None


def whole_words(quotation: str) -> str:
    """Give a pattern finding a quotation as text, never cutting into a word at either end."""
    before = NO_WORD_BEFORE if WORD_CHARACTER.match(quotation[0]) else ""
    after = NO_WORD_AFTER if WORD_CHARACTER.match(quotation[-1]) else ""
    return f"{before}{re.escape(quotation)}{after}"
