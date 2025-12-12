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
}

export type WorkspacePayloadType = 'draft' | 'summary' | 'data' | 'code' | 'plan' | 'wip' | 'final';

export interface WorkspacePayload {
    type: WorkspacePayloadType;
    title: string;
    content: string;
    // Extended fields for plan payloads
    goal?: string;
    initial_input?: string;
    steps?: WorkflowStepDefinition[];
    // Extended fields for wip payloads
    step_number?: number;
    content_type?: 'document' | 'data' | 'code';
    data?: any;  // Structured data when content_type is 'data'
    // Extended fields for final workflow output
    workflow_title?: string;
    steps_completed?: number;
}

// ============================================================================
// Workflow Types
// ============================================================================

export interface WorkflowPlan {
    id: string;
    title: string;
    goal: string;
    initial_input: string;
    status: 'proposed' | 'active' | 'completed' | 'abandoned';
    steps: WorkflowStep[];
    created_at: string;
}

export interface WorkflowStep {
    step_number: number;
    description: string;
    input_description: string;
    input_sources: ('user' | number)[];   // Array of sources: 'user' and/or step numbers
    output_description: string;
    method: StepMethod;
    status: 'pending' | 'in_progress' | 'completed' | 'skipped';
    wip_output?: WipOutput;
}

export interface WorkflowStepDefinition {
    description: string;
    input_description: string;
    input_sources: ('user' | number)[];   // Array of sources
    output_description: string;
    method: StepMethod;
}

export interface StepMethod {
    approach: string;
    tools: string[];
    reasoning: string;
}

export interface WipOutput {
    title: string;
    content: string;
    content_type: 'document' | 'data' | 'code';
    data?: any;  // Structured data when content_type is 'data'
}

const VALID_PAYLOAD_TYPES = ['draft', 'summary', 'data', 'code', 'plan', 'wip'];

/**
 * Parse a workspace payload from message content.
 * Looks for ```payload JSON ``` blocks in the message.
 * Returns the payload and the message content without the payload block.
 */
export function parseWorkspacePayload(content: string): { text: string; payload: WorkspacePayload | null } {
    // Try multiple patterns - LLM might format differently
    const patterns = [
        /```payload\s*\n([\s\S]*?)\n```/,      // ```payload\n...\n```
        /```payload\s+([\s\S]*?)```/,           // ```payload {...}```
        /```json\s*\n(\{[\s\S]*?"type"\s*:\s*"(?:draft|summary|data|code|plan|wip)"[\s\S]*?\})\n```/, // ```json with type field
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
            if (payload.type === 'plan') {
                // Plan requires goal and steps
                if (!payload.title || !payload.goal || !payload.steps) {
                    continue;
                }
            } else if (payload.type === 'wip') {
                // WIP requires step_number and content
                if (!payload.title || !payload.content || payload.step_number === undefined) {
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