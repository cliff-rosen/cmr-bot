# TABILIZER: AI-Computed Table Columns

## Overview

TABILIZER is a feature that displays tool results (like PubMed searches) as interactive tables, and allows users to add AI-computed columns by running a prompt against each row. For example, a user can search PubMed for articles, then add a "Relevant?" column that uses an LLM to classify each article based on title and abstract.

## Core Concept

1. **Tool returns table data** - Search tools return structured table data with columns and rows
2. **Interactive table display** - Results render as sortable/filterable tables
3. **Add computed column** - User defines a new column with a prompt template
4. **Real-time computation** - LLM processes each row, values appear in real-time via streaming

---

## Data Structures

### Table Payload (returned by tools)

```typescript
interface TablePayload {
    type: 'table';
    title: string;                    // e.g., "PubMed: asbestos litigation"
    content?: string;                 // Summary text, e.g., "Found 150 results, showing 10"
    table_data: {
        columns: TableColumn[];
        rows: Record<string, any>[];  // Array of row objects
        source?: string;              // e.g., "pubmed_search"
    };
}

interface TableColumn {
    key: string;                      // Field name in row objects
    label: string;                    // Display name
    type: 'text' | 'number' | 'boolean' | 'date' | 'link';
    sortable?: boolean;               // Default: true
    filterable?: boolean;             // Default: true
    computed?: boolean;               // True if AI-generated
    width?: string;                   // e.g., "100px", "20%"
}
```

### Example PubMed Table Payload

```json
{
    "type": "table",
    "title": "PubMed: mesothelioma treatment",
    "content": "Found 1,234 total results, showing 10",
    "table_data": {
        "columns": [
            {"key": "pmid", "label": "PMID", "type": "text", "width": "80px"},
            {"key": "title", "label": "Title", "type": "text"},
            {"key": "authors_display", "label": "Authors", "type": "text"},
            {"key": "journal", "label": "Journal", "type": "text", "filterable": true},
            {"key": "publication_date", "label": "Date", "type": "text", "width": "100px"},
            {"key": "url", "label": "Link", "type": "link", "width": "60px"}
        ],
        "rows": [
            {
                "pmid": "12345678",
                "title": "Novel treatment approaches for malignant mesothelioma",
                "authors_display": "Smith J, Jones M et al.",
                "journal": "J Thorac Oncol",
                "publication_date": "2024",
                "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
                "abstract": "Background: Mesothelioma remains a challenging..."
            }
        ],
        "source": "pubmed_search"
    }
}
```

### Column Configuration (user input)

```typescript
interface ColumnConfig {
    name: string;                     // Display name, e.g., "Relevant"
    key: string;                      // Generated from name, e.g., "relevant"
    type: 'text' | 'boolean' | 'number';
    prompt: string;                   // Template with {field} placeholders
}
```

---

## Frontend Components

### 1. TablePayloadView

Main component that renders the table with sorting, filtering, and the Add Column button.

**State:**
- `columns: TableColumn[]` - Mutable, starts from payload
- `rows: Record<string, any>[]` - Mutable, updated as values computed
- `sort: { column: string | null, direction: 'asc' | 'desc' | null }`
- `filters: Record<string, string>`
- `isComputing: boolean`
- `computingColumnKey: string | null` - Which column is being computed
- `computeProgress: { completed: number, total: number, status: string } | null`

**Features:**
- Sortable columns (click header to cycle: asc → desc → none)
- Filterable columns (text input or dropdown for boolean)
- Column type rendering (boolean shows Yes/No, link shows clickable link, etc.)
- Computed columns marked with indicator (e.g., asterisk or sparkle icon)
- "+ Column" button opens AddColumnModal
- Progress banner during computation
- Loading indicator (pulsing dot) in cells being computed

### 2. AddColumnModal

Modal for configuring a new computed column.

**Fields:**
- Column Name (text input)
- Column Type (radio: Text, Yes/No, Number)
- Prompt (textarea with {field} placeholder support)

**Features:**
- "Insert Article" button - inserts pre-built template:
  ```
  Title: {title}
  Authors: {authors_display}
  Journal: {journal}
  Date: {publication_date}
  Abstract: {abstract}
  ```
- Field chips - clickable buttons to insert individual `{field}` placeholders
- Type-specific hints (e.g., "Answer with only Yes or No")

**Recommended Size:** Large modal (e.g., 80vh height, max-w-4xl) with fixed dimensions to prevent jumping.

---

## Backend Endpoint

### POST `/api/table/compute-column`

Computes values for a new column using an LLM.

**Request:**
```typescript
interface ComputeColumnRequest {
    rows: Record<string, any>[];      // All rows from the table
    prompt: string;                   // Prompt template with {field} placeholders
    column_key: string;               // Key for the new column
    column_type: 'text' | 'boolean' | 'number';
}
```

**Response:** Server-Sent Events (SSE) stream

### SSE Event Types

```typescript
// Progress update
{ "type": "progress", "completed": 5, "total": 10, "message": "Processing 5/10..." }

// Single row result
{ "type": "row_result", "row_index": 3, "value": true }

// Completion
{ "type": "complete", "message": "Computed 10 values" }

// Error
{ "type": "error", "message": "API rate limit exceeded" }
```

### Backend Implementation Notes

1. **Prompt substitution:** Replace `{field}` placeholders with actual row values
2. **Type-specific system prompts:**
   - Boolean: "You must respond with ONLY 'Yes' or 'No'. No other text."
   - Number: "You must respond with ONLY a number. No other text or units."
   - Text: "Respond concisely with the requested information."
3. **Parallel processing:** Process rows in batches (e.g., 5 at a time) for speed
4. **Value parsing:**
   - Boolean: Check if response contains "yes"/"true"/"1" (case-insensitive)
   - Number: Extract first number from response using regex
   - Text: Use response as-is (trimmed)

### Example Backend (Python/FastAPI)

```python
@router.post("/compute-column")
async def compute_column(request: ComputeColumnRequest):
    async def generate():
        total = len(request.rows)

        yield f"data: {json.dumps({'type': 'progress', 'completed': 0, 'total': total})}\n\n"

        for batch_start in range(0, total, 5):
            batch = request.rows[batch_start:batch_start+5]
            tasks = [compute_single(row, i + batch_start) for i, row in enumerate(batch)]
            results = await asyncio.gather(*tasks)

            for result in results:
                yield f"data: {json.dumps({'type': 'row_result', ...})}\n\n"
                yield f"data: {json.dumps({'type': 'progress', ...})}\n\n"

        yield f"data: {json.dumps({'type': 'complete'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

---

## Frontend SSE Handling

```typescript
const handleAddColumn = async (config: ColumnConfig) => {
    // 1. Add column immediately (appears with empty cells)
    setColumns(prev => [...prev, {
        key: config.key,
        label: config.name,
        type: config.type,
        computed: true
    }]);

    setIsComputing(true);
    setComputingColumnKey(config.key);

    // 2. Call API
    const response = await fetch('/api/table/compute-column', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rows, prompt: config.prompt, ... })
    });

    // 3. Process SSE stream
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const data = JSON.parse(line.slice(6));

                if (data.type === 'progress') {
                    setComputeProgress({ completed: data.completed, total: data.total });
                } else if (data.type === 'row_result') {
                    // Update specific row immediately
                    setRows(prev => prev.map((row, idx) =>
                        idx === data.row_index
                            ? { ...row, [config.key]: data.value }
                            : row
                    ));
                }
            }
        }
    }

    setIsComputing(false);
    setComputingColumnKey(null);
};
```

---

## UX Details

### During Computation

1. **Banner at top of table:** "Computing column values... X of Y complete" with progress bar
2. **Pulsing indicator in empty cells:** Shows which cells are pending
3. **Values appear in real-time:** As each `row_result` arrives, that cell updates
4. **Non-blocking:** User can see the table and watch values materialize

### Cell Rendering by Type

| Type | Null/Empty | Value |
|------|------------|-------|
| text | Gray dash (-) | Text as-is |
| boolean | Gray dash (-) | Green "Yes" / Red "No" |
| number | Gray dash (-) | Formatted number |
| date | Gray dash (-) | Formatted date |
| link | Gray dash (-) | Clickable "Link" text |

### Computed Column Indicator

Mark computed columns in the header with a visual indicator (asterisk, sparkle icon, or different color) so users know which columns were AI-generated.

---

## Integration Checklist

### Backend
- [ ] Create `/api/table/compute-column` endpoint
- [ ] Implement SSE streaming
- [ ] Add LLM integration for prompt evaluation
- [ ] Handle parallel batch processing
- [ ] Add authentication (if needed)

### Frontend
- [ ] Create TablePayloadView component
- [ ] Implement sorting logic
- [ ] Implement filtering logic
- [ ] Create AddColumnModal component
- [ ] Implement "Insert Article" template button
- [ ] Handle SSE streaming and real-time updates
- [ ] Add progress indicators
- [ ] Add loading state for computing cells

### Tool Integration
- [ ] Modify PubMed tool to return table payload format
- [ ] Include all fields needed for prompts (especially abstract)
- [ ] Test with various result sizes

---

## Example User Flow

1. User: "Search PubMed for mesothelioma treatment articles from 2024"
2. Agent runs PubMed search, returns table payload
3. Table displays with 10 articles (title, authors, journal, date, link)
4. User clicks "+ Column" button
5. User enters:
   - Name: "Relevant"
   - Type: Yes/No
   - Clicks "Insert Article" then adds: "Is this article relevant to asbestos litigation lawsuits? Answer Yes or No."
6. User clicks "Compute Column"
7. "Relevant" column appears, cells show pulsing dots
8. Banner shows "Computing... 3 of 10 complete"
9. Values appear one by one: "Yes", "No", "Yes"...
10. User can now sort/filter by the Relevant column
