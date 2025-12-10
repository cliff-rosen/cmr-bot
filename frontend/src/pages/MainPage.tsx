import { useState, useRef, useEffect } from 'react';
import { PaperAirplaneIcon, WrenchScrewdriverIcon, XMarkIcon } from '@heroicons/react/24/solid';
import { useGeneralChat } from '../hooks/useGeneralChat';
import { InteractionType, ToolCall } from '../types/chat';
import { MarkdownRenderer, JsonRenderer } from '../components/common';

/**
 * Main page with two-panel layout:
 * - Left: Chat interface for interacting with the AI agent
 * - Right: Collaborative workspace (content TBD)
 */
export default function MainPage() {
    const { messages, sendMessage, isLoading, streamingText, statusText } = useGeneralChat({});
    const [input, setInput] = useState('');
    const [selectedToolHistory, setSelectedToolHistory] = useState<ToolCall[] | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages, streamingText]);

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
            sendMessage(input.trim(), InteractionType.TEXT_INPUT);
            setInput('');
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e);
        }
    };

    const handleValueSelect = (value: string) => {
        sendMessage(value, InteractionType.VALUE_SELECTED);
    };

    const handleActionClick = async (action: any) => {
        if (action.handler === 'client') {
            console.log('Client action:', action);
        } else {
            await sendMessage(
                action.label,
                InteractionType.ACTION_EXECUTED,
                {
                    action_identifier: action.action,
                    action_data: action.data
                }
            );
        }
    };

    return (
        <div className="flex h-full">
            {/* Left Panel - Chat */}
            <div className="w-1/2 flex flex-col border-r border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
                {/* Chat Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                    <div>
                        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                            Agent Chat
                        </h2>
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                            Your personal AI assistant
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

                    {messages.map((message, idx) => (
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
                                        <MarkdownRenderer content={message.content} />
                                    ) : (
                                        <div className="text-sm whitespace-pre-wrap">{message.content}</div>
                                    )}
                                    <div className="flex items-center justify-between mt-2">
                                        <p className="text-xs opacity-60">
                                            {new Date(message.timestamp).toLocaleTimeString()}
                                        </p>
                                        {/* Tool history indicator */}
                                        {message.role === 'assistant' && message.custom_payload?.type === 'tool_history' && (
                                            <button
                                                onClick={() => setSelectedToolHistory(message.custom_payload?.data as ToolCall[])}
                                                className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300"
                                            >
                                                <WrenchScrewdriverIcon className="h-3 w-3" />
                                                {(message.custom_payload?.data as ToolCall[])?.length} tool call(s)
                                            </button>
                                        )}
                                    </div>
                                </div>
                            </div>

                            {/* Suggested Values */}
                            {message.suggested_values && message.suggested_values.length > 0 && (
                                <div className="flex flex-wrap gap-2 mt-3 ml-2">
                                    {message.suggested_values.map((suggestion, sIdx) => (
                                        <button
                                            key={sIdx}
                                            onClick={() => handleValueSelect(suggestion.value)}
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
                                    {message.suggested_actions.map((action, aIdx) => (
                                        <button
                                            key={aIdx}
                                            onClick={() => handleActionClick(action)}
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
                    ))}

                    {/* Streaming message */}
                    {streamingText && (
                        <div className="flex justify-start">
                            <div className="max-w-[85%] rounded-lg px-4 py-3 bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white">
                                <MarkdownRenderer content={streamingText} />
                                <div className="flex items-center gap-1 mt-2">
                                    <div className="animate-pulse flex gap-1">
                                        <div className="w-1.5 h-1.5 bg-blue-600 rounded-full"></div>
                                        <div className="w-1.5 h-1.5 bg-blue-600 rounded-full"></div>
                                        <div className="w-1.5 h-1.5 bg-blue-600 rounded-full"></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Loading indicator */}
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

            {/* Right Panel - Workspace */}
            <div className="w-1/2 flex flex-col bg-gray-50 dark:bg-gray-950">
                {/* Workspace Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                    <div>
                        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                            {selectedToolHistory ? 'Tool History' : 'Workspace'}
                        </h2>
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                            {selectedToolHistory ? `${selectedToolHistory.length} tool call(s)` : 'Collaborative space'}
                        </p>
                    </div>
                    {selectedToolHistory && (
                        <button
                            onClick={() => setSelectedToolHistory(null)}
                            className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                        >
                            <XMarkIcon className="h-5 w-5" />
                        </button>
                    )}
                </div>

                {/* Workspace Content */}
                <div className="flex-1 overflow-y-auto p-4">
                    {selectedToolHistory ? (
                        <div className="space-y-4">
                            {selectedToolHistory.map((toolCall, idx) => (
                                <div key={idx} className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
                                    <div className="px-4 py-3 bg-gray-100 dark:bg-gray-700 border-b border-gray-200 dark:border-gray-600">
                                        <div className="flex items-center gap-2">
                                            <WrenchScrewdriverIcon className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                                            <span className="font-medium text-gray-900 dark:text-white">
                                                {toolCall.tool_name}
                                            </span>
                                        </div>
                                    </div>
                                    <div className="p-4 space-y-3">
                                        <div>
                                            <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase mb-1">Input</h4>
                                            <div className="bg-gray-50 dark:bg-gray-900 rounded p-2 text-sm">
                                                <JsonRenderer data={toolCall.input} />
                                            </div>
                                        </div>
                                        <div>
                                            <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase mb-1">Output</h4>
                                            <div className="bg-gray-50 dark:bg-gray-900 rounded p-2 text-sm max-h-64 overflow-y-auto">
                                                {typeof toolCall.output === 'string' ? (
                                                    <pre className="whitespace-pre-wrap text-gray-700 dark:text-gray-300">{toolCall.output}</pre>
                                                ) : (
                                                    <JsonRenderer data={toolCall.output} />
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="flex items-center justify-center h-full">
                            <div className="text-center text-gray-400 dark:text-gray-500">
                                <div className="text-6xl mb-4">Workspace</div>
                                <h3 className="text-xl font-medium mb-2">Content TBD</h3>
                                <p className="text-sm max-w-md">
                                    This collaborative workspace will display assets, documents,
                                    and other content generated during your conversations with the agent.
                                </p>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
