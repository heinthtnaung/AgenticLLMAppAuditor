"""Works out which package an import came from.

An import name is not a package name: `import yaml` comes from PyYAML. Getting
this wrong produces a mapping that looks complete and is not.

Resolution is deliberately not done with `importlib.metadata`: that reads the
auditor's own environment, which does not contain the audited app's
dependencies and must not, so it would answer from the wrong machine.
"""

import sys

from deps.requirements_parser import normalise_name

# PyPI imports whose package is not simply the normalised import name. Small
# and hand-checked; each entry is a fact about that ecosystem, not a guess.
# Applied to Python only: `yaml` and `dotenv` are real npm packages under their
# own names, so using this table there would rename them to PyPI distributions.
PYPI_IMPORT_NAME_EXCEPTIONS = {
    "yaml": "pyyaml",
    "dotenv": "python-dotenv",
    "sklearn": "scikit-learn",
    "bs4": "beautifulsoup4",
    "PIL": "pillow",
    "cv2": "opencv-python",
    "attr": "attrs",
    "dateutil": "python-dateutil",
}

# How a name was resolved, recorded so a reader can check the working.
BY_NORMALISED_NAME = "normalised_name"
BY_ALIAS_TABLE = "alias_table"
NOT_RESOLVED = "none"

NPM_SCOPE_PREFIX = "@"
NODE_PREFIX = "node:"
PYTHON = "python"

# Node's built-in modules. There is no `sys.stdlib_module_names` for
# JavaScript, so the list is written out; without it every `fs` or `path`
# import would look like a package the app forgot to declare.
NODE_BUILTINS = frozenset({
    "assert", "buffer", "child_process", "cluster", "console", "crypto",
    "dgram", "dns", "events", "fs", "http", "http2", "https", "net", "os",
    "path", "perf_hooks", "process", "querystring", "readline", "stream",
    "string_decoder", "timers", "tls", "url", "util", "v8", "vm", "worker_threads",
    "zlib",
})


def package_root(module: str, language: str) -> str:
    """Return the package a module path belongs to, per its ecosystem's rule."""
    if not module:
        return ""
    if language == PYTHON:
        return module.split(".")[0]
    parts = module.removeprefix(NODE_PREFIX).split("/")
    return "/".join(parts[:2]) if module.startswith(NPM_SCOPE_PREFIX) else parts[0]


def is_stdlib(root: str, language: str = PYTHON) -> bool:
    """Say whether a module is part of the language runtime, so no package exists.

    Language-specific on purpose: `fs` and `path` are Node builtins but mean
    nothing to Python, and asking Python's list about them would report them as
    packages the app failed to declare.
    """
    if language == PYTHON:
        return root in sys.stdlib_module_names
    return root.removeprefix(NODE_PREFIX) in NODE_BUILTINS


def resolve(module: str, language: str) -> tuple[str, str]:
    """Return the distribution name an import belongs to, and how it was decided."""
    root = package_root(module, language)
    if not root:
        return "", NOT_RESOLVED
    if language != PYTHON:
        return root, BY_NORMALISED_NAME
    if root in PYPI_IMPORT_NAME_EXCEPTIONS:
        return PYPI_IMPORT_NAME_EXCEPTIONS[root], BY_ALIAS_TABLE
    return normalise_name(root), BY_NORMALISED_NAME
