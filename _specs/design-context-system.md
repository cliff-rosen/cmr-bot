# Design: Context Enhancement System

## Overview

This system enhances the AI agent's context with three types of information:
1. **Working Memory** - Short-term facts from the current session
2. **Long-term Memory** - Persistent facts, preferences, and knowledge about the user
3. **Assets** - Files, documents, and data actively in use
4. **Cross-conversation Highlights** - Relevant context from other conversations

The user has explicit control over what context is included via the Context Panel UI.

---

## Database Schema

### Memories Table

```sql
CREATE TABLE memories (
    memory_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,

    -- Classification
    memory_type ENUM('working', 'fact', 'preference', 'entity', 'project') NOT NULL,
    category VARCHAR(100),              -- e.g., "work", "personal", "health"

    -- Content
    content TEXT NOT NULL,              -- The actual memory
    source_conversation_id INT,         -- Where this memory came from
    source_message_id INT,

    -- Temporal
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NULL,          -- For working memory auto-cleanup
    last_accessed_at TIMESTAMP,
    access_count INT DEFAULT 0,

    -- Control
    is_active BOOLEAN DEFAULT TRUE,     -- Include in context
    is_pinned BOOLEAN DEFAULT FALSE,    -- Always include (for facts/preferences)
    confidence FLOAT DEFAULT 1.0,       -- For auto-extracted memories

    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (source_conversation_id) REFERENCES conversations(conversation_id) ON DELETE SET NULL
);
```

### Assets Table

```sql
CREATE TABLE assets (
    asset_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,

    -- Identity
    name VARCHAR(255) NOT NULL,
    asset_type ENUM('file', 'document', 'data', 'code', 'link') NOT NULL,
    mime_type VARCHAR(100),

    -- Content (choose one based on size)
    content TEXT,                       -- For small text content
    file_path VARCHAR(500),             -- For file storage reference
    external_url VARCHAR(500),          -- For links

    -- Metadata
    description TEXT,
    tags JSON,                          -- Array of tags for filtering
    metadata JSON,                      -- Flexible extra data

    -- Context control
    is_in_context BOOLEAN DEFAULT FALSE, -- Currently active in context
    context_summary TEXT,               -- Compressed version for context

    -- Source tracking
    source_conversation_id INT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (source_conversation_id) REFERENCES conversations(conversation_id) ON DELETE SET NULL
);
```

### Conversation Highlights Table (for cross-conversation context)

```sql
CREATE TABLE conversation_highlights (
    highlight_id INT PRIMARY KEY AUTO_INCREMENT,
    conversation_id INT NOT NULL,
    user_id INT NOT NULL,

    -- Content
    summary TEXT NOT NULL,              -- Key point or decision
    highlight_type ENUM('decision', 'insight', 'action', 'reference') NOT NULL,

    -- Relevance
    topics JSON,                        -- Array of topic tags

    -- Control
    is_active BOOLEAN DEFAULT TRUE,     -- Include when browsing

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
```

---

## Memory Types

### Working Memory (session-scoped)
- Created during conversation
- Auto-expires after session or 24 hours
- Examples: "User is working on the login page", "Current task is fixing bug #123"

### Facts
- Persistent knowledge about user
- Manually created or extracted
- Examples: "User works at Acme Corp", "User's timezone is EST"

### Preferences
- User preferences and style
- Examples: "Prefers TypeScript over JavaScript", "Likes concise responses"

### Entities
- People, projects, systems the user references
- Examples: "Project Alpha is the main product", "Sarah is the tech lead"

### Projects
- Active projects with context
- Examples: "CMR-Bot is a personal AI agent system"

---

## Context Assembly

When building the system prompt, context is assembled in priority order:

```python
def build_context(user_id: int, conversation_id: int) -> str:
    context_parts = []

    # 1. Pinned memories (always included)
    pinned = memory_service.get_pinned_memories(user_id)
    if pinned:
        context_parts.append("## About the User\n" + format_memories(pinned))

    # 2. Working memory (current session)
    working = memory_service.get_working_memories(user_id)
    if working:
        context_parts.append("## Current Session Context\n" + format_memories(working))

    # 3. Active assets
    assets = asset_service.get_active_assets(user_id)
    if assets:
        context_parts.append("## Active Assets\n" + format_assets(assets))

    # 4. Relevant highlights from other conversations (if enabled)
    if user_wants_cross_conv_context:
        highlights = get_relevant_highlights(user_id, conversation_id)
        if highlights:
            context_parts.append("## From Previous Conversations\n" + format_highlights(highlights))

    return "\n\n".join(context_parts)
```

---

## API Endpoints

### Memories

```
GET    /api/memories                    - List memories (filterable by type, category)
POST   /api/memories                    - Create memory manually
PUT    /api/memories/:id                - Update memory
DELETE /api/memories/:id                - Delete memory
POST   /api/memories/:id/toggle         - Toggle is_active
POST   /api/memories/:id/pin            - Toggle is_pinned
POST   /api/memories/extract            - Extract memories from conversation (LLM-powered)
```

### Assets

```
GET    /api/assets                      - List assets
POST   /api/assets                      - Create/upload asset
GET    /api/assets/:id                  - Get asset details
PUT    /api/assets/:id                  - Update asset
DELETE /api/assets/:id                  - Delete asset
POST   /api/assets/:id/context          - Toggle asset in context
```

### Conversation Highlights

```
GET    /api/conversations/:id/highlights - Get highlights for conversation
POST   /api/conversations/:id/highlights - Add highlight
DELETE /api/highlights/:id               - Remove highlight
GET    /api/highlights/relevant          - Get relevant highlights for current context
```

---

## Context Panel UI

### Layout

```
┌─────────────────────────────────────┐
│ Context                       [⚙️]  │
├─────────────────────────────────────┤
│ ▼ AVAILABLE TOOLS                   │
│   ● web_search                      │
│   ● fetch_webpage                   │
├─────────────────────────────────────┤
│ ▼ WORKING MEMORY                    │
│   ☑ Working on login page           │
│   ☑ Bug #123 needs fixing      [x]  │
│   [+ Add note]                      │
├─────────────────────────────────────┤
│ ▼ ACTIVE ASSETS                     │
│   📄 requirements.txt          [x]  │
│   📄 design-doc.md             [x]  │
│   [+ Add asset]                     │
├─────────────────────────────────────┤
│ ▼ USER PROFILE                      │
│   📌 Works at Acme Corp             │
│   📌 Prefers TypeScript             │
│   [Manage memories...]              │
├─────────────────────────────────────┤
│ ▼ CROSS-CONVERSATION [toggle]       │
│   From "API Design Discussion":     │
│   • Decided on REST over GraphQL    │
│   [Browse conversations...]         │
└─────────────────────────────────────┘
```

### Interactions

- **Checkboxes** - Toggle items in/out of active context
- **Pin icon** - Mark as always-included
- **X button** - Remove from context (or delete working memory)
- **Add buttons** - Quick-add new items
- **Section collapse** - Expand/collapse sections
- **Cross-conversation toggle** - Global on/off for including other conversation context

---

## Implementation Order

### Phase 1: Working Memory
1. Create memories table and model
2. Create MemoryService with basic CRUD
3. Add working memory UI to context panel
4. Inject working memory into system prompt

### Phase 2: Persistent Memory
1. Add memory type differentiation
2. Add pinning functionality
3. Add memory management UI
4. Add LLM-powered memory extraction

### Phase 3: Assets
1. Create assets table and model
2. Create AssetService
3. Add asset upload/management UI
4. Add asset context injection

### Phase 4: Cross-conversation Highlights
1. Create highlights table
2. Add highlight extraction (manual + LLM)
3. Add relevance matching
4. Add cross-conversation UI

---

## Open Questions

1. **Memory extraction trigger** - Manual button? After each conversation? Background job?
2. **Asset storage** - Store in DB, local filesystem, or cloud storage?
3. **Highlight relevance** - Keyword matching, embedding similarity, or topic overlap?
4. **Context token budget** - How much context to include before truncating?
5. **Working memory cleanup** - Session-based, time-based, or manual?
