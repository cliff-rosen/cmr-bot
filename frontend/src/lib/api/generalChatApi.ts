import { makeStreamRequest } from './streamUtils';
import { InteractionType, ActionMetadata, SuggestedValue, SuggestedAction, CustomPayload, WorkspacePayload } from '../../types/chat';

// ============================================================================
// General Chat API Request/Response Types
// ============================================================================

export interface GeneralChatRequest {
    message: string;
    conversation_id?: number;  // If provided, continues existing conversation
    context?: Record<string, any>;
    interaction_type?: InteractionType;
    action_metadata?: ActionMetadata;
    enabled_tools?: string[];  // List of tool IDs to enable (undefined = all tools)
    include_profile?: boolean;  // Whether to include user profile in context
}

export interface ChatResponsePayload {
    message: string;
    conversation_id?: number;  // The conversation this message belongs to
    suggested_values?: SuggestedValue[];
    suggested_actions?: SuggestedAction[];
    custom_payload?: CustomPayload;
    workspace_payload?: WorkspacePayload;  // Direct workspace payload from tools (takes precedence over parsed message payloads)
}


// ============================================================================
// Stream Event Types (discriminated union with explicit 'type' field)
// ============================================================================

/** Streaming text token */
export interface TextDeltaEvent {
    type: 'text_delta';
    text: string;
}

/** Status message (thinking, processing, etc.) */
export interface StatusEvent {
    type: 'status';
    message: string;
}

/** Tool execution begins */
export interface ToolStartEvent {
    type: 'tool_start';
    tool: string;
    input: any;
    tool_use_id: string;
}

/** Tool execution progress update */
export interface ToolProgressEvent {
    type: 'tool_progress';
    tool: string;
    stage: string;
    message: string;
    progress: number;  // 0.0 to 1.0
    data?: any;
}

/** Tool execution finished */
export interface ToolCompleteEvent {
    type: 'tool_complete';
    tool: string;
    index: number;  // Index into tool_history
}

/** Final response with payload */
export interface CompleteEvent {
    type: 'complete';
    payload: ChatResponsePayload;
}

/** Error occurred */
export interface ErrorEvent {
    type: 'error';
    message: string;
}

/** Request was cancelled */
export interface CancelledEvent {
    type: 'cancelled';
}

/** Discriminated union of all stream event types */
export type StreamEvent =
    | TextDeltaEvent
    | StatusEvent
    | ToolStartEvent
    | ToolProgressEvent
    | ToolCompleteEvent
    | CompleteEvent
    | ErrorEvent
    | CancelledEvent;

export const generalChatApi = {
    /**
     * Stream chat messages from the backend
     * @param request - Chat request with message, context, and interaction type
     * @param signal - Optional AbortSignal for cancellation
     * @returns AsyncGenerator that yields stream events
     */
    async* streamMessage(
        request: GeneralChatRequest,
        signal?: AbortSignal
    ): AsyncGenerator<StreamEvent> {
        try {
            const rawStream = makeStreamRequest('/api/chat/stream', request, 'POST', signal);

            // Buffer for accumulating partial SSE data lines across chunks
            let buffer = '';

            for await (const update of rawStream) {
                // Append new data to buffer
                buffer += update.data;

                // Process complete lines from the buffer
                // SSE messages end with \n\n, but we process line by line
                // looking for complete "data: {...}" lines
                let newlineIndex: number;
                while ((newlineIndex = buffer.indexOf('\n')) !== -1) {
                    const line = buffer.slice(0, newlineIndex);
                    buffer = buffer.slice(newlineIndex + 1);

                    // Skip empty lines and non-data lines (event:, id:, retry:, comments)
                    if (!line.trim() || !line.startsWith('data: ')) {
                        continue;
                    }

                    const jsonStr = line.slice(6); // Remove "data: " prefix

                    // Skip ping/keepalive messages
                    if (jsonStr === '' || jsonStr === 'ping') {
                        continue;
                    }

                    try {
                        const data = JSON.parse(jsonStr) as StreamEvent;
                        // Log non-text events for debugging
                        if (data.type !== 'text_delta') {
                            console.log('[SSE] Event:', data.type);
                        }
                        yield data;
                    } catch (e) {
                        // JSON parse failed - this line might be incomplete
                        // Put it back in the buffer and wait for more data
                        buffer = line + '\n' + buffer;
                        break;
                    }
                }
            }

            // Process any remaining buffered data
            if (buffer.trim() && buffer.startsWith('data: ')) {
                const jsonStr = buffer.slice(6);
                try {
                    const data = JSON.parse(jsonStr) as StreamEvent;
                    if (data.type !== 'text_delta') {
                        console.log('[SSE] Event (final):', data.type);
                    }
                    yield data;
                } catch (e) {
                    console.error('Failed to parse final stream data:', jsonStr.slice(0, 200) + '...', e);
                }
            }
        } catch (error) {
            // Re-throw AbortError so callers can detect cancellation
            if (error instanceof Error && error.name === 'AbortError') {
                throw error;
            }
            yield {
                type: 'error',
                message: `Stream error: ${error instanceof Error ? error.message : String(error)}`
            };
        }
    }
};
