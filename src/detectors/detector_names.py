"""The framework names each detector looks for, defined once."""

# --- Prompt surfaces -------------------------------------------------------
PROMPT_CLASSES = frozenset({
    "PromptTemplate", "ChatPromptTemplate", "FewShotPromptTemplate",
    "PipelinePromptTemplate", "SystemMessagePromptTemplate",
    "HumanMessagePromptTemplate", "AIMessagePromptTemplate",
    "ChatMessagePromptTemplate", "MessagesPlaceholder",
    "SystemMessage", "HumanMessage",
})

# A string assigned to a variable containing one of these reads as a prompt.
PROMPT_NAME_HINTS = (
    "prompt", "template", "system_msg", "system_message",
    "instruction", "persona", "preamble",
)

# --- Agent surfaces --------------------------------------------------------
AGENT_FACTORIES = frozenset({
    "create_react_agent", "initialize_agent", "AgentExecutor",
    "ConversationalChatAgent", "create_openai_functions_agent",
    "create_openai_tools_agent", "create_tool_calling_agent",
    "create_structured_chat_agent", "create_sql_agent", "create_csv_agent",
    "create_pandas_dataframe_agent", "LLMChain", "ConversationChain",
    "SQLDatabaseChain", "PALChain", "RetrievalQA", "StateGraph",
    "MessageGraph",
})

# Matched on the call root, so a factory function belongs here beside the
# classes: `init_chat_model("openai:gpt-4")` builds a model client exactly as
# `ChatOpenAI(...)` does, and a surface the extractor misses is a surface no
# check can reach.
MODEL_CLASSES = frozenset({
    "ChatOpenAI", "AzureChatOpenAI", "ChatLiteLLM", "ChatAnthropic",
    "ChatOllama", "Ollama", "ChatGoogleGenerativeAI", "ChatBedrockConverse",
    "OpenAI", "HuggingFaceHub", "LlamaCpp", "init_chat_model",
})

# --- Tool surfaces ---------------------------------------------------------
TOOL_DECORATORS = frozenset({"tool", "tools.tool", "langchain_core.tools.tool"})

TOOL_CLASSES = frozenset({
    "Tool", "StructuredTool", "BaseTool", "ShellTool", "PythonREPLTool",
    "PythonAstREPLTool", "QuerySQLDataBaseTool", "RequestsGetTool",
    "RequestsPostTool",
    # MCP clients: a server the agent reaches for tools it does not define
    # itself. Recorded as tool surfaces, and lifted into the AIBOM as
    # MCP_SERVER components -- the proposal names MCP servers among the AI
    # components a bill of materials should hold.
    "MultiServerMCPClient", "ClientSession", "MCPToolkit", "StdioServerParameters",
    # LangGraph's prebuilt tool runner, and the Tavily web-search tools. Both
    # were misses recorded in `docs/TODO.md`: an app using them had tool
    # surfaces the extractor never saw, so every tool check stayed silent on it.
    # `ToolNode` is filed here while `detector_names_js.py` files it under
    # AGENT_FACTORIES, so one construct extracts as a different kind per
    # language. Pinned by a test and open in `docs/TODO.md`; not decided here.
    "ToolNode", "TavilySearch", "TavilySearchResults",
})

# Tools that hand the model shell, code, or network reach (LLM06 candidates).
# `TavilySearch` is deliberately absent: a fixed search API is not the
# arbitrary-URL reach `RequestsGetTool` hands the model, and adding it here
# would change what LLM06 reports.
HIGH_PRIVILEGE_TOOLS = frozenset({
    "ShellTool", "PythonREPLTool", "PythonAstREPLTool",
    "RequestsGetTool", "RequestsPostTool",
})

# --- Data source surfaces --------------------------------------------------
# Full dotted call names, mapped to how the surface is described.
# Dataset loaders: a named corpus the application pulls in whole, as opposed to
# a query against data it already holds. Kept apart from DATA_SOURCE_METHODS
# because the AIBOM records these as DATASET components and a `cursor.execute`
# is not a dataset.
DATASET_CALLS = frozenset({"load_dataset", "load_from_disk"})

# The tool-class names that are an MCP client rather than a tool of the app's
# own. A subset of TOOL_CLASSES, guarded at import in `artifacts/aibom.py`.
MCP_CLASSES = frozenset({
    "MultiServerMCPClient", "ClientSession", "MCPToolkit", "StdioServerParameters"})

DATA_SOURCE_CALLS = {
    # The bare-call spelling of each dataset loader. The receiver spellings
    # (`datasets.load_dataset`, `ds.load_from_disk`) are carried by
    # DATA_SOURCE_METHODS instead, which matches a leaf and so survives any
    # receiver -- including an aliased import. Spelling a module prefix into
    # *this* table would cover one alias and miss the rest, and would count one
    # published API name twice in the registered-name total.
    "load_dataset": "dataset loaded by name",
    "load_from_disk": "dataset loaded from disk",
    "json.load": "json file read",
    "yaml.load": "yaml file read",
    "yaml.safe_load": "yaml file read",
    "os.getenv": "environment variable read",
    "os.environ.get": "environment variable read",
    "requests.get": "outbound http request",
    "requests.post": "outbound http request",
    "httpx.get": "outbound http request",
    "httpx.post": "outbound http request",
    "urllib.request.urlopen": "outbound http request",
    "st.chat_input": "end-user chat input",
    "st.text_input": "end-user text input",
    "st.text_area": "end-user text input",
    "st.file_uploader": "user-uploaded file",
}

# open() is deliberately not in the table above: its mode says whether data
# comes in or goes out, so its detail is computed rather than looked up.
OPEN_CALL = "open"

# Method names that read outside data regardless of the object they sit on.
DATA_SOURCE_METHODS = {
    "execute": "database query",
    "executemany": "database query",
    "from_uri": "database connection handed to a model",
    "fetchall": "database read",
    "fetchone": "database read",
    "load": "document loader read",
    "load_and_split": "document loader read",
    "get_relevant_documents": "retrieval read",
    "similarity_search": "retrieval read",
    "as_retriever": "retrieval read",
    "load_from_disk": "dataset loaded from disk",
    "load_dataset": "dataset loaded by name",
}

# A web route handler receives untrusted request input.
ROUTE_DECORATOR_ROOTS = frozenset({"app", "router"})
HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "route"})
