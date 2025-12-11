import { useState, useRef, useEffect } from 'react';
import { PaperAirplaneIcon, WrenchScrewdriverIcon, DocumentPlusIcon, ArrowTopRightOnSquareIcon } from '@heroicons/react/24/solid';
import { MarkdownRenderer } from '../common';
import { GeneralChatMessage, ToolCall, SuggestedValue, SuggestedAction, WorkspacePayload, parseWorkspacePayload } from '../../types/chat';

interface ChatPanelProps {
    messages: GeneralChatMessage[];
    conversationId: number | null;
    isLoading: boolean;
    streamingText: string;
    statusText: string | null;
    onSendMessage: (message: string) => void;
    onValueSelect: (value: string) => void;
    onActionClick: (action: any) => void;
    onToolHistoryClick: (toolHistory: ToolCall[]) => void;
    onSaveMessageAsAsset: (message: GeneralChatMessage) => void;
    onPayloadClick: (payload: WorkspacePayload) => void;
}

export default function ChatPanel({
    messages,
    conversationId,
    isLoading,
    streamingText,
    statusText,
    onSendMessage,
    onValueSelect,
    onActionClick,
    onToolHistoryClick,
    onSaveMessageAsAsset,
    onPayloadClick
}: ChatPanelProps) {
    const [input, setInput] = useState('');
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);
      const lastPayloadShownRef = useRef<string | null>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages, streamingText]);

    // Auto-show payload in workspace when new message with payload arrives
    useEffect(() => {
        if (messages.length === 0) return;
        const lastMessage = messages[messages.length - 1];
        if (lastMessage.role !== 'assistant') return;

        const { payload } = parseWorkspacePayload(lastMessage.content);
        if (payload) {
            // Create a unique key for this payload to avoid re-triggering
            const payloadKey = `${lastMessage.timestamp}-${payload.title}`;
            if (lastPayloadShownRef.current !== payloadKey) {
                lastPayloadShownRef.current = payloadKey;
                onPayloadClick(payload);
            }
        }
    }, [messages, onPayloadClick]);

    // Auto-resize textarea
    useEffect(() => {
        if (inputRef.current) {
            inputRef.current.style.height = 'auto';
            inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 200)}px`;
        }
    }, [input]);

    // Keep focus on input after messages update
    useEffect(() => {
        if (!isLoading && inputRef.current) {
            inputRef.current.focus();
        }
    }, [isLoading, messages]);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (input.trim() && !isLoading) {
            onSendMessage(input.trim());
            setInput('');
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e);
        }
    };

    return (
        <div className="flex-1 flex flex-col bg-white dark:bg-gray-900 min-w-0">
            {/* Chat Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                <div>
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                        Agent Chat
                    </h2>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                        {conversationId ? `Conversation #${conversationId}` : 'New conversation'}
                    </p>
                </div>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-full text-center text-gray-500 dark:text-gray-400">
                        <div className="text-4xl mb-4">
                            <span role="img" aria-label="robot">AI Agent</span>
                        </div>
                        <p className="text-lg font-medium mb-2">How can I help you today?</p>
                        <p className="text-sm max-w-md">
                            I can help you research topics, search the web, find scientific literature,
                            and work with you on various tasks.
                        </p>
                    </div>
                )}

                {messages.map((message, idx) => {
                    // Parse payload from assistant messages
                    const { text: displayText, payload } = message.role === 'assistant'
                        ? parseWorkspacePayload(message.content)
                        : { text: message.content, payload: null };

                    return (
                    <div key={idx}>
                        <div className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                            <div
                                className={`max-w-[85%] rounded-lg px-4 py-3 ${
                                    message.role === 'user'
                                        ? 'bg-blue-600 text-white'
                                        : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white'
                                }`}
                            >
                                {message.role === 'assistant' ? (
                                    <MarkdownRenderer content={displayText} />
                                ) : (
                                    <div className="text-sm whitespace-pre-wrap">{displayText}</div>
                                )}

                                {/* Payload indicator */}
                                {payload && (
                                    <button
                                        onClick={() => onPayloadClick(payload)}
                                        className="mt-2 w-full flex items-center justify-between gap-2 px-3 py-2 bg-white/50 dark:bg-gray-700/50 rounded-lg border border-gray-200 dark:border-gray-600 hover:bg-white dark:hover:bg-gray-700 transition-colors"
                                    >
                                        <span className="text-sm font-medium text-gray-700 dark:text-gray-200">
                                            {payload.title}
                                        </span>
                                        <span className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400">
                                            <ArrowTopRightOnSquareIcon className="h-3 w-3" />
                                            View in Workspace
                                        </span>
                                    </button>
                                )}

                                <div className="flex items-center justify-between mt-2">
                                    <p className="text-xs opacity-60">
                                        {new Date(message.timestamp).toLocaleTimeString()}
                                    </p>
                                    <div className="flex items-center gap-2">
                                        {/* Tool history indicator */}
                                        {message.role === 'assistant' && message.custom_payload?.type === 'tool_history' && (
                                            <button
                                                onClick={() => onToolHistoryClick(message.custom_payload?.data as ToolCall[])}
                                                className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300"
                                            >
                                                <WrenchScrewdriverIcon className="h-3 w-3" />
                                                {(message.custom_payload?.data as ToolCall[])?.length} tool call(s)
                                            </button>
                                        )}
                                        {/* Save as asset button */}
                                        <button
                                            onClick={() => onSaveMessageAsAsset(message)}
                                            className={`flex items-center gap-1 text-xs hover:opacity-80 ${
                                                message.role === 'user'
                                                    ? 'text-blue-200'
                                                    : 'text-gray-500 dark:text-gray-400'
                                            }`}
                                            title="Save as asset"
                                        >
                                            <DocumentPlusIcon className="h-3 w-3" />
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Suggested Values */}
                        {message.suggested_values && message.suggested_values.length > 0 && (
                            <div className="flex flex-wrap gap-2 mt-3 ml-2">
                                {message.suggested_values.map((suggestion: SuggestedValue, sIdx: number) => (
                                    <button
                                        key={sIdx}
                                        onClick={() => onValueSelect(suggestion.value)}
                                        disabled={isLoading}
                                        className="px-3 py-1.5 bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 rounded-full text-sm hover:bg-blue-200 dark:hover:bg-blue-800 transition-colors disabled:opacity-50"
                                    >
                                        {suggestion.label}
                                    </button>
                                ))}
                            </div>
                        )}

                        {/* Suggested Actions */}
                        {message.suggested_actions && message.suggested_actions.length > 0 && (
                            <div className="flex flex-wrap gap-2 mt-3 ml-2">
                                {message.suggested_actions.map((action: SuggestedAction, aIdx: number) => (
                                    <button
                                        key={aIdx}
                                        onClick={() => onActionClick(action)}
                                        disabled={isLoading}
                                        className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
                                            action.style === 'primary'
                                                ? 'bg-blue-600 hover:bg-blue-700 text-white'
                                                : action.style === 'warning'
                                                    ? 'bg-yellow-600 hover:bg-yellow-700 text-white'
                                                    : 'bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-900 dark:text-white'
                                        }`}
                                    >
                                        {action.label}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                    );
                })}

                {/* Streaming message */}
                {streamingText && (
                    <div className="flex justify-start">
                        <div className="max-w-[85%] rounded-lg px-4 py-3 bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white">
                            <MarkdownRenderer content={streamingText} />
                            <div className="flex items-center gap-2 mt-2">
                                {statusText ? (
                                    <>
                                        <WrenchScrewdriverIcon className="h-4 w-4 text-blue-600 dark:text-blue-400 animate-pulse" />
                                        <span className="text-sm text-blue-600 dark:text-blue-400">
                                            {statusText}
                                        </span>
                                    </>
                                ) : isLoading ? (
                                    <div className="animate-pulse flex gap-1">
                                        <div className="w-1.5 h-1.5 bg-blue-600 rounded-full"></div>
                                        <div className="w-1.5 h-1.5 bg-blue-600 rounded-full"></div>
                                        <div className="w-1.5 h-1.5 bg-blue-600 rounded-full"></div>
                                    </div>
                                ) : null}
                            </div>
                        </div>
                    </div>
                )}

                {/* Loading indicator - only when no streaming text yet */}
                {isLoading && !streamingText && (
                    <div className="flex justify-start">
                        <div className="bg-gray-100 dark:bg-gray-800 rounded-lg px-4 py-3">
                            <div className="flex items-center gap-2">
                                <div className="animate-pulse flex gap-1">
                                    <div className="w-2 h-2 bg-gray-400 rounded-full"></div>
                                    <div className="w-2 h-2 bg-gray-400 rounded-full"></div>
                                    <div className="w-2 h-2 bg-gray-400 rounded-full"></div>
                                </div>
                                <span className="text-sm text-gray-600 dark:text-gray-400">
                                    {statusText || 'Thinking...'}
                                </span>
                            </div>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="p-4 border-t border-gray-200 dark:border-gray-700">
                <form onSubmit={handleSubmit} className="flex gap-3">
                    <textarea
                        ref={inputRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Type your message... (Shift+Enter for new line)"
                        disabled={isLoading}
                        rows={1}
                        className="flex-1 px-4 py-3 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none disabled:opacity-50"
                    />
                    <button
                        type="submit"
                        disabled={!input.trim() || isLoading}
                        className="px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                        <PaperAirplaneIcon className="h-5 w-5" />
                    </button>
                </form>
            </div>
        </div>
    );
}
