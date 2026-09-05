"""Two written surface lists to map against the recorded bills of materials.

These replace `extract_repo` over the pinned apps, which was how the mapping
tests used to get a whole document to assert over. **They were written by the
same author as the mapping code**, so unlike the pinned apps they hold no
import shape nobody foresaw -- what they buy instead is that every one of the
five outcomes is reached, which the pinned apps managed only by luck.

Nothing here parses anything: a `Surface` is constructed directly, because what
the mapping reads off one is its `module`, its `language` and its `name`, and a
file to extract those from would only add a step that can go wrong.
"""

from artifacts.surface import (
    AGENT_DEF,
    DATA_SOURCE,
    PROMPT_TEMPLATE,
    TOOL_CALL,
    Surface,
)
from parsing.languages import PYTHON, TYPESCRIPT

# The audited app's own top-level modules, which is what makes `utils`
# first-party rather than an undeclared package.
LOCAL_MODULES = frozenset({"utils"})

# One Python surface per mapping outcome, against `dependency_fixtures`'
# recorded PyPI bill: langchain and langchain-litellm are declared there,
# `os` is the standard library, `utils` is the app's own, `yaml` resolves to
# PyYAML that no manifest lists, and `cursor.execute` resolves to nothing.
PYTHON_SURFACES = [
    Surface(AGENT_DEF, "ChatLiteLLM", "app.py", 10, PYTHON, "", "langchain_litellm"),
    Surface(PROMPT_TEMPLATE, "ChatPromptTemplate.from_template", "app.py", 12, PYTHON,
            "", "langchain.prompts"),
    Surface(DATA_SOURCE, "os.getenv", "app.py", 14, PYTHON, "", "os"),
    Surface(DATA_SOURCE, "read_config", "app.py", 16, PYTHON, "", "utils"),
    Surface(DATA_SOURCE, "yaml.load", "app.py", 18, PYTHON, "", "yaml"),
    Surface(DATA_SOURCE, "cursor.execute", "app.py", 20, PYTHON, "", ""),
    # An npm import against a PyPI bill: a name that resolves but cannot join.
    Surface(TOOL_CALL, "ChatOpenAI", "web.ts", 3, TYPESCRIPT, "", "@langchain/openai"),
]

# Four TypeScript surfaces against `dependency_fixtures`' recorded npm bill,
# one per join shape it holds -- one locked version, two, three -- plus a
# prompt string the app wrote itself, so the document has a first-party entry.
JS_SURFACES = [
    Surface(AGENT_DEF, "StateGraph", "src/agent.ts", 51, TYPESCRIPT, "",
            "@langchain/langgraph"),
    Surface(AGENT_DEF, "ChatOpenAI", "src/agent.ts", 20, TYPESCRIPT, "",
            "@langchain/openai"),
    Surface(DATA_SOURCE, "Client", "src/agent.ts", 8, TYPESCRIPT, "", "langsmith"),
    Surface(PROMPT_TEMPLATE, "systemPrompt", "src/agent.ts", 3, TYPESCRIPT, "", ""),
]
