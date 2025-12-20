# Chat System Specification

## Table of Contents

1. [Overview & Architecture](#1-overview--architecture)
2. [Streaming Protocol](#2-streaming-protocol)
   - [SSE Format](#sse-format)
   - [Event Types](#event-types)
   - [Event Flow](#event-flow)
3. [Tool System](#3-tool-system)
   - [Backend: Tool Configuration](#backend-tool-configuration)
   - [Backend: Tool Registry](#backend-tool-registry)
   - [Streaming Tools](#streaming-tools)
   - [Tool Execution](#tool-execution)
4. [Workspace System](#4-workspace-system)
   - [Workspace Modes](#workspace-modes)
   - [Payload View Registry](#payload-view-registry)
   - [Workflow View Registry](#workflow-view-registry)
   - [Adding New Payload Types](#adding-new-payload-types)
5. [Response Payloads](#5-response-payloads)
   - [ChatResponsePayload Structure](#chatresponsepayload-structure)
   - [WorkspacePayload Structure](#workspacepayload-structure)
   - [Tool History](#tool-history)
6. [Frontend Implementation](#6-frontend-implementation)
   - [useGeneralChat Hook](#usegeneralchat-hook)
   - [MainPage Layout](#mainpage-layout)
   - [ChatPanel Component](#chatpanel-component)
   - [WorkspacePanel Component](#workspacepanel-component)
7. [Backend Implementation](#7-backend-implementation)
   - [GeneralChatService](#generalchatservice)
   - [Agent Loop Integration](#agent-loop-integration)
   - [Conversation Persistence](#conversation-persistence)
8. [File Structure](#8-file-structure)

---

## 1. Overview & Architecture

The chat system provides streaming LLM interactions with tool support using a **workspace-centric** architecture. It uses Server-Sent Events (SSE) to stream typed events from backend to frontend, following a discriminated union pattern for type safety.

The system is **tool-centric** rather than page-aware: tools are globally registered and return workspace payloads that are displayed in a unified workspace panel.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                 MAINPAGE                                       │
│  ┌────────────┐  ┌────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │ Sidebar    │  │  ChatPanel     │  │  WorkspacePanel  │  │ ContextPanel │  │
│  │            │  │                │  │                  │  │              │  │
│  │ Convo List │  │ useGeneralChat │  │ View Registry    │  │ Tools/Assets │  │
│  └────────────┘  └────────────────┘  └──────────────────┘  └──────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
                                ▲
                                │ SSE Stream
                                │
┌──────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND                                          │
│  ┌──────────────────┐    ┌─────────────┐    ┌────────────────────────┐      │
│  │ GeneralChatSvc   │───►│ Agent Loop  │───►│   Tool Registry        │      │
│  │                  │    │             │    │   - Global tools       │      │
│  │  Maps events to  │    │ Call Model  │    │   - Streaming support  │      │
│  │  SSE format      │    │ → Tools     │    │   - workspace_payload  │      │
│  │                  │    │ → Repeat    │    └────────────────────────┘      │
│  └──────────────────┘    └─────────────┘                                     │
│                                │                                              │
│                                ▼                                              │
│                         ┌─────────────┐                                      │
│                         │ Anthropic   │                                      │
│                         │    API      │                                      │
│                         └─────────────┘                                      │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Key Architectural Decisions

| Aspect | Design Choice |
|--------|---------------|
| **Tool Registration** | Global registry - tools available regardless of UI state |
| **Payload Handling** | View registry maps payload types to components |
| **Workspace Display** | Unified WorkspacePanel with discriminated union modes |
| **State Management** | useGeneralChat hook with conversation persistence |
| **Streaming** | Generator-based tools yield ToolProgress updates |

---

## 2. Streaming Protocol

### SSE Format

Events are sent as Server-Sent Events with JSON payloads:

```
data: {"type": "status", "message": "Thinking..."}

data: {"type": "text_delta", "text": "Hello"}

data: {"type": "tool_progress", "tool": "analyze_reviews", "stage": "phase1", "message": "Getting overview...", "progress": 0.25}

data: {"type": "complete", "payload": {...}}
```

Each event has a `type` field for discrimination, enabling type-safe handling via `switch (event.type)`.

### Event Types

| Event | Description | Key Fields |
|-------|-------------|------------|
| `status` | Status/thinking indicator | `message` |
| `text_delta` | Streaming text token | `text` |
| `tool_start` | Tool execution begins | `tool`, `input`, `tool_use_id` |
| `tool_progress` | Tool progress update | `tool`, `stage`, `message`, `progress`, `data` |
| `tool_complete` | Tool execution finished | `tool`, `index` |
| `complete` | Final response | `payload` (ChatResponsePayload) |
| `error` | Error occurred | `message` |
| `cancelled` | Request cancelled | (none) |

#### Event Schemas

```typescript
// Backend: schemas/general_chat.py
// Frontend: lib/api/generalChatApi.ts

// Streaming text
{ "type": "text_delta", "text": "Hello" }

// Tool lifecycle with progress
{ "type": "tool_start", "tool": "analyze_reviews", "input": {"business_name": "..."}, "tool_use_id": "toolu_123" }
{ "type": "tool_progress", "tool": "analyze_reviews", "stage": "phase2_negative", "message": "Fetching negative reviews...", "progress": 0.4, "data": {"negative_count": 15} }
{ "type": "tool_complete", "tool": "analyze_reviews", "index": 0 }

// Final response with workspace_payload
{
  "type": "complete",
  "payload": {
    "message": "I analyzed the reviews...",
    "conversation_id": 123,
    "workspace_payload": { "type": "review_analysis", "title": "...", "content": "...", "data": {...} },
    "custom_payload": { "type": "tool_history", "data": [...] }
  }
}
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
│ tool_progress │  Stage updates with progress %
│ tool_progress │  More updates...
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
│   complete    │  Final payload with workspace_payload
└───────────────┘
```

---

## 3. Tool System

Tools are capabilities the agent can invoke regardless of UI state. They are globally registered and can return workspace payloads for rich visualization.

### Backend: Tool Configuration

Location: `backend/tools/registry.py`

```python
@dataclass
class ToolProgress:
    """Progress update from a streaming tool."""
    stage: str                          # Current stage name
    message: str                        # Human-readable status
    data: Optional[Dict[str, Any]]      # Structured data for UI
    progress: Optional[float]           # 0-1 progress indicator

@dataclass
class ToolResult:
    """Result from a tool execution."""
    text: str                           # Text result for LLM
    data: Optional[Dict[str, Any]]      # Structured data
    workspace_payload: Optional[Dict]   # Payload to display in workspace

@dataclass
class ToolConfig:
    """Configuration for a tool the agent can use."""
    name: str                           # Tool name (e.g., "analyze_reviews")
    description: str                    # Description for LLM
    input_schema: Dict[str, Any]        # JSON schema for parameters
    executor: Callable                  # Function that executes the tool
    output_schema: Optional[Dict]       # JSON schema for validation
    category: str = "general"           # Tool category
    streaming: bool = False             # If True, yields ToolProgress
```

### Backend: Tool Registry

```python
# Global registry instance
_tool_registry = ToolRegistry()

def register_tool(tool: ToolConfig):
    """Register a tool in the global registry."""
    _tool_registry.register(tool)

def get_all_tools() -> List[ToolConfig]:
    """Get all registered tools."""
    return _tool_registry.get_all()

def get_tools_for_anthropic() -> List[Dict[str, Any]]:
    """Get all tools in Anthropic API format."""
    return _tool_registry.to_anthropic_format()
```

### Streaming Tools

Streaming tools yield `ToolProgress` updates before returning the final `ToolResult`:

```python
def execute_analyze_reviews(
    params: Dict[str, Any],
    db: Any,
    user_id: int,
    context: Dict[str, Any]
) -> Generator[ToolProgress, None, ToolResult]:
    """
    Human-intuition review analysis with 4-phase streaming.
    """
    yield ToolProgress(
        stage="phase1_overview",
        message="Getting business overview...",
        data={"phase": 1}
    )

    # ... do work ...

    yield ToolProgress(
        stage="phase2_negative",
        message=f"Found {count} negative reviews",
        progress=0.5,
        data={"negative_count": count}
    )

    # ... more work ...

    return ToolResult(
        text="Analysis complete...",
        data=result.to_dict(),
        workspace_payload={
            "type": "review_analysis",
            "title": f"Review Analysis: {business_name}",
            "content": verdict.summary,
            "data": result.to_dict()
        }
    )
```

### Tool Execution

Location: `backend/tools/executor.py`

The executor handles both streaming and non-streaming tools:

```python
async def execute_streaming_tool(
    tool_config: ToolConfig,
    tool_input: Dict[str, Any],
    db: Any,
    user_id: int,
    context: Dict[str, Any],
    cancellation_token: Optional[CancellationToken] = None
) -> AsyncGenerator[Union[ToolProgress, Tuple[str, Any, Any]], None]:
    """
    Execute a streaming tool, yielding progress updates and finally the result.

    Yields:
        ToolProgress for progress updates
        (text, data, workspace_payload) tuple as final result
    """
```

Key features:
- Runs tool executor in separate thread via `asyncio.to_thread`
- Supports cancellation via `cancellation_token`
- Handles both generator (streaming) and direct return (non-streaming) tools
- Validates output against `output_schema` if defined

---

## 4. Workspace System

The workspace system provides a unified panel for displaying tool results and other payloads.

### Workspace Modes

Location: `frontend/src/lib/workspace/workspaceMode.ts`

```typescript
export type WorkspaceMode =
    | { mode: 'empty' }
    | { mode: 'workflow'; instance: WorkflowInstanceState; handlers: WorkflowHandlers }
    | { mode: 'workflow_loading'; handlers?: WorkflowHandlers | null }
    | { mode: 'tool'; tool: ToolCall }
    | { mode: 'tool_history'; history: ToolCall[] }
    | { mode: 'payload'; payload: WorkspacePayload };
```

The `getWorkspaceMode()` function determines the current mode based on state, with explicit priority:

1. Workflow loading (processing but no instance yet)
2. Active workflow instance
3. Single tool inspection
4. Tool history inspection
5. Payload display
6. Empty state (default)

### Payload View Registry

Location: `frontend/src/lib/workspace/workspaceRegistry.tsx`

Maps payload types to their view components:

```typescript
export const payloadViewRegistry: PayloadViewRegistry = {
    // Agent creation/update
    'agent_create': AgentPayloadView,
    'agent_update': AgentPayloadView,

    // Table display
    'table': TablePayloadView,

    // Research workflow
    'research': ResearchWorkflowView,
    'research_result': ResearchResultView,

    // Review analysis
    'review_collection': ReviewCollectionView,
    'review_analysis': ReviewAnalysisView,

    // Entity verification
    'entity_verification': EntityVerificationView,

    // Workflow graph design
    'workflow_graph': WorkflowGraphView,

    // Standard types (draft, summary, data, code) use StandardPayloadView fallback
};

export function getPayloadView(payloadType: string): React.ComponentType<PayloadViewProps> {
    return payloadViewRegistry[payloadType] || StandardPayloadView;
}
```

### Workflow View Registry

For custom workflow execution views:

```typescript
export const workflowViewRegistry: WorkflowViewRegistry = {
    'vendor_finder': VendorFinderWorkflowView,
    // Other workflows use generic WorkflowExecutionView
};

export function getWorkflowView(workflowId: string): React.ComponentType<WorkflowViewProps> {
    return workflowViewRegistry[workflowId] || WorkflowExecutionView;
}
```

### Adding New Payload Types

1. **Backend: Return workspace_payload from tool**
   ```python
   return ToolResult(
       text="...",
       workspace_payload={
           "type": "my_new_type",
           "title": "My Title",
           "content": "Summary text",
           "data": { ... }
       }
   )
   ```

2. **Frontend: Create view component**
   ```typescript
   // components/panels/workspace/MyNewTypeView.tsx
   export default function MyNewTypeView({ payload }: PayloadViewProps) {
       const data = payload.data as MyNewTypeData;
       return <div>...</div>;
   }
   ```

3. **Register in workspace registry**
   ```typescript
   // lib/workspace/workspaceRegistry.tsx
   export const payloadViewRegistry: PayloadViewRegistry = {
       // ... existing entries
       'my_new_type': MyNewTypeView,
   };
   ```

4. **Add type config for styling**
   ```typescript
   // components/panels/workspace/types.ts
   export const payloadTypeConfig: Record<string, PayloadTypeConfig> = {
       // ... existing entries
       my_new_type: {
           icon: MyIcon,
           color: 'text-blue-500',
           bg: 'bg-blue-50 dark:bg-blue-900/20',
           border: 'border-blue-200 dark:border-blue-800',
           label: 'My New Type',
           editable: false
       }
   };
   ```

5. **Add TypeScript interface**
   ```typescript
   // types/chat.ts
   export type WorkspacePayloadType = '...' | 'my_new_type';

   export interface MyNewTypeData {
       // ... fields
   }
   ```

---

## 5. Response Payloads

### ChatResponsePayload Structure

```typescript
// Backend: schemas/general_chat.py
class ChatResponsePayload(BaseModel):
    message: str                                    # LLM text (may contain [[tool:N]] markers)
    conversation_id: Optional[int]                  # Conversation this belongs to
    suggested_values: Optional[List[SuggestedValue]]
    suggested_actions: Optional[List[SuggestedAction]]
    custom_payload: Optional[CustomPayload]         # Tool history or other custom data
    workspace_payload: Optional[Any]                # Direct workspace payload from tools

// Frontend: types/chat.ts
interface GeneralChatMessage {
    role: 'user' | 'assistant';
    content: string;
    timestamp: string;
    suggested_values?: SuggestedValue[];
    suggested_actions?: SuggestedAction[];
    custom_payload?: CustomPayload;
    workspace_payload?: WorkspacePayload;
}
```

### WorkspacePayload Structure

```typescript
export interface WorkspacePayload {
    type: WorkspacePayloadType;
    title: string;
    content: string;
    data?: any;                          // Structured data for the view
    agent_data?: AgentPayloadData;       // For agent_create/agent_update
    table_data?: TablePayloadData;       // For table type
    research_data?: ResearchWorkflow;    // For research workflow
    // ... other type-specific fields
}

export type WorkspacePayloadType =
    | 'draft' | 'summary' | 'data' | 'code'
    | 'agent_create' | 'agent_update'
    | 'table' | 'research' | 'research_result'
    | 'workflow_graph'
    | 'review_collection' | 'review_analysis';
```

### Tool History

Tool calls are tracked and included in the final response:

```typescript
// custom_payload in complete event
{
    "type": "tool_history",
    "data": [
        {
            "tool_name": "analyze_reviews",
            "input": { "business_name": "...", "location": "...", "source": "yelp" },
            "output": "Analysis complete...",
            "workspace_payload": { "type": "review_analysis", ... }
        }
    ]
}
```

Tool markers `[[tool:N]]` in the message text can be replaced with inline tool cards using `tool_history[N]`.

---

## 6. Frontend Implementation

### useGeneralChat Hook

Location: `frontend/src/hooks/useGeneralChat.ts`

#### State

```typescript
{
    // Chat state
    messages: GeneralChatMessage[];
    context: Record<string, any>;
    isLoading: boolean;
    error: string | null;
    streamingText: string;
    statusText: string | null;
    activeToolProgress: ActiveToolProgress | null;

    // Conversation persistence
    conversationId: number | null;
    conversations: Conversation[];
    isLoadingConversation: boolean;
    isLoadingConversations: boolean;
}

interface ActiveToolProgress {
    toolName: string;
    updates: ToolProgressEvent[];
}
```

#### Actions

```typescript
{
    // Chat actions
    sendMessage(content: string, type?: InteractionType, metadata?: ActionMetadata): void;
    cancelRequest(): void;
    updateContext(updates: Record<string, any>): void;
    reset(): void;

    // Conversation actions
    newConversation(): Promise<number>;
    loadConversation(id: number): Promise<void>;
    deleteConversation(id: number): Promise<void>;
    refreshConversations(): Promise<void>;
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
            setStatusText(`Running ${event.tool}...`);
            setActiveToolProgress({ toolName: event.tool, updates: [] });
            break;

        case 'tool_progress':
            setActiveToolProgress(prev => ({
                ...prev,
                updates: [...prev.updates, event]
            }));
            break;

        case 'tool_complete':
            setActiveToolProgress(null);
            setStatusText(null);
            break;

        case 'complete':
            // Add message with workspace_payload
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: event.payload.message,
                workspace_payload: event.payload.workspace_payload,
                custom_payload: event.payload.custom_payload,
                // ...
            }]);
            break;
    }
}
```

### MainPage Layout

Location: `frontend/src/pages/MainPage.tsx`

Four-panel layout:

```
┌──────────┬─────────────────┬──────────────────┬─────────────┐
│          │                 │                  │             │
│ Sidebar  │   ChatPanel     │  WorkspacePanel  │ ContextPanel│
│          │                 │                  │             │
│ Convo    │ Messages        │ Payload View     │ Tools       │
│ List     │ Input           │ or Workflow      │ Assets      │
│          │ Progress        │ or Empty         │ Settings    │
│          │                 │                  │             │
└──────────┴─────────────────┴──────────────────┴─────────────┘
```

- **Sidebar**: Conversation history list (collapsible)
- **ChatPanel**: Chat messages, input, streaming text, tool progress
- **WorkspacePanel**: Renders based on `getWorkspaceMode()` discriminated union
- **ContextPanel**: Tool toggles, assets, settings (collapsible)

### ChatPanel Component

Location: `frontend/src/components/panels/ChatPanel.tsx`

Handles:
- Message display (user and assistant)
- Streaming text with typing indicator
- Tool progress cards during execution
- Input with send/cancel buttons
- Suggested values/actions

### WorkspacePanel Component

Location: `frontend/src/components/panels/WorkspacePanel.tsx`

Renders the appropriate view based on workspace mode:

```typescript
function WorkspacePanel({ payload, workflowInstance, ... }) {
    const mode = getWorkspaceMode({
        workflowInstance,
        workflowHandlers,
        isWorkflowProcessing,
        currentWorkflowEvent,
        selectedTool,
        selectedToolHistory,
        activePayload: payload
    });

    switch (mode.mode) {
        case 'empty':
            return <EmptyWorkspace />;
        case 'workflow':
            const WorkflowView = getWorkflowView(mode.instance.workflow.id);
            return <WorkflowView instance={mode.instance} handlers={mode.handlers} />;
        case 'payload':
            const PayloadView = getPayloadView(mode.payload.type);
            return <PayloadView payload={mode.payload} />;
        // ...
    }
}
```

---

## 7. Backend Implementation

### GeneralChatService

Location: `backend/services/general_chat_service.py`

```python
class GeneralChatService:
    """Service for primary agent chat interactions."""

    async def stream_chat_message(
        self,
        request,
        cancellation_token: Optional[CancellationToken] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream a chat message response with tool support via SSE.
        """
        # 1. Setup conversation (create/load, save user message)
        conversation_id = self._setup_conversation(request, user_prompt)

        # 2. Load message history
        messages = self._load_message_history(conversation_id)

        # 3. Get tools configuration
        tools_by_name, tool_descriptions, context = self._get_tools_config(...)

        # 4. Build system prompt
        system_prompt = self._build_system_prompt(tool_descriptions, ...)

        # 5. Run agent loop
        async for event in run_agent_loop(...):
            if isinstance(event, AgentTextDelta):
                yield TextDeltaEvent(text=event.text).model_dump_json()
            elif isinstance(event, AgentToolProgress):
                yield ToolProgressEvent(...).model_dump_json()
            # ... map all event types

        # 6. Extract workspace_payload from tool results
        workspace_payload = None
        for tool_call in reversed(tool_call_history):
            if tool_call.get("workspace_payload"):
                workspace_payload = tool_call["workspace_payload"]
                break

        # 7. Save assistant message
        self.conv_service.add_message(conversation_id, "assistant", collected_text, ...)

        # 8. Yield final CompleteEvent
        yield CompleteEvent(payload=ChatResponsePayload(
            message=collected_text,
            conversation_id=conversation_id,
            workspace_payload=workspace_payload,
            custom_payload={"type": "tool_history", "data": tool_call_history}
        )).model_dump_json()
```

### Agent Loop Integration

Location: `backend/services/agent_loop.py`

The agent loop handles multi-turn tool execution:

```python
async def run_agent_loop(
    client: AsyncAnthropic,
    model: str,
    max_tokens: int,
    max_iterations: int,
    system_prompt: str,
    messages: List[Dict],
    tools: Dict[str, ToolConfig],
    db: Session,
    user_id: int,
    context: Dict,
    cancellation_token: CancellationToken,
    stream_text: bool = True
) -> AsyncGenerator[AgentEvent, None]:
    """
    Run the agent loop with tool execution support.

    Yields:
        AgentThinking, AgentTextDelta, AgentToolStart,
        AgentToolProgress, AgentToolComplete, AgentComplete/AgentError
    """
```

### Conversation Persistence

Location: `backend/services/conversation_service.py`

- `create_conversation()` - Create new conversation
- `get_conversation(id)` - Load existing conversation
- `add_message(conversation_id, role, content, tool_calls)` - Save message
- `get_messages(conversation_id)` - Load message history
- `auto_title_if_needed(conversation_id)` - Generate title from first message

---

## 8. File Structure

```
backend/
├── schemas/
│   └── general_chat.py              # Domain types + Stream event types
├── services/
│   ├── agent_loop.py                # Generic agent loop (reusable)
│   ├── general_chat_service.py      # Chat service using agent loop
│   └── conversation_service.py      # Conversation persistence
├── tools/
│   ├── registry.py                  # ToolConfig, ToolResult, ToolProgress
│   ├── executor.py                  # Streaming tool execution
│   └── builtin/                     # Tool implementations
│       ├── __init__.py              # Auto-registers all tools
│       ├── research.py              # deep_research tool
│       ├── review_analyzer.py       # analyze_reviews tool
│       └── ...
└── routers/
    └── general_chat.py              # SSE endpoint

frontend/
├── lib/
│   ├── workspace/
│   │   ├── workspaceMode.ts         # Discriminated union for modes
│   │   ├── workspaceRegistry.tsx    # View registries
│   │   └── index.ts
│   └── api/
│       ├── generalChatApi.ts        # Stream event types + API client
│       └── conversationApi.ts       # Conversation CRUD
├── hooks/
│   └── useGeneralChat.ts            # Chat state management
├── components/panels/
│   ├── ChatPanel.tsx                # Chat UI
│   ├── WorkspacePanel.tsx           # Workspace container
│   └── workspace/                   # View components
│       ├── types.ts                 # PayloadTypeConfig
│       ├── StandardPayloadView.tsx  # Default view
│       ├── TablePayloadView.tsx
│       ├── ReviewAnalysisView.tsx
│       ├── ResearchResultView.tsx
│       └── ...
├── pages/
│   └── MainPage.tsx                 # Four-panel layout
└── types/
    └── chat.ts                      # Domain types + payload interfaces
```

---

## Appendix: Comparison with Old Architecture

| Aspect | Old (Page-Aware ChatTray) | Current (Workspace-Centric) |
|--------|---------------------------|----------------------------|
| **Primary UI** | ChatTray component per page | MainPage with WorkspacePanel |
| **Payload Handling** | Page-specific PayloadHandlers | Global View Registry |
| **Tool System** | Basic executor → string/ToolResult | Streaming generators with ToolProgress |
| **State Management** | Local to ChatTray | useGeneralChat hook + persistence |
| **Extensibility** | Requires page code changes | Registry-based (add view + register) |
| **Context Building** | Per-page context builders | Global context from frontend |
| **Tool Registration** | Page-registered tools | Global tool registry |

See `_specs/chat_system_evolution.md` for detailed migration notes.
