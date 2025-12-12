import { makeStreamRequest } from './streamUtils';
import { InteractionType, ActionMetadata, SuggestedValue, SuggestedAction, CustomPayload } from '../../types/chat';

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
}

export interface ToolProgressPayload {
    tool: string;
    phase: 'started' | 'progress' | 'completed';
    stage?: string;
    data?: Record<string, any>;
    progress?: number;
}

export interface ChatStreamChunk {
    token?: string | null;
    response_text?: string | null;
    payload?: ChatResponsePayload | ToolProgressPayload | null;
    status?: string | null;
    error?: string | null;
    debug?: any;
}

export const generalChatApi = {
    /**
     * Stream chat messages from the backend
     * @param request - Chat request with message, context, and interaction type
     * @param signal - Optional AbortSignal for cancellation
     * @returns AsyncGenerator that yields stream chunks
     */
    async* streamMessage(
        request: GeneralChatRequest,
        signal?: AbortSignal
    ): AsyncGenerator<ChatStreamChunk> {
        try {
            const rawStream = makeStreamRequest('/api/chat/stream', request, 'POST', signal);

            for await (const update of rawStream) {
                const lines = update.data.split('\n');
                for (const line of lines) {
                    if (!line.trim()) continue;

                    if (line.startsWith('data: ')) {
                        const jsonStr = line.slice(6);
                        try {
                            const data = JSON.parse(jsonStr);
                            // Log non-streaming status updates
                            if (data.status && data.status !== 'streaming') {
                                console.log('[SSE] Received status:', data.status);
                            }
                            yield data;
                        } catch (e) {
                            console.error('Failed to parse stream data:', jsonStr, e);
                        }
                    }
                }
            }
        } catch (error) {
            // Re-throw AbortError so callers can detect cancellation
            if (error instanceof Error && error.name === 'AbortError') {
                throw error;
            }
            yield {
                error: `Stream error: ${error instanceof Error ? error.message : String(error)}`,
                status: null
            };
        }
    }
};
