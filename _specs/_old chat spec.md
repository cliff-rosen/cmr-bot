# Chat System Specification

## Table of Contents

1. [Overview & Architecture](#1-overview--architecture)
2. [Streaming Protocol](#2-streaming-protocol)
   - [SSE Format](#sse-format)
   - [Event Types](#event-types)
   - [Event Flow](#event-flow)
3. [Page-Aware Configuration](#3-page-aware-configuration)
   - [Backend: Page Registry](#backend-page-registry)
   - [Backend: Context Builders](#backend-context-builders)
   - [Frontend: Payload Handlers](#frontend-payload-handlers)
   - [Backend ↔ Frontend Mapping](#backend--frontend-mapping)
4. [Tool System](#4-tool-system)
   - [Backend: Tool Configuration](#backend-tool-configuration)
   - [Backend: Agent Loop](#backend-agent-loop)
   - [Tool Call Markers](#tool-call-markers)
   - [Frontend: Tool UI](#frontend-tool-ui)
5. [Response Payloads](#5-response-payloads)
   - [ChatResponsePayload Structure](#chatresponsepayload-structure)
   - [Suggested Values](#suggested-values)
   - [Suggested Actions](#suggested-actions)
   - [Custom Payloads](#custom-payloads)
6. [Frontend Implementation](#6-frontend-implementation)
   - [useGeneralChat Hook](#usegeneralchat-hook)
   - [ChatTray Component](#chattray-component)
7. [File Structure](#7-file-structure)
8. [TODO](#8-todo)

---

## 1. Overview & Architecture

The chat system provides streaming LLM interactions with tool support. It uses Server-Sent Events (SSE) to stream typed events from backend to frontend, following a discriminated union pattern for type safety.

The system is **page-aware**: each page registers its own configuration (context builders, payload types, tools) that customize chat behavior for that page's domain.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND                                    │
│  ┌─────────────┐    ┌──────────────────┐    ┌────────────────────────┐ │
│  │  ChatTray   │◄───│  useGeneralChat  │◄───│   Payload Handlers     │ │
│  │  Component  │    │      Hook        │    │   (per-page inline)    │ │
│  └─────────────┘    └──────────────────┘    └────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                ▲
                                │ SSE Stream
                                │
┌─────────────────────────────────────────────────────────────────────────┐
│                              BACKEND                                     │
│  ┌──────────────────┐    ┌─────────────┐    ┌────────────────────────┐ │
│  │ GeneralChatSvc   │───►│ Agent Loop  │───►│   Page Registry        │ │
│  │                  │    │             │    │   - Context Builders   │ │
│  │  Maps events to  │    │ Call Model  │    │   - PayloadConfigs     │ │
│  │  SSE format      │    │ → Tools     │    │   - ToolConfigs        │ │
│  │                  │    │ → Repeat    │    │   - ClientActions      │ │
│  └──────────────────┘    └─────────────┘    └────────────────────────┘ │
│                                │                                        │
│                                ▼                                        │
│                         ┌─────────────┐                                │
│                         │ Anthropic   │                                │
│                         │    API      │                                │
│                         └─────────────┘                                │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Streaming Protocol

### SSE Format

Events are sent as Server-Sent Events with JSON payloads:

```
data: {"type": "status", "message": "Thinking..."}

data: {"type": "text_delta", "text": "Hello"}

data: {"type": "complete", "payload": {...}}
```

Each event has a `type` field for discrimination, enabling type-safe handling via `switch (event.type)`.

### Event Types

| Event | Description | Key Fields |
|-------|-------------|------------|
| `status` | Status/thinking indicator | `message` |
| `text_delta` | Streaming text token | `text` |
| `tool_start` | Tool execution begins | `tool`, `input`, `tool_use_id` |
| `tool_progress` | Tool progress update | `tool`, `stage`, `message`, `progress` |
| `tool_complete` | Tool execution finished | `tool`, `index` |
| `complete` | Final response | `payload` (ChatResponsePayload) |
| `error` | Error occurred | `message` |
| `cancelled` | Request cancelled | (none) |

#### Event Schemas

```typescript
// Streaming text
{ "type": "text_delta", "text": "Hello" }

// Tool lifecycle
{ "type": "tool_start", "tool": "search_pubmed", "input": {"query": "..."}, "tool_use_id": "toolu_123" }
{ "type": "tool_progress", "tool": "search_pubmed", "stage": "searching", "message": "Found 15...", "progress": 0.5 }
{ "type": "tool_complete", "tool": "search_pubmed", "index": 0 }

// Final response
{ "type": "complete", "payload": { "message": "...", "suggested_values": [...], "custom_payload": {...} } }
```

### Event Flow

```
User sends message
        │
        ▼
┌───────────────┐
│    status     │  "Thinking..."
└───────────────┘
        │
        ▼
┌───────────────┐
│  text_delta   │  Streaming tokens...
│  text_delta   │
│  text_delta   │
└───────────────┘
        │
        ▼ (if tools requested)
┌───────────────┐
│  tool_start   │  Tool begins
│ tool_progress │  (optional updates)
│ tool_complete │  Tool done, emits [[tool:0]] marker
└───────────────┘
        │
        ▼ (loop back for more text/tools)
┌───────────────┐
│  text_delta   │  More streaming...
└───────────────┘
        │
        ▼
┌───────────────┐
│   complete    │  Final payload with message, suggestions, tool_history
└───────────────┘
```

---

## 3. Page-Aware Configuration

Each page can customize chat behavior by registering configuration on both backend and frontend.

### Backend: Page Registry

Location: `backend/services/chat_payloads/`

```
chat_payloads/
├── __init__.py          # Auto-imports all page configs
├── registry.py          # Core types and registry
├── edit_stream.py       # edit_research_stream page
├── streams_list.py      # streams list page
├── new_stream.py        # new stream page
└── reports.py           # reports page (has tools)
```

#### Core Types

```python
@dataclass
class PageConfig:
    payloads: List[PayloadConfig]           # Structured output types LLM can emit
    context_builder: Callable               # Builds system prompt context
    client_actions: List[ClientAction]      # Frontend-executable actions
    tools: List[ToolConfig]                 # LLM-callable tools
```

```python
@dataclass
class PayloadConfig:
    type: str                               # e.g., "schema_proposal"
    parse_marker: str                       # e.g., "SCHEMA_PROPOSAL:"
    llm_instructions: str                   # Prompt instructions for LLM
    parser: Callable[[str], Dict]           # Parses LLM output to payload
    relevant_tabs: Optional[List[str]]      # Tab filtering (None = all)
```

```python
@dataclass
class ClientAction:
    action: str                             # e.g., "close_chat"
    description: str                        # For LLM context
    parameters: Optional[List[str]]         # e.g., ["tab_name"]
```

#### Registration

Pages self-register on module import:

```python
# In edit_stream.py
register_page(
    page="edit_research_stream",
    payloads=EDIT_STREAM_PAYLOADS,
    context_builder=build_context,
    client_actions=EDIT_STREAM_CLIENT_ACTIONS,
    tools=None
)
```

#### Registry API

```python
get_page_payloads(page: str) -> List[PayloadConfig]
get_page_context_builder(page: str) -> Optional[Callable]
get_page_client_actions(page: str) -> List[ClientAction]
get_page_tools(page: str) -> List[ToolConfig]
has_page_payloads(page: str) -> bool
```

### Backend: Context Builders

Each page provides a function that builds the system prompt context based on current page state.

```python
def build_context(context: Dict[str, Any]) -> str:
    """Build context section for system prompt."""
    active_tab = context.get("active_tab", "semantic")

    if active_tab == "semantic":
        return _build_semantic_tab_context(context)
    elif active_tab == "retrieval":
        return _build_retrieval_tab_context(context)
    # ...
```

**Input** (from frontend):
```python
{
    "current_page": "edit_research_stream",
    "active_tab": "semantic",
    "current_schema": {...},
    "report_id": 123
}
```

**Output** (injected into system prompt):
```
The user is on the SEMANTIC SPACE tab (Layer 1).

Current values:
- Stream Name: Cancer Research Monitor
- Purpose: Track oncology breakthroughs
- Topics: 5 topics defined

SEMANTIC SPACE defines the canonical ground truth...
```

### Frontend: Payload Handlers

The frontend uses **inline registration** where each page passes handlers as props to ChatTray.

#### PayloadHandler Interface

```typescript
// In types/chat.ts
interface PayloadHandler {
    render: (
        payload: any,
        callbacks: { onAccept?: (data: any) => void; onReject?: () => void }
    ) => React.ReactNode;
    onAccept?: (payload: any, pageState?: any) => void;
    onReject?: (payload: any) => void;
    renderOptions?: {
        panelWidth?: string;      // e.g., "500px"
        headerTitle?: string;     // e.g., "Schema Proposal"
        headerIcon?: string;      // e.g., "📋"
    };
}
```

#### Registration Pattern

```tsx
// In EditStreamPage.tsx
<ChatTray
    initialContext={{
        current_page: "edit_research_stream",
        active_tab: activeTab,
        current_schema: schema
    }}
    payloadHandlers={{
        schema_proposal: {
            render: (payload, callbacks) => (
                <SchemaProposalCard
                    proposal={payload}
                    onAccept={callbacks.onAccept}
                    onReject={callbacks.onReject}
                />
            ),
            onAccept: handleSchemaProposalAccept,
            onReject: handleSchemaProposalReject,
            renderOptions: {
                panelWidth: '500px',
                headerTitle: 'Schema Proposal',
                headerIcon: '📋'
            }
        }
    }}
/>
```

#### Handler Flow

1. Message received with `custom_payload.type = "schema_proposal"`
2. ChatTray looks up `payloadHandlers["schema_proposal"]`
3. Opens floating panel, calls `handler.render(payload.data, callbacks)`
4. User clicks Accept → calls `handler.onAccept(payload)`
5. Page applies changes to its state

### Backend ↔ Frontend Mapping

| Page | Backend PayloadConfig | Frontend Handler | Card Component |
|------|----------------------|------------------|----------------|
| EditStreamPage | `schema_proposal` | `schema_proposal` | `SchemaProposalCard` |
| EditStreamPage | `presentation_categories` | `presentation_categories` | `PresentationCategoriesCard` |
| EditStreamPage | `retrieval_proposal` | `retrieval_proposal` | `RetrievalProposalCard` |
| StreamsPage | `stream_suggestions` | `stream_suggestions` | `StreamSuggestionsCard` |
| StreamsPage | `portfolio_insights` | `portfolio_insights` | `PortfolioInsightsCard` |
| CreateStreamPage | `stream_template` | `stream_template` | `StreamTemplateCard` |
| CreateStreamPage | `topic_suggestions` | `topic_suggestions` | `TopicSuggestionsCard` |
| ReportsPage | (tools only) | `pubmed_article` | `PubMedArticleCard` |

---

## 4. Tool System

Tools allow the LLM to take actions (search, fetch data, etc.) during a conversation.

### Backend: Tool Configuration

#### ToolConfig

```python
@dataclass
class ToolConfig:
    name: str                               # e.g., "search_pubmed"
    description: str                        # For LLM context
    input_schema: Dict[str, Any]            # JSON schema for parameters
    executor: Callable                      # (params, db, user_id, context) -> str | ToolResult
```

#### ToolResult

Tools can return simple text or structured data for the frontend:

```python
@dataclass
class ToolResult:
    text: str                               # Text result for LLM to reason about
    payload: Optional[Dict[str, Any]]       # Structured data for frontend card
```

#### Example Tool

```python
# In reports.py
ToolConfig(
    name="search_pubmed",
    description="Search PubMed for research articles.",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "max_results": {"type": "integer", "default": 10}
        },
        "required": ["query"]
    },
    executor=execute_search_pubmed
)

def execute_search_pubmed(params, db, user_id, context) -> str:
    query = params.get("query")
    articles = pubmed_service.search(query)
    return f"Found {len(articles)} articles: ..."

def execute_get_pubmed_article(params, db, user_id, context) -> ToolResult:
    pmid = params.get("pmid")
    article = pubmed_service.get(pmid)

    # Text for LLM
    text = f"Title: {article.title}\nAbstract: {article.abstract}"

    # Structured payload for frontend
    payload = {
        "type": "pubmed_article",
        "data": {"pmid": pmid, "title": article.title, ...}
    }

    return ToolResult(text=text, payload=payload)
```

### Backend: Agent Loop

Location: `backend/services/agent_loop.py`

The agent loop is a reusable async generator that handles multi-turn tool execution.

#### Event Types

```python
@dataclass
class AgentThinking(AgentEvent): message: str
@dataclass
class AgentTextDelta(AgentEvent): text: str
@dataclass
class AgentToolStart(AgentEvent): tool_name: str; tool_input: Dict; tool_use_id: str
@dataclass
class AgentToolProgress(AgentEvent): tool_name: str; stage: str; message: str; progress: float
@dataclass
class AgentToolComplete(AgentEvent): tool_name: str; result_text: str; result_data: Any
@dataclass
class AgentComplete(AgentEvent): text: str; tool_calls: List[Dict]
@dataclass
class AgentCancelled(AgentEvent): text: str; tool_calls: List[Dict]
@dataclass
class AgentError(AgentEvent): error: str
```

#### Loop Structure

```python
async def run_agent_loop(...) -> AsyncGenerator[AgentEvent, None]:
    for iteration in range(1, max_iterations + 1):
        # 1. Call model
        async for event in _call_model(client, api_kwargs, stream_text):
            if isinstance(event, _ModelResult):
                response = event.response
            else:
                yield event  # AgentTextDelta

        # 2. Check for tool use
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        if not tool_use_blocks:
            yield AgentComplete(text=collected_text, tool_calls=tool_call_history)
            return

        # 3. Process tools
        async for event in _process_tools(tool_use_blocks, tools, db, user_id, context):
            if isinstance(event, _ToolsResult):
                tool_results = event.tool_results
                tool_call_history.extend(event.tool_records)
            else:
                yield event  # AgentToolStart, AgentToolComplete

        # 4. Update messages for next iteration
        _append_tool_exchange(messages, response, tool_results)
```

#### Helper Functions

| Function | Purpose |
|----------|---------|
| `_build_api_kwargs()` | Build Anthropic API call kwargs |
| `_call_model()` | Stream LLM response, yield text events |
| `_process_tools()` | Execute tools, yield tool events |
| `_append_tool_exchange()` | Add assistant + tool_result messages |

#### Usage in GeneralChatService

```python
async for event in run_agent_loop(
    client=self.async_client,
    model=CHAT_MODEL,
    max_tokens=CHAT_MAX_TOKENS,
    max_iterations=MAX_TOOL_ITERATIONS,
    system_prompt=system_prompt,
    messages=messages,
    tools=tools_by_name,
    db=self.db,
    user_id=self.user_id,
    context=request.context,
    stream_text=True
):
    # Map AgentEvent to SSE StreamEvent
    if isinstance(event, AgentTextDelta):
        yield TextDeltaEvent(text=event.text).model_dump_json()
    elif isinstance(event, AgentToolStart):
        yield ToolStartEvent(tool=event.tool_name, ...).model_dump_json()
    elif isinstance(event, AgentToolComplete):
        yield ToolCompleteEvent(tool=event.tool_name, index=tool_index).model_dump_json()
        yield TextDeltaEvent(text=f"[[tool:{tool_index}]]").model_dump_json()
        tool_index += 1
    # ...
```

### Tool Call Markers

Markers are inserted into the text stream to indicate where tool results should render.

#### Format

```
[[tool:N]]
```

Where `N` is a zero-indexed integer matching the `index` field in `tool_complete` events.

#### Flow

1. LLM streams: `"Let me search for that..."`
2. LLM requests tool use
3. Backend emits `tool_start`
4. Backend executes tool
5. Backend emits `tool_complete` with `index: 0`
6. Backend emits `text_delta` with `"[[tool:0]]"`
7. Loop continues...
8. Final `complete` event includes `tool_history` in `custom_payload`

#### Tool History in Complete Event

```json
{
  "type": "complete",
  "payload": {
    "message": "Let me search...\n\n[[tool:0]]\n\nI found 5 articles.",
    "custom_payload": {
      "type": "tool_history",
      "data": [
        {
          "tool_name": "search_pubmed",
          "input": {"query": "CRISPR"},
          "output": "Found 5 articles: ..."
        }
      ]
    }
  }
}
```

### Frontend: Tool UI

#### During Execution

Tool progress is shown as an amber card with spinner:

```
┌─────────────────────────────────────────┐
│ ⟳ search_pubmed                     [×] │
│   Searching PubMed...                   │
└─────────────────────────────────────────┘
```

Visible even while text is streaming (separate from thinking indicator).

#### After Completion (Inline Cards)

Markers are replaced with expandable tool cards:

```
┌─────────────────────────────────────────┐
│ 🔧 search_pubmed                    [▼] │
├─────────────────────────────────────────┤
│ Input: {"query": "CRISPR"}              │
│ Output: Found 5 articles...             │
└─────────────────────────────────────────┘
```

- Collapsed by default (just header)
- Click to expand input/output
- Uses `tool_history[N]` from `custom_payload`

---

## 5. Response Payloads

The `complete` event contains a structured payload with the final response.

### ChatResponsePayload Structure

```typescript
interface ChatResponsePayload {
    message: string;                        // LLM text (may contain [[tool:N]] markers)
    suggested_values?: SuggestedValue[];    // Quick-select options
    suggested_actions?: SuggestedAction[];  // Action buttons
    custom_payload?: CustomPayload;         // Structured data (tool_history, page payloads)
}
```

### Suggested Values

Quick-select options the user can click to send as their next message.

```json
{
  "suggested_values": [
    {"label": "Yes, proceed", "value": "yes"},
    {"label": "No, cancel", "value": "no"},
    {"label": "Tell me more", "value": "tell me more about this"}
  ]
}
```

Rendered as clickable chips below the message.

### Suggested Actions

Action buttons that trigger handlers.

```json
{
  "suggested_actions": [
    {
      "label": "Apply Changes",
      "action": "apply_schema",
      "handler": "server",
      "data": {"schema_id": 123},
      "style": "primary"
    },
    {
      "label": "Close Chat",
      "action": "close_chat",
      "handler": "client",
      "style": "secondary"
    }
  ]
}
```

| Field | Description |
|-------|-------------|
| `handler: "client"` | Execute on frontend (must be registered via ClientAction) |
| `handler: "server"` | Send action back to backend for processing |
| `style` | `"primary"` / `"secondary"` / `"warning"` |

### Custom Payloads

Structured data for rich UI rendering.

```typescript
interface CustomPayload {
    type: string;   // Payload type identifier
    data: any;      // Type-specific data
}
```

#### Payload Types

| Type | Source | Description |
|------|--------|-------------|
| `tool_history` | Agent loop | Array of tool calls with inputs/outputs |
| `schema_proposal` | LLM output | Proposed schema changes |
| `validation_results` | LLM output | Errors, warnings, suggestions |
| `presentation_categories` | LLM output | Article categorization |
| `retrieval_proposal` | LLM output | Search query suggestions |
| `pubmed_article` | Tool result | Article card data |
| `stream_suggestions` | LLM output | Research stream recommendations |

#### Example

```json
{
  "custom_payload": {
    "type": "schema_proposal",
    "data": {
      "proposed_changes": {
        "stream_name": "Oncology Monitor",
        "purpose": "Track cancer treatment advances"
      },
      "confidence": "high",
      "reasoning": "Based on your description..."
    }
  }
}
```

---

## 6. Frontend Implementation

### useGeneralChat Hook

Location: `frontend/src/hooks/useGeneralChat.ts`

#### State

```typescript
{
    messages: GeneralChatMessage[];     // Conversation history
    isLoading: boolean;                 // Request in progress
    streamingText: string;              // Current streaming response
    statusText: string | null;          // "Thinking..." status
    activeToolProgress: {               // Current tool execution
        toolName: string;
        updates: ToolProgressEvent[];
    } | null;
    error: string | null;
}
```

#### Event Handling

```typescript
for await (const event of generalChatApi.streamMessage(request, signal)) {
    switch (event.type) {
        case 'status':
            setStatusText(event.message);
            break;

        case 'text_delta':
            setStatusText(null);
            collectedText += event.text;
            setStreamingText(collectedText);
            break;

        case 'tool_start':
            setActiveToolProgress({ toolName: event.tool, updates: [] });
            break;

        case 'tool_progress':
            // Append to activeToolProgress.updates
            break;

        case 'tool_complete':
            setActiveToolProgress(null);
            break;

        case 'complete':
            // Add message to history with payload
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: event.payload.message,
                suggested_values: event.payload.suggested_values,
                suggested_actions: event.payload.suggested_actions,
                custom_payload: event.payload.custom_payload,
                timestamp: new Date().toISOString()
            }]);
            setStreamingText('');
            setIsLoading(false);
            break;

        case 'error':
            setError(event.message);
            setIsLoading(false);
            break;
    }
}
```

### ChatTray Component

Location: `frontend/src/components/chat/ChatTray.tsx`

#### Props

```typescript
interface ChatTrayProps {
    initialContext: Record<string, any>;
    payloadHandlers?: Record<string, PayloadHandler>;
    hidden?: boolean;
}
```

#### Visual States

| State | Condition | Display |
|-------|-----------|---------|
| Empty | No messages | Welcome prompt |
| User Message | `role === 'user'` | Right-aligned blue bubble |
| Thinking | `isLoading && !streamingText && !activeToolProgress` | Gray bubble with dots |
| Tool Progress | `isLoading && activeToolProgress` | Amber card with spinner |
| Streaming | `streamingText` | White bubble with pulsing dots |
| Final Message | `role === 'assistant'` | White bubble + chips + cards |

#### Floating Payload Panel

When a custom payload with a registered handler is received:

```
┌─────────────────────────────────────────┐
│ 📋 Schema Proposal                  [×] │
├─────────────────────────────────────────┤
│                                         │
│     [PayloadHandler.render() output]    │
│                                         │
│     ┌──────────┐    ┌──────────┐       │
│     │  Accept  │    │  Reject  │       │
│     └──────────┘    └──────────┘       │
└─────────────────────────────────────────┘
```

---

## 7. File Structure

```
backend/
├── schemas/
│   └── general_chat.py              # Domain types + Stream event types
├── services/
│   ├── agent_loop.py                # Generic agent loop (reusable)
│   ├── general_chat_service.py      # Chat service using agent loop
│   └── chat_payloads/
│       ├── __init__.py              # Auto-imports page configs
│       ├── registry.py              # Core registry classes
│       ├── edit_stream.py           # edit_research_stream config
│       ├── streams_list.py          # streams list config
│       ├── new_stream.py            # new stream config
│       └── reports.py               # reports config (has tools)
└── routers/
    └── general_chat.py              # SSE endpoint

frontend/
├── lib/api/
│   └── generalChatApi.ts            # Stream event types + API client
├── hooks/
│   └── useGeneralChat.ts            # Chat state management
├── components/chat/
│   ├── ChatTray.tsx                 # Main chat UI
│   ├── ToolCallCard.tsx             # Inline tool card (TODO)
│   ├── SchemaProposalCard.tsx       # Payload card
│   ├── PresentationCategoriesCard.tsx
│   ├── StreamSuggestionsCard.tsx
│   └── ...
└── types/
    └── chat.ts                      # Domain types + PayloadHandler
```

---

## 8. TODO

### Backend

1. **Emit tool markers**: On `tool_complete`, emit `[[tool:N]]` in text stream
2. **Include tool_history**: Add `tool_history` to `custom_payload` in `complete` event
3. **Streaming tools**: Consider yielding `tool_progress` during long-running tool execution

### Frontend

1. **ToolCallCard component**: Create inline expandable card for `[[tool:N]]` markers
2. **Parse markers**: Replace `[[tool:N]]` in message text with `ToolCallCard`
3. **Built-in handler**: Register `tool_history` as built-in payload handler in ChatTray
