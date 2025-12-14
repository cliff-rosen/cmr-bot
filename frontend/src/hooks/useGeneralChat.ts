import { useState, useCallback, useEffect, useRef } from 'react';
import { generalChatApi, ToolProgressEvent } from '../lib/api/generalChatApi';
import { conversationApi, Conversation } from '../lib/api/conversationApi';
import {
    GeneralChatMessage,
    InteractionType,
    ActionMetadata
} from '../types/chat';

export interface ActiveToolProgress {
    toolName: string;
    updates: ToolProgressEvent[];
}

interface UseGeneralChatOptions {
    initialContext?: Record<string, any>;
    enabledTools?: string[];  // List of tool IDs to enable
    includeProfile?: boolean;  // Whether to include user profile
    onToolCallsComplete?: (toolNames: string[]) => void;  // Called when tool calls complete
}

export function useGeneralChat(options: UseGeneralChatOptions = {}) {
    const { initialContext, enabledTools, includeProfile = true, onToolCallsComplete } = options;
    const [messages, setMessages] = useState<GeneralChatMessage[]>([]);
    const [context, setContext] = useState(initialContext || {});
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [streamingText, setStreamingText] = useState('');
    const [statusText, setStatusText] = useState<string | null>(null);
    const [conversationId, setConversationId] = useState<number | null>(null);
    const [isLoadingConversation, setIsLoadingConversation] = useState(false);

    // Tool progress tracking
    const [activeToolProgress, setActiveToolProgress] = useState<ActiveToolProgress | null>(null);

    // Cancellation support
    const abortControllerRef = useRef<AbortController | null>(null);

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
        setActiveToolProgress(null);

        // Create new AbortController for this request
        const abortController = new AbortController();
        abortControllerRef.current = abortController;

        // Track collected text outside try block so it's accessible in catch for cancellation
        let collectedText = '';

        try {
            for await (const event of generalChatApi.streamMessage({
                message: content,
                conversation_id: conversationId ?? undefined,
                context,
                interaction_type: interactionType,
                action_metadata: actionMetadata,
                enabled_tools: enabledTools,
                include_profile: includeProfile
            }, abortController.signal)) {
                switch (event.type) {
                    case 'text_delta':
                        // Clear status when streaming text (unless it's "Completed...")
                        setStatusText(prev => prev?.startsWith('Completed') ? prev : null);
                        setActiveToolProgress(null);
                        collectedText += event.text;
                        setStreamingText(collectedText);
                        break;

                    case 'status':
                        console.log('[useGeneralChat] Status:', event.message);
                        setStatusText(event.message);
                        break;

                    case 'tool_start':
                        setStatusText(`Running ${event.tool.replace(/_/g, ' ')}...`);
                        setActiveToolProgress({ toolName: event.tool, updates: [] });
                        break;

                    case 'tool_progress':
                        setActiveToolProgress(prev => {
                            if (prev && prev.toolName === event.tool) {
                                return { ...prev, updates: [...prev.updates, event] };
                            }
                            return { toolName: event.tool, updates: [event] };
                        });
                        break;

                    case 'tool_complete':
                        setActiveToolProgress(null);
                        setStatusText(null);
                        break;

                    case 'complete': {
                        const responsePayload = event.payload;

                        // Update conversation ID if returned (new conversation was created)
                        if (responsePayload.conversation_id && responsePayload.conversation_id !== conversationId) {
                            setConversationId(responsePayload.conversation_id);
                            // Refresh conversation list to include the new conversation
                            conversationApi.list(50).then(convs => setConversations(convs)).catch(console.error);
                        }

                        const assistantMessage: GeneralChatMessage = {
                            role: 'assistant',
                            content: responsePayload.message,
                            timestamp: new Date().toISOString(),
                            suggested_values: responsePayload.suggested_values,
                            suggested_actions: responsePayload.suggested_actions,
                            custom_payload: responsePayload.custom_payload,
                            workspace_payload: responsePayload.workspace_payload
                        };
                        setMessages(prev => {
                            console.log('[setMessages] Adding assistant message, prev:', prev.length, prev.map(m => m.role));
                            return [...prev, assistantMessage];
                        });
                        setStreamingText('');
                        setStatusText(null);

                        // Notify about tool calls if any
                        if (onToolCallsComplete && responsePayload.custom_payload?.type === 'tool_history') {
                            const toolCalls = responsePayload.custom_payload.data as Array<{ tool_name: string }>;
                            const toolNames = toolCalls.map(tc => tc.tool_name);
                            onToolCallsComplete(toolNames);
                        }
                        break;
                    }

                    case 'error':
                        setError(event.message);
                        // Add error as a visible message so the user knows what happened
                        const errorMessage: GeneralChatMessage = {
                            role: 'assistant',
                            content: `**Error:** ${event.message}\n\nPlease try again or check your API configuration.`,
                            timestamp: new Date().toISOString()
                        };
                        setMessages(prev => [...prev, errorMessage]);
                        setStreamingText('');
                        setStatusText(null);
                        setActiveToolProgress(null);
                        break;

                    case 'cancelled':
                        setStatusText('Cancelled');
                        break;
                }
            }

        } catch (err) {
            // Don't show error for intentional cancellation
            if (err instanceof Error && err.name === 'AbortError') {
                // Request was cancelled - add a note if there was streaming text
                if (collectedText) {
                    const cancelledMessage: GeneralChatMessage = {
                        role: 'assistant',
                        content: collectedText + '\n\n*[Response cancelled]*',
                        timestamp: new Date().toISOString()
                    };
                    setMessages(prev => [...prev, cancelledMessage]);
                }
                setStreamingText('');
                setStatusText(null);
                setActiveToolProgress(null);
                return;
            }

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
            abortControllerRef.current = null;
        }
    }, [context, conversationId, enabledTools, includeProfile]);

    const cancelRequest = useCallback(() => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
        }
    }, []);

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
        activeToolProgress,
        // Conversation state
        conversationId,
        conversations,
        isLoadingConversation,
        isLoadingConversations,
        // Chat actions
        sendMessage,
        cancelRequest,
        updateContext,
        reset,
        // Conversation actions
        newConversation,
        loadConversation,
        deleteConversation,
        refreshConversations
    };
}
