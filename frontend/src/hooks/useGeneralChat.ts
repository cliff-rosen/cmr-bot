import { useState, useCallback, useEffect } from 'react';
import { generalChatApi } from '../lib/api/generalChatApi';
import { conversationApi, Conversation } from '../lib/api/conversationApi';
import {
    GeneralChatMessage,
    InteractionType,
    ActionMetadata
} from '../types/chat';

interface UseGeneralChatOptions {
    initialContext?: Record<string, any>;
    enabledTools?: string[];  // List of tool IDs to enable
    includeProfile?: boolean;  // Whether to include user profile
}

export function useGeneralChat(options: UseGeneralChatOptions = {}) {
    const { initialContext, enabledTools, includeProfile = true } = options;
    const [messages, setMessages] = useState<GeneralChatMessage[]>([]);
    const [context, setContext] = useState(initialContext || {});
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [streamingText, setStreamingText] = useState('');
    const [statusText, setStatusText] = useState<string | null>(null);
    const [conversationId, setConversationId] = useState<number | null>(null);
    const [isLoadingConversation, setIsLoadingConversation] = useState(false);

    // Conversation list management
    const [conversations, setConversations] = useState<Conversation[]>([]);
    const [isLoadingConversations, setIsLoadingConversations] = useState(true);

    // Load conversation list on mount
    useEffect(() => {
        const loadConversations = async () => {
            try {
                const convs = await conversationApi.list(50);
                setConversations(convs);
            } catch (err) {
                console.error('Failed to load conversations:', err);
            } finally {
                setIsLoadingConversations(false);
            }
        };
        loadConversations();
    }, []);

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
                conversation_id: conversationId ?? undefined,
                context,
                interaction_type: interactionType,
                action_metadata: actionMetadata,
                enabled_tools: enabledTools,
                include_profile: includeProfile
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
                    // Update conversation ID if returned
                    if (chunk.payload.conversation_id) {
                        setConversationId(chunk.payload.conversation_id);
                    }

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
    }, [context, conversationId, enabledTools, includeProfile]);

    const updateContext = useCallback((updates: Record<string, any>) => {
        setContext(prev => ({ ...prev, ...updates }));
    }, []);

    const reset = useCallback(() => {
        setMessages([]);
        setContext(initialContext || {});
        setError(null);
        setConversationId(null);
    }, [initialContext]);

    const newConversation = useCallback(async () => {
        try {
            const conversation = await conversationApi.create();
            setConversationId(conversation.conversation_id);
            setMessages([]);
            setContext(initialContext || {});
            setError(null);
            // Add to conversations list
            setConversations(prev => [conversation, ...prev]);
            return conversation.conversation_id;
        } catch (err) {
            console.error('Failed to create conversation:', err);
            throw err;
        }
    }, [initialContext]);

    const deleteConversation = useCallback(async (id: number) => {
        try {
            await conversationApi.delete(id);
            setConversations(prev => prev.filter(c => c.conversation_id !== id));
            // If we deleted the current conversation, reset state
            if (id === conversationId) {
                setConversationId(null);
                setMessages([]);
            }
        } catch (err) {
            console.error('Failed to delete conversation:', err);
            throw err;
        }
    }, [conversationId]);

    const refreshConversations = useCallback(async () => {
        try {
            const convs = await conversationApi.list(50);
            setConversations(convs);
        } catch (err) {
            console.error('Failed to refresh conversations:', err);
        }
    }, []);

    const loadConversation = useCallback(async (id: number) => {
        try {
            setIsLoadingConversation(true);
            const conversation = await conversationApi.get(id);
            setConversationId(conversation.conversation_id);

            if (conversation.messages && conversation.messages.length > 0) {
                const loadedMessages: GeneralChatMessage[] = conversation.messages.map(msg => ({
                    role: msg.role,
                    content: msg.content,
                    timestamp: msg.created_at,
                    suggested_values: msg.suggested_values,
                    suggested_actions: msg.suggested_actions,
                    custom_payload: msg.custom_payload
                }));
                setMessages(loadedMessages);
            } else {
                setMessages([]);
            }
            setError(null);
        } catch (err) {
            console.error('Failed to load conversation:', err);
            throw err;
        } finally {
            setIsLoadingConversation(false);
        }
    }, []);

    return {
        // Chat state
        messages,
        context,
        isLoading,
        error,
        streamingText,
        statusText,
        // Conversation state
        conversationId,
        conversations,
        isLoadingConversation,
        isLoadingConversations,
        // Chat actions
        sendMessage,
        updateContext,
        reset,
        // Conversation actions
        newConversation,
        loadConversation,
        deleteConversation,
        refreshConversations
    };
}
