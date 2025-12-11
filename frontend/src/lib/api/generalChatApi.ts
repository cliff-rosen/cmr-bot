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
}

export interface ChatResponsePayload {
    message: string;
    conversation_id?: number;  // The conversation this message belongs to
    suggested_values?: SuggestedValue[];
    suggested_actions?: SuggestedAction[];
    custom_payload?: CustomPayload;
}

export interface ChatStreamChunk {
    token?: string | null;
    response_text?: string | null;
    payload?: ChatResponsePayload | null;
    status?: string | null;
    error?: string | null;
    debug?: any;
}

export const generalChatApi = {
    /**
     * Stream chat messages from the backend
     * @param request - Chat request with message, context, and interaction type
     * @returns AsyncGenerator that yields stream chunks
     */
    async* streamMessage(
        request: GeneralChatRequest
    ): AsyncGenerator<ChatStreamChunk> {
        try {
            const rawStream = makeStreamRequest('/api/chat/stream', request, 'POST');

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
            yield {
                error: `Stream error: ${error instanceof Error ? error.message : String(error)}`,
                status: null
            };
        }
    }
};
