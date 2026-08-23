"""The JavaScript and TypeScript framework names each detector looks for.

The mirror of detector_names.py. Names are drawn from the LangChain.js API.
The ones exercised by a corpus fixture or a test are the ones the evaluation
can speak for; the rest are there so a real app is not missed, and are listed
as an untested-coverage gap in docs/TODO.md.
"""

from detectors.detector_names import PROMPT_NAME_HINTS  # noqa: F401  (language-neutral, shared)

# --- Prompt surfaces -------------------------------------------------------
# Object keys that carry prompt text in a chat message: {role, content}.
MESSAGE_TEXT_KEYS = frozenset({"content", "text"})
MESSAGE_ROLE_KEY = "role"

PROMPT_CLASSES = frozenset({
    "ChatPromptTemplate", "PromptTemplate", "SystemMessagePromptTemplate",
    "HumanMessagePromptTemplate", "SystemMessage", "HumanMessage",
})

# --- Agent surfaces --------------------------------------------------------
AGENT_FACTORIES = frozenset({
    "StateGraph", "MessageGraph", "createReactAgent", "AgentExecutor",
    "createOpenAIFunctionsAgent", "createToolCallingAgent", "RunnableSequence",
    # Wires the already-counted tools into the graph; it defines no new
    # capability, so counting it as a tool would double-count them.
    "ToolNode",
})

MODEL_CLASSES = frozenset({
    "ChatOpenAI", "ChatAnthropic", "ChatOllama", "ChatGoogleGenerativeAI",
    "ChatBedrockConverse", "OpenAI",
})

# --- Tool surfaces ---------------------------------------------------------
TOOL_CLASSES = frozenset({
    "DynamicStructuredTool", "DynamicTool", "TavilySearchResults",
    "Calculator", "WebBrowser", "ShellTool", "JavaScriptInterpreter",
})

TOOL_FACTORIES = frozenset({"tool", "createTool"})

# Tools that hand the model shell, code, or network reach (LLM06 candidates).
HIGH_PRIVILEGE_TOOLS = frozenset({"WebBrowser", "ShellTool", "JavaScriptInterpreter"})

# --- Data source surfaces --------------------------------------------------
# Full call names, mapped to how the surface is described.
DATA_SOURCE_CALLS = {
    "fetch": "outbound http request",
    "axios.get": "outbound http request",
    "axios.post": "outbound http request",
    "fs.readFile": "file read",
    "fs.readFileSync": "file read",
    "fs.promises.readFile": "file read",
}

# Method names that read outside data regardless of the object they sit on.
# Member expressions, not calls: matched by text prefix rather than call name.
DATA_SOURCE_MEMBERS = {
    "process.env": "environment variable read",
}

# Note: `invoke` is deliberately absent. In LangChain.js it is the universal
# call for models, chains and retrievers alike, so matching it reports every
# model call as a data source.
DATA_SOURCE_METHODS = {
    "query": "database query",
    "execute": "database query",
    "load": "document loader read",
    "similaritySearch": "retrieval read",
    "asRetriever": "retrieval read",
    "getRelevantDocuments": "retrieval read",
}
