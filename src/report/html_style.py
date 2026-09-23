"""The page's one stylesheet, inlined, and the class that colours a severity band.

**Inlined because a scan runs offline.** The report is made behind a corporate
proxy and read from a file, so a stylesheet fetched over the network is a report
that arrives unreadable in the environment it was produced for.

**Every colour is a token, and every token is defined in both themes.** A token
defined in the light block and missed in the dark one is how a card ends up with
black text on a black background, so `tests/report/test_html_style.py` holds the
two blocks to the same set of names.

**A published CVSS score and an Organisation Risk Score never share a shape.**
They are different claims on different scales -- `docs/SCORING_MODEL.md` refuses
to merge them -- so one is a square outlined chip and the other a solid pill,
and the band colour they share cannot make them read as one badge.
"""

# The CVSS bands plus the organisation ones, which are the same names without
# `None`. A band with no colour is refused rather than rendered unstyled.
BANDS: tuple[str, ...] = ("Critical", "High", "Medium", "Low", "None")

BAND_CLASSES = {name: f"band-{name.lower()}" for name in BANDS}


def band_class(band: str) -> str:
    """Give the class that colours one band, refusing a band the palette cannot reach."""
    named = BAND_CLASSES.get(band)
    if named is None:
        named_bands = ", ".join(BANDS)
        raise ValueError(f"{band!r} is no band this palette has a colour for: {named_bands}")
    return named


STYLESHEET = """
:root {
  color-scheme: light dark;
  --page-bg: #f7f8fa;
  --page-fg: #14181d;
  --muted-fg: #5a626c;
  --card-bg: #ffffff;
  --card-border: #dbe0e6;
  --rule: #e9ecf1;
  --chip-bg: #eef1f5;
  --chip-border: #ccd3db;
  --code-bg: #f2f4f7;
  --alarm-bg: #fdecea;
  --alarm-fg: #7f1d12;
  --alarm-border: #f0b4ab;
  --note-bg: #f1f4f8;
  --note-border: #c6cedb;
  --band-critical-bg: #8c1d13; --band-critical-fg: #ffffff;
  --band-high-bg: #a8551b;     --band-high-fg: #ffffff;
  --band-medium-bg: #74600f;   --band-medium-fg: #ffffff;
  --band-low-bg: #1f6b45;      --band-low-fg: #ffffff;
  --band-none-bg: #4c545e;     --band-none-fg: #ffffff;
}
@media (prefers-color-scheme: dark) {
  :root {
    --page-bg: #12151a;
    --page-fg: #e6e9ee;
    --muted-fg: #9aa3ae;
    --card-bg: #1a1f26;
    --card-border: #2c333d;
    --rule: #262e38;
    --chip-bg: #222932;
    --chip-border: #39424e;
    --code-bg: #1e242c;
    --alarm-bg: #3a1a16;
    --alarm-fg: #ffb4a8;
    --alarm-border: #6b2b22;
    --note-bg: #1c222a;
    --note-border: #333c47;
    --band-critical-bg: #f0a79b; --band-critical-fg: #2a0b06;
    --band-high-bg: #f0c39a;     --band-high-fg: #2e1705;
    --band-medium-bg: #e3d194;   --band-medium-fg: #2b2405;
    --band-low-bg: #a5d9bd;      --band-low-fg: #08301d;
    --band-none-bg: #c2c9d2;     --band-none-fg: #1a1f26;
  }
}

.band-critical { --band-bg: var(--band-critical-bg); --band-fg: var(--band-critical-fg); }
.band-high     { --band-bg: var(--band-high-bg);     --band-fg: var(--band-high-fg); }
.band-medium   { --band-bg: var(--band-medium-bg);   --band-fg: var(--band-medium-fg); }
.band-low      { --band-bg: var(--band-low-bg);      --band-fg: var(--band-low-fg); }
.band-none     { --band-bg: var(--band-none-bg);     --band-fg: var(--band-none-fg); }

* { box-sizing: border-box; }
body {
  margin: 0; background: var(--page-bg); color: var(--page-fg);
  font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
  font-size: 15px; line-height: 1.5;
}
main { max-width: 60rem; margin: 0 auto; padding: 1.25rem 1rem 4rem; }
h1 { font-size: 1.4rem; margin: 0 0 .35rem; }
h2 { font-size: 1rem; text-transform: uppercase; letter-spacing: .06em; margin: 0 0 .3rem; }
h3 { font-size: 1rem; font-weight: 600; margin: 0 0 .35rem; }
p { margin: 0 0 .5rem; }
ul { list-style: none; margin: 0; padding: 0; }
section { margin-top: 2rem; }
code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .82em;
  background: var(--code-bg); border: 1px solid var(--rule); border-radius: 4px;
  padding: .05rem .3rem; overflow-wrap: anywhere;
}
.lede { color: var(--muted-fg); margin: 0 0 .75rem; }
.separator { color: var(--muted-fg); margin: 0 .4rem; }
.run { border-bottom: 1px solid var(--rule); padding-bottom: 1rem; }
.run + .note { margin-top: 1rem; }
.tools { color: var(--muted-fg); font-size: .9em; }
.alarm {
  background: var(--alarm-bg); color: var(--alarm-fg); border: 1px solid var(--alarm-border);
  border-radius: 6px; padding: .5rem .7rem; font-weight: 600;
}
.note {
  background: var(--note-bg); border: 1px solid var(--note-border);
  border-radius: 6px; padding: .6rem .8rem; color: var(--page-fg);
}
.finding, .risk-entry, .council > li {
  background: var(--card-bg); border: 1px solid var(--card-border);
  border-radius: 8px; padding: .7rem .85rem; margin-bottom: .55rem;
}
.finding-name { display: flex; flex-wrap: wrap; gap: .15rem .6rem; align-items: baseline; }
.advisory { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  overflow-wrap: anywhere; }
.component { color: var(--muted-fg); font-weight: 500; }
.spread { color: var(--muted-fg); font-size: .9em; margin: 0 0 .4rem; }
.sources > li, .risk-scores > li {
  display: flex; flex-wrap: wrap; gap: .35rem .6rem; align-items: center;
  padding: .3rem 0; border-top: 1px solid var(--rule);
}
.sources > li:first-child, .risk-scores > li:first-child { border-top: 0; }
.source-name { font-weight: 600; min-width: 4rem; }
.refusal { color: var(--muted-fg); font-size: .88em; }
.cvss, .risk {
  display: inline-flex; align-items: baseline; gap: .35rem;
  padding: .1rem .55rem; white-space: nowrap; font-variant-numeric: tabular-nums;
}
.cvss { background: var(--chip-bg); border: 1px solid var(--chip-border);
  border-left: 4px solid var(--band-bg); border-radius: 4px; }
.cvss .band { color: var(--band-bg); font-weight: 600; }
.risk { background: var(--band-bg); color: var(--band-fg); border-radius: 999px; font-weight: 600; }
.scale { font-size: .7rem; text-transform: uppercase; letter-spacing: .08em; opacity: .8; }
.value { font-weight: 700; }
.not-scored, .flag {
  display: inline-block; border-radius: 4px; padding: .05rem .45rem;
  font-size: .85em; color: var(--muted-fg);
}
.not-scored { border: 1px dashed var(--chip-border); }
.flag { border: 1px solid var(--chip-border); background: var(--chip-bg); }
details { margin-top: .45rem; border-top: 1px solid var(--rule); padding-top: .4rem; }
summary { cursor: pointer; color: var(--muted-fg); font-size: .88em; }
.category { margin-top: .6rem; }
.category-name { font-weight: 600; font-size: .9em; }
.category-total { color: var(--muted-fg); font-size: .85em; }
.answers > li { display: flex; flex-wrap: wrap; gap: .25rem .6rem; padding: .12rem 0;
  font-size: .88em; }
.answer-id { font-weight: 600; min-width: 3.5rem; }
.answer-text { flex: 1 1 16rem; }
.answer-value { min-width: 4rem; }
.answer-weight { color: var(--muted-fg); }
.weighting { color: var(--muted-fg); font-size: .85em; margin: .6rem 0 0; }
.counts > li, .absences > li, .artifacts > li { padding: .25rem 0; }
.absence-what { font-weight: 600; display: block; }
.absence-why { color: var(--muted-fg); display: block; }
.counts details { border-top: 0; padding-top: 0; margin-top: 0; }
.counts summary { color: var(--page-fg); font-size: 1em; }
.council-name { margin: 0 0 .2rem; }
.council-settled { color: var(--muted-fg); font-size: .88em; margin: 0; }
.bases > li { color: var(--muted-fg); font-size: .88em; padding: .05rem 0 .05rem .9rem; }
.basis-count { font-weight: 600; margin-right: .45rem; }
.not-asked { color: var(--muted-fg); font-size: .88em; margin: .8rem 0 .2rem; }
.not-asked > li { padding: .15rem 0; font-size: .88em; }
.metric > summary { color: var(--page-fg); font-size: 1em; }
.ruling { color: var(--muted-fg); font-size: .9em; margin: .4rem 0 0; }
.members > li {
  display: flex; flex-wrap: wrap; gap: .2rem .6rem; align-items: baseline;
  padding: .3rem 0; font-size: .9em; border-top: 1px solid var(--rule);
}
.members > li:first-child { border-top: 0; }
.member-name { font-weight: 600; min-width: 9rem; }
.member-value { font-weight: 700; }
.verified { color: var(--muted-fg); }
.unverified { color: var(--alarm-fg); font-weight: 600; }
.evidence {
  flex: 1 1 100%; margin: .1rem 0 0; padding: .1rem 0 .1rem .6rem;
  border-left: 2px solid var(--chip-border); color: var(--muted-fg);
  overflow-wrap: anywhere;
}
@media (max-width: 30rem) {
  main { padding: 1rem .7rem 3rem; }
  .source-name, .answer-id, .answer-value, .member-name { min-width: 0; }
}
"""
