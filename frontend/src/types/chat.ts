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

export type WorkspacePayloadType = 'draft' | 'summary' | 'data' | 'code' | 'plan';

export interface WorkspacePayload {
    type: WorkspacePayloadType;
    title: string;
    content: string;
}

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
        /```json\s*\n(\{[\s\S]*?"type"\s*:\s*"(?:draft|summary|data|code|plan)"[\s\S]*?\})\n```/, // ```json with type field
    ];

    for (const regex of patterns) {
        const match = content.match(regex);
        if (!match) continue;

        try {
            const payloadJson = match[1].trim();
            const payload = JSON.parse(payloadJson) as WorkspacePayload;

            // Validate required fields
            if (!payload.type || !payload.title || !payload.content) {
                continue;
            }

            // Validate type is one of our known types
            if (!['draft', 'summary', 'data', 'code', 'plan'].includes(payload.type)) {
                continue;
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