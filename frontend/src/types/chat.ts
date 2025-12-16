// ============================================================================
// General Purpose Chat System Types
// ============================================================================

export enum InteractionType {
    TEXT_INPUT = 'text_input',
    VALUE_SELECTED = 'value_selected',
    ACTION_EXECUTED = 'action_executed'
}

export interface GeneralChatMessage {
    role: 'user' | 'assistant';
    content: string;
    timestamp: string;
    suggested_values?: SuggestedValue[];
    suggested_actions?: SuggestedAction[];
    custom_payload?: CustomPayload;
    workspace_payload?: WorkspacePayload;  // Direct workspace payload from tools (takes precedence over parsed message payloads)
}

export interface SuggestedValue {
    label: string;
    value: string;
}

export interface SuggestedAction {
    label: string;
    action: string;
    handler: 'client' | 'server';
    data?: any;
    style?: 'primary' | 'secondary' | 'warning';
}

export interface CustomPayload {
    type: string;
    data: any;
}

export interface ToolCall {
    tool_name: string;
    input: Record<string, any>;
    output: string | Record<string, any>;
    workspace_payload?: WorkspacePayload;  // Payload to display in workspace panel
}

export type WorkspacePayloadType = 'draft' | 'summary' | 'data' | 'code' | 'agent_create' | 'agent_update' | 'table' | 'research' | 'research_result' | 'workflow_graph';

// Table payload types for TABILIZER functionality
export interface TableColumn {
    key: string;
    label: string;
    type: 'text' | 'number' | 'boolean' | 'date' | 'link';
    sortable?: boolean;
    filterable?: boolean;
    computed?: boolean;  // Was this column added by LLM?
    width?: string;      // Optional column width (e.g., '200px', '20%')
}

export interface TablePayloadData {
    columns: TableColumn[];
    rows: Record<string, any>[];
    source?: string;     // Origin tool: "pubmed_search", "web_search", etc.
}

export interface AgentPayloadData {
    agent_id?: number;  // Only for updates
    name: string;
    description?: string;
    instructions: string;
    lifecycle: 'one_shot' | 'scheduled' | 'monitor';
    tools?: string[];
    schedule?: string;
    monitor_interval_minutes?: number;
}

// Research result payload types (from deep_research tool)
export interface ResearchChecklistItem {
    question: string;
    status: 'unfilled' | 'partial' | 'complete';
    findings: string[];
    sources: string[];
}

export interface ResearchResultData {
    topic: string;
    goal: string;
    synthesis: string;
    checklist: ResearchChecklistItem[];
    checklist_summary: { unfilled: number; partial: number; complete: number };
    sources: string[];
    iterations: number;
    queries_used: string[];
}

// Workflow Graph types (from design_workflow tool)
export type StepType = 'tool_call' | 'llm_transform' | 'llm_decision';

export interface WorkflowStepDefinition {
    id: string;
    name: string;
    description: string;
    step_type: StepType;
    output_field: string;

    // For tool_call
    tool?: string;
    input_mapping?: Record<string, string>;

    // For llm_transform and llm_decision
    goal?: string;
    input_fields?: string[];

    // For llm_transform
    output_schema?: Record<string, any>;

    // For llm_decision
    choices?: string[];
}

export interface WorkflowCheckpointConfig {
    title: string;
    description: string;
    allowed_actions: string[];
    editable_fields: string[];
    auto_proceed?: boolean;
    auto_proceed_timeout_seconds?: number;
}

export interface WorkflowNode {
    id: string;
    name: string;
    description: string;
    node_type: 'execute' | 'checkpoint';
    step_definition?: WorkflowStepDefinition;
    checkpoint_config?: WorkflowCheckpointConfig;
    ui_component?: string;
}

export interface WorkflowEdge {
    from_node: string;
    to_node: string;
    label?: string;
    condition_expr?: string;
}

export interface WorkflowGraphData {
    id: string;
    name: string;
    description: string;
    nodes: Record<string, WorkflowNode>;
    edges: WorkflowEdge[];
    entry_node: string;
    icon?: string;
    category?: string;
    input_schema?: Record<string, any>;
    output_schema?: Record<string, any>;
}

export interface WorkspacePayload {
    type: WorkspacePayloadType;
    title: string;
    content: string;
    // Extended fields for data payloads
    data?: any;  // Structured data when type is 'data'
    // Extended fields for agent payloads
    agent_data?: AgentPayloadData;
    // Extended fields for table payloads (TABILIZER)
    table_data?: TablePayloadData;
    // Extended fields for research workflow
    research_data?: ResearchWorkflow;
    // Extended fields for research result (from deep_research tool)
    research_result_data?: ResearchResultData;
    // Extended fields for workflow graph (from design_workflow tool)
    workflow_graph_data?: WorkflowGraphData;
}

// ============================================================================
// Research Workflow Types
// ============================================================================

export type ResearchWorkflowStage = 'question' | 'checklist' | 'retrieval' | 'compiling' | 'complete';

export interface ResearchWorkflow {
    id: string;
    stage: ResearchWorkflowStage;
    original_query: string;
    created_at: string;

    // Stage 1: Formulated Question
    question?: ResearchQuestion;

    // Stage 2: Answer Checklist
    checklist?: AnswerChecklist;

    // Stage 3: Retrieval Loop State
    retrieval?: RetrievalState;

    // Stage 4: Final Answer
    final?: ResearchFinal;
}

export interface ResearchQuestion {
    original: string;           // What user asked
    refined: string;            // AI-refined research question
    scope: string;              // Clarified scope/boundaries
    key_terms: string[];        // Important terms/concepts
    constraints?: string[];     // Any constraints mentioned
    approved: boolean;          // User approved this formulation
}

export interface AnswerChecklist {
    items: ChecklistItem[];
    approved: boolean;          // User approved this checklist
}

export interface ChecklistItem {
    id: string;
    description: string;        // What this part of the answer needs
    rationale: string;          // Why this is needed for a complete answer
    status: 'pending' | 'partial' | 'complete';
    findings: Finding[];        // Relevant findings for this item
    priority: 'high' | 'medium' | 'low';
}

export interface Finding {
    id: string;
    checklist_item_id: string;  // Which checklist item this supports
    source: string;             // Where this came from (e.g., "PubMed: PMID123")
    source_url?: string;        // Link to source
    title: string;              // Title/summary of finding
    content: string;            // The relevant information
    relevance: string;          // Why it's relevant to the checklist item
    confidence: 'high' | 'medium' | 'low';
    added_at: string;
}

export interface RetrievalState {
    iteration: number;
    max_iterations: number;
    iterations: RetrievalIteration[];
    current_focus: string[];    // Which checklist item IDs we're working on
    status: 'searching' | 'reviewing' | 'updating' | 'paused' | 'complete';
}

export interface RetrievalIteration {
    iteration_number: number;
    focus_items: string[];      // Checklist items targeted this iteration
    queries: SearchQuery[];
    results_reviewed: number;
    findings_added: number;
    notes?: string;             // AI's notes about this iteration
    completed_at: string;
}

export interface SearchQuery {
    id: string;
    query: string;
    source: 'pubmed' | 'pubmed_smart' | 'web' | 'semantic_scholar';
    rationale: string;          // Why this query
    results_count: number;
    useful_results: number;
    executed_at: string;
}

export interface ResearchFinal {
    answer: string;             // The compiled answer (markdown)
    summary: string;            // Brief summary
    confidence: 'high' | 'medium' | 'low';
    confidence_explanation: string;
    limitations: string[];      // Known gaps or limitations
    sources: ResearchSource[];  // All sources used
    approved: boolean;
}

export interface ResearchSource {
    id: string;
    title: string;
    url?: string;
    citation?: string;
    contribution: string;       // How this source contributed
}

const VALID_PAYLOAD_TYPES = ['draft', 'summary', 'data', 'code', 'agent_create', 'agent_update', 'table', 'research', 'research_result', 'workflow_graph'];

/**
 * Parse a workspace payload from message content.
 * Looks for ```payload JSON ``` blocks in the message.
 * Returns the payload and the message content without the payload block.
 */
export function parseWorkspacePayload(content: string): { text: string; payload: WorkspacePayload | null } {
    // Try multiple patterns - LLM might format differently
    const patterns = [
        /```payload\s*\n?([\s\S]*?)```/,        // ```payload ... ``` (most permissive)
        /```json\s*\n(\{[\s\S]*?"type"\s*:\s*"(?:draft|summary|data|code|agent_create|agent_update|workflow_graph|table|research|research_result)"[\s\S]*?\})\s*```/, // ```json with type field
    ];

    for (const regex of patterns) {
        const match = content.match(regex);
        if (!match) continue;

        try {
            const payloadJson = match[1].trim();
            const payload = JSON.parse(payloadJson) as WorkspacePayload;

            // Validate type is one of our known types
            if (!payload.type || !VALID_PAYLOAD_TYPES.includes(payload.type)) {
                continue;
            }

            // Validate required fields based on type
            if (payload.type === 'agent_create' || payload.type === 'agent_update') {
                // Agent payloads require agent_data with name and instructions
                if (!payload.title || !payload.agent_data?.name || !payload.agent_data?.instructions) {
                    continue;
                }
                // agent_update also requires agent_id
                if (payload.type === 'agent_update' && !payload.agent_data?.agent_id) {
                    continue;
                }
            } else if (payload.type === 'workflow_graph') {
                // Workflow graph payloads require title and workflow_graph_data
                if (!payload.title || !payload.workflow_graph_data) {
                    continue;
                }
            } else {
                // Standard payloads require title and content
                if (!payload.title || !payload.content) {
                    continue;
                }
            }

            // Remove the payload block from the text
            const text = content.replace(match[0], '').trim();

            return { text, payload };
        } catch {
            // Invalid JSON, try next pattern
            continue;
        }
    }

    return { text: content, payload: null };
}

export interface ActionMetadata {
    action_identifier: string;
    action_data?: any;
}

// PayloadHandler interface for ChatTray
export interface PayloadHandler {
    render: (payload: any, callbacks: { onAccept?: (data: any) => void; onReject?: () => void }) => React.ReactNode;
    onAccept?: (payload: any, pageState?: any) => void;
    onReject?: (payload: any) => void;
    renderOptions?: {
        panelWidth?: string;
        headerTitle?: string;
        headerIcon?: string;
    };
}