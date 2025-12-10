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