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

MODEL_CLASSES = frozenset({
    "ChatOpenAI", "AzureChatOpenAI", "ChatLiteLLM", "ChatAnthropic",
    "ChatOllama", "Ollama", "ChatGoogleGenerativeAI", "ChatBedrockConverse",
    "OpenAI", "HuggingFaceHub", "LlamaCpp",
})

# --- Tool surfaces ---------------------------------------------------------
TOOL_DECORATORS = frozenset({"tool", "tools.tool", "langchain_core.tools.tool"})

TOOL_CLASSES = frozenset({
    "Tool", "StructuredTool", "BaseTool", "ShellTool", "PythonREPLTool",
    "PythonAstREPLTool", "QuerySQLDataBaseTool", "RequestsGetTool",
    "RequestsPostTool",
})

# Tools that hand the model shell, code, or network reach (LLM06 candidates).
HIGH_PRIVILEGE_TOOLS = frozenset({
    "ShellTool", "PythonREPLTool", "PythonAstREPLTool",
    "RequestsGetTool", "RequestsPostTool",
})

# --- Data source surfaces --------------------------------------------------
# Full dotted call names, mapped to how the surface is described.
DATA_SOURCE_CALLS = {
    "open": "file access",
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
}

# A web route handler receives untrusted request input.
ROUTE_DECORATOR_ROOTS = frozenset({"app", "router"})
HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "route"})
