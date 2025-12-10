import { useState, useCallback } from 'react';
import { generalChatApi } from '../lib/api/generalChatApi';
import {
    GeneralChatMessage,
    InteractionType,
    ActionMetadata
} from '../types/chat';

export function useGeneralChat(initialContext?: Record<string, any>) {
    const [messages, setMessages] = useState<GeneralChatMessage[]>([]);
    const [context, setContext] = useState(initialContext || {});
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [streamingText, setStreamingText] = useState('');
    const [statusText, setStatusText] = useState<string | null>(null);

    const sendMessage = useCallback(async (
        content: string,
        interactionType: InteractionType = InteractionType.TEXT_INPUT,
        actionMetadata?: ActionMetadata
    ) => {
        console.log('[sendMessage] Starting, current messages:', messages.length, messages.map(m => m.role));

        // Add user message
        const userMessage: GeneralChatMessage = {
            role: 'user',
            content,
            timestamp: new Date().toISOString()
        };
        setMessages(prev => {
            console.log('[setMessages] Adding user message, prev:', prev.length, prev.map(m => m.role));
            return [...prev, userMessage];
        });

        setIsLoading(true);
        setError(null);
        setStreamingText('');
        setStatusText(null);

        try {
            // Stream the response
            let collectedText = '';

            for await (const chunk of generalChatApi.streamMessage({
                message: content,
                context,
                interaction_type: interactionType,
                action_metadata: actionMetadata,
                conversation_history: messages.map(msg => ({
                    role: msg.role,
                    content: msg.content,
                    timestamp: msg.timestamp
                }))
            })) {
                if (chunk.error) {
                    setError(chunk.error);
                    break;
                }

                // Handle status updates (e.g., "Thinking...", "Running web_search...")
                if (chunk.status && chunk.status !== 'streaming' && chunk.status !== 'complete') {
                    console.log('[useGeneralChat] Status update:', chunk.status);
                    setStatusText(chunk.status);
                }

                // Handle token streaming - clear status only if it's a "Running" status (not "Completed")
                if (chunk.token) {
                    setStatusText(prev => prev?.startsWith('Completed') ? prev : null);
                    collectedText += chunk.token;
                    setStreamingText(collectedText);
                }

                // Handle final payload
                if (chunk.payload && chunk.status === 'complete') {
                    const assistantMessage: GeneralChatMessage = {
                        role: 'assistant',
                        content: chunk.payload.message,
                        timestamp: new Date().toISOString(),
                        suggested_values: chunk.payload.suggested_values,
                        suggested_actions: chunk.payload.suggested_actions,
                        custom_payload: chunk.payload.custom_payload
                    };
                    setMessages(prev => {
                        console.log('[setMessages] Adding assistant message, prev:', prev.length, prev.map(m => m.role));
                        return [...prev, assistantMessage];
                    });
                    setStreamingText('');
                    setStatusText(null);
                }
            }

        } catch (err) {
            const errorMessage = err instanceof Error ? err.message : 'An error occurred';
            setError(errorMessage);

            // Add error message
            const errorMsg: GeneralChatMessage = {
                role: 'assistant',
                content: 'Sorry, something went wrong. Please try again.',
                timestamp: new Date().toISOString()
            };
            setMessages(prev => [...prev, errorMsg]);
            setStreamingText('');
        } finally {
            setIsLoading(false);
        }
    }, [context, messages]);

    const updateContext = useCallback((updates: Record<string, any>) => {
        setContext(prev => ({ ...prev, ...updates }));
    }, []);

    const reset = useCallback(() => {
        setMessages([]);
        setContext(initialContext || {});
        setError(null);
    }, [initialContext]);

    return {
        messages,
        context,
        isLoading,
        error,
        streamingText,
        statusText,
        sendMessage,
        updateContext,
        reset
    };
}
