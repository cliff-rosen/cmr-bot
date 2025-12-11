import { useState, useRef, useEffect, useCallback } from 'react';
import { PaperAirplaneIcon, WrenchScrewdriverIcon, XMarkIcon, PlusIcon, ChatBubbleLeftRightIcon, TrashIcon, ChevronLeftIcon, ChevronRightIcon, Cog6ToothIcon, DocumentIcon, CpuChipIcon, LightBulbIcon, BookmarkIcon, ArchiveBoxArrowDownIcon, UserIcon, HeartIcon, BuildingOfficeIcon, FolderIcon, ClockIcon } from '@heroicons/react/24/solid';
import { BookmarkIcon as BookmarkOutlineIcon } from '@heroicons/react/24/outline';
import { useGeneralChat } from '../hooks/useGeneralChat';
import { InteractionType, ToolCall } from '../types/chat';
import { MarkdownRenderer, JsonRenderer } from '../components/common';
import { memoryApi, Memory, MemoryType, assetApi, Asset } from '../lib/api';

const SIDEBAR_WIDTH = 256;
const CONTEXT_PANEL_WIDTH = 280;
const MIN_CHAT_WIDTH = 300;
const MIN_WORKSPACE_WIDTH = 200;

/**
 * Main page with four-panel layout:
 * - Left sidebar: Conversation history (collapsible)
 * - Center-left: Chat interface for interacting with the AI agent
 * - Center-right: Collaborative workspace (resizable)
 * - Right sidebar: Context panel - tools, assets, settings (collapsible)
 */
export default function MainPage() {
    const {
        messages,
        sendMessage,
        isLoading,
        streamingText,
        statusText,
        conversationId,
        conversations,
        isLoadingConversations,
        newConversation,
        loadConversation,
        deleteConversation
    } = useGeneralChat({});
    const [input, setInput] = useState('');
    const [selectedToolHistory, setSelectedToolHistory] = useState<ToolCall[] | null>(null);
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);
    const [isContextPanelOpen, setIsContextPanelOpen] = useState(true);
    const [workspaceWidth, setWorkspaceWidth] = useState(400);
    const [isDragging, setIsDragging] = useState(false);
    const [memories, setMemories] = useState<Memory[]>([]);
    const [assets, setAssets] = useState<Asset[]>([]);
    const [newMemoryInput, setNewMemoryInput] = useState('');
    const [memoryFilter, setMemoryFilter] = useState<MemoryType | 'all' | 'pinned'>('all');
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    // Get the last tool history from messages for the context panel
    const lastToolHistory = messages
        .filter(m => m.role === 'assistant' && m.custom_payload?.type === 'tool_history')
        .slice(-1)[0]?.custom_payload?.data as ToolCall[] | undefined;

    // Handle divider drag
    const handleMouseDown = useCallback((e: React.MouseEvent) => {
        e.preventDefault();
        setIsDragging(true);
    }, []);

    useEffect(() => {
        if (!isDragging) return;

        const handleMouseMove = (e: MouseEvent) => {
            if (!containerRef.current) return;
            const containerRect = containerRef.current.getBoundingClientRect();
            const sidebarW = isSidebarOpen ? SIDEBAR_WIDTH : 0;
            const contextPanelW = isContextPanelOpen ? CONTEXT_PANEL_WIDTH : 0;
            // Calculate workspace width: distance from mouse to where context panel starts
            const newWorkspaceWidth = containerRect.right - contextPanelW - 6 - e.clientX; // 6px for toggle button
            const availableWidth = containerRect.width - sidebarW - 6 - contextPanelW - 6; // account for both toggle buttons

            // Clamp workspace width
            const clampedWidth = Math.max(
                MIN_WORKSPACE_WIDTH,
                Math.min(newWorkspaceWidth, availableWidth - MIN_CHAT_WIDTH)
            );
            setWorkspaceWidth(clampedWidth);
        };

        const handleMouseUp = () => {
            setIsDragging(false);
        };

        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);

        return () => {
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
        };
    }, [isDragging, isSidebarOpen, isContextPanelOpen]);

    // Load memories and assets on mount
    useEffect(() => {
        const loadMemoriesAndAssets = async () => {
            try {
                const [mems, assts] = await Promise.all([
                    memoryApi.list(),
                    assetApi.list()
                ]);
                setMemories(mems);
                setAssets(assts);
            } catch (err) {
                console.error('Failed to load memories/assets:', err);
            }
        };
        loadMemoriesAndAssets();
    }, []);

    // Conversation handlers - delegate to hook
    const handleNewConversation = async () => {
        try {
            await newConversation();
        } catch (err) {
            console.error('Failed to create new conversation:', err);
        }
    };

    const handleSelectConversation = async (convId: number) => {
        if (convId === conversationId) return;
        try {
            await loadConversation(convId);
            setSelectedToolHistory(null);
        } catch (err) {
            console.error('Failed to load conversation:', err);
        }
    };

    const handleDeleteConversation = async (convId: number, e: React.MouseEvent) => {
        e.stopPropagation();
        if (!confirm('Delete this conversation?')) return;
        try {
            await deleteConversation(convId);
        } catch (err) {
            console.error('Failed to delete conversation:', err);
        }
    };

    // Memory handlers
    const handleAddWorkingMemory = async () => {
        if (!newMemoryInput.trim()) return;
        try {
            const newMem = await memoryApi.create({
                content: newMemoryInput.trim(),
                memory_type: 'working',
                source_conversation_id: conversationId || undefined
            });
            setMemories(prev => [newMem, ...prev]);
            setNewMemoryInput('');
        } catch (err) {
            console.error('Failed to add memory:', err);
        }
    };

    const handleToggleMemoryActive = async (memId: number) => {
        try {
            const result = await memoryApi.toggleActive(memId);
            setMemories(prev => prev.map(m =>
                m.memory_id === memId ? { ...m, is_active: result.is_active } : m
            ));
        } catch (err) {
            console.error('Failed to toggle memory:', err);
        }
    };

    const handleToggleMemoryPinned = async (memId: number) => {
        try {
            const result = await memoryApi.togglePinned(memId);
            setMemories(prev => prev.map(m =>
                m.memory_id === memId ? { ...m, is_pinned: result.is_pinned } : m
            ));
        } catch (err) {
            console.error('Failed to toggle memory pin:', err);
        }
    };

    const handleDeleteMemory = async (memId: number) => {
        try {
            await memoryApi.delete(memId);
            setMemories(prev => prev.filter(m => m.memory_id !== memId));
        } catch (err) {
            console.error('Failed to delete memory:', err);
        }
    };

    // Asset handlers
    const handleToggleAssetContext = async (assetId: number) => {
        try {
            const result = await assetApi.toggleContext(assetId);
            setAssets(prev => prev.map(a =>
                a.asset_id === assetId ? { ...a, is_in_context: result.is_in_context } : a
            ));
        } catch (err) {
            console.error('Failed to toggle asset context:', err);
        }
    };

    const handleDeleteAsset = async (assetId: number) => {
        try {
            await assetApi.delete(assetId);
            setAssets(prev => prev.filter(a => a.asset_id !== assetId));
        } catch (err) {
            console.error('Failed to delete asset:', err);
        }
    };

    // Save tool output as asset
    const handleSaveToolOutputAsAsset = async (toolCall: ToolCall) => {
        try {
            const content = typeof toolCall.output === 'string'
                ? toolCall.output
                : JSON.stringify(toolCall.output, null, 2);

            const newAsset = await assetApi.create({
                name: `${toolCall.tool_name} result`,
                asset_type: 'data',
                content,
                description: `Output from ${toolCall.tool_name} tool call`,
                source_conversation_id: conversationId || undefined
            });
            setAssets(prev => [newAsset, ...prev]);
        } catch (err) {
            console.error('Failed to save as asset:', err);
        }
    };

    // Helper to get memory type icon and color
    const getMemoryTypeInfo = (type: MemoryType) => {
        switch (type) {
            case 'fact':
                return { icon: UserIcon, color: 'text-blue-500', bg: 'bg-blue-100 dark:bg-blue-900/30', label: 'Fact' };
            case 'preference':
                return { icon: HeartIcon, color: 'text-pink-500', bg: 'bg-pink-100 dark:bg-pink-900/30', label: 'Preference' };
            case 'entity':
                return { icon: BuildingOfficeIcon, color: 'text-purple-500', bg: 'bg-purple-100 dark:bg-purple-900/30', label: 'Entity' };
            case 'project':
                return { icon: FolderIcon, color: 'text-green-500', bg: 'bg-green-100 dark:bg-green-900/30', label: 'Project' };
            case 'working':
                return { icon: ClockIcon, color: 'text-yellow-500', bg: 'bg-yellow-100 dark:bg-yellow-900/30', label: 'Session' };
            default:
                return { icon: LightBulbIcon, color: 'text-gray-500', bg: 'bg-gray-100 dark:bg-gray-900/30', label: type };
        }
    };

    // Derived data for context panel
    const filteredMemories = memories.filter(m => {
        if (!m.is_active) return false;
        if (memoryFilter === 'all') return true;
        if (memoryFilter === 'pinned') return m.is_pinned;
        return m.memory_type === memoryFilter;
    });
    const pinnedCount = memories.filter(m => m.is_pinned && m.is_active).length;
    const memoryCounts = {
        all: memories.filter(m => m.is_active).length,
        pinned: pinnedCount,
        fact: memories.filter(m => m.memory_type === 'fact' && m.is_active).length,
        preference: memories.filter(m => m.memory_type === 'preference' && m.is_active).length,
        entity: memories.filter(m => m.memory_type === 'entity' && m.is_active).length,
        project: memories.filter(m => m.memory_type === 'project' && m.is_active).length,
        working: memories.filter(m => m.memory_type === 'working' && m.is_active).length,
    };
    const contextAssets = assets.filter(a => a.is_in_context);
    const otherAssets = assets.filter(a => !a.is_in_context);

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
        <div ref={containerRef} className={`flex h-full ${isDragging ? 'select-none' : ''}`}>
            {/* Left Sidebar - Conversation List (Collapsible) */}
            <div
                className={`flex flex-col border-r border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 transition-all duration-300 ${
                    isSidebarOpen ? 'w-64' : 'w-0'
                } overflow-hidden`}
            >
                {/* Sidebar Header */}
                <div className="flex items-center justify-between px-4 py-4 border-b border-gray-200 dark:border-gray-700 min-w-[256px]">
                    <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
                        Conversations
                    </h2>
                    <button
                        onClick={handleNewConversation}
                        className="p-1.5 text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white hover:bg-gray-200 dark:hover:bg-gray-700 rounded"
                        title="New conversation"
                    >
                        <PlusIcon className="h-5 w-5" />
                    </button>
                </div>

                {/* Conversation List */}
                <div className="flex-1 overflow-y-auto min-w-[256px]">
                    {isLoadingConversations ? (
                        <div className="p-4 text-center text-gray-500 dark:text-gray-400 text-sm">
                            Loading...
                        </div>
                    ) : conversations.length === 0 ? (
                        <div className="p-4 text-center text-gray-500 dark:text-gray-400 text-sm">
                            No conversations yet
                        </div>
                    ) : (
                        <div className="py-2">
                            {conversations.map((conv) => (
                                <div
                                    key={conv.conversation_id}
                                    onClick={() => handleSelectConversation(conv.conversation_id)}
                                    className={`group flex items-center gap-2 px-4 py-2.5 cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-800 ${
                                        conv.conversation_id === conversationId
                                            ? 'bg-gray-200 dark:bg-gray-800'
                                            : ''
                                    }`}
                                >
                                    <ChatBubbleLeftRightIcon className="h-4 w-4 text-gray-400 flex-shrink-0" />
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm text-gray-900 dark:text-white truncate">
                                            {conv.title || 'New conversation'}
                                        </p>
                                        <p className="text-xs text-gray-500 dark:text-gray-400">
                                            {new Date(conv.updated_at).toLocaleDateString()}
                                        </p>
                                    </div>
                                    <button
                                        onClick={(e) => handleDeleteConversation(conv.conversation_id, e)}
                                        className="p-1 text-gray-400 hover:text-red-600 dark:hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                                        title="Delete conversation"
                                    >
                                        <TrashIcon className="h-4 w-4" />
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {/* Sidebar Toggle Button */}
            <button
                onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                className="flex-shrink-0 w-6 flex items-center justify-center bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 border-r border-gray-200 dark:border-gray-700 transition-colors"
                title={isSidebarOpen ? 'Hide conversations' : 'Show conversations'}
            >
                {isSidebarOpen ? (
                    <ChevronLeftIcon className="h-4 w-4 text-gray-500" />
                ) : (
                    <ChevronRightIcon className="h-4 w-4 text-gray-500" />
                )}
            </button>

            {/* Center Panel - Chat */}
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

            {/* Resizable Divider */}
            <div
                onMouseDown={handleMouseDown}
                className={`flex-shrink-0 w-1.5 cursor-col-resize hover:bg-blue-500 transition-colors ${
                    isDragging ? 'bg-blue-500' : 'bg-gray-200 dark:bg-gray-700'
                }`}
                title="Drag to resize"
            />

            {/* Right Panel - Workspace */}
            <div
                style={{ width: workspaceWidth }}
                className="flex-shrink-0 flex flex-col bg-gray-50 dark:bg-gray-950"
            >
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
                                            <div className="flex items-center justify-between mb-1">
                                                <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Output</h4>
                                                <button
                                                    onClick={() => handleSaveToolOutputAsAsset(toolCall)}
                                                    className="flex items-center gap-1 px-2 py-1 text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors"
                                                    title="Save output as asset"
                                                >
                                                    <ArchiveBoxArrowDownIcon className="h-3 w-3" />
                                                    Save as Asset
                                                </button>
                                            </div>
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

            {/* Context Panel Toggle Button */}
            <button
                onClick={() => setIsContextPanelOpen(!isContextPanelOpen)}
                className="flex-shrink-0 w-6 flex items-center justify-center bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 border-l border-gray-200 dark:border-gray-700 transition-colors"
                title={isContextPanelOpen ? 'Hide context' : 'Show context'}
            >
                {isContextPanelOpen ? (
                    <ChevronRightIcon className="h-4 w-4 text-gray-500" />
                ) : (
                    <ChevronLeftIcon className="h-4 w-4 text-gray-500" />
                )}
            </button>

            {/* Right Sidebar - Context Panel (Collapsible) */}
            <div
                className={`flex flex-col border-l border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 transition-all duration-300 ${
                    isContextPanelOpen ? 'w-[280px]' : 'w-0'
                } overflow-hidden`}
            >
                {/* Context Panel Header */}
                <div className="flex items-center justify-between px-4 py-4 border-b border-gray-200 dark:border-gray-700 min-w-[280px]">
                    <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
                        Context
                    </h2>
                    <Cog6ToothIcon className="h-5 w-5 text-gray-400" />
                </div>

                {/* Context Panel Content */}
                <div className="flex-1 overflow-y-auto min-w-[280px]">
                    {/* Active Tools Section */}
                    <div className="border-b border-gray-200 dark:border-gray-700">
                        <div className="px-4 py-3 bg-gray-100 dark:bg-gray-800">
                            <div className="flex items-center gap-2">
                                <WrenchScrewdriverIcon className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                                <span className="text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase">
                                    Available Tools
                                </span>
                            </div>
                        </div>
                        <div className="p-3 space-y-1">
                            <div className="flex items-center gap-2 px-2 py-1.5 rounded text-sm text-gray-700 dark:text-gray-300">
                                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                                web_search
                            </div>
                            <div className="flex items-center gap-2 px-2 py-1.5 rounded text-sm text-gray-700 dark:text-gray-300">
                                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                                fetch_webpage
                            </div>
                        </div>
                    </div>

                    {/* Memories Section */}
                    <div className="border-b border-gray-200 dark:border-gray-700">
                        <div className="px-4 py-3 bg-gray-100 dark:bg-gray-800">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <LightBulbIcon className="h-4 w-4 text-yellow-600 dark:text-yellow-400" />
                                    <span className="text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase">
                                        Memories
                                    </span>
                                    <span className="text-xs text-gray-500">({memoryCounts.all})</span>
                                </div>
                            </div>
                        </div>

                        {/* Memory Type Filter Tabs */}
                        <div className="px-2 py-2 border-b border-gray-200 dark:border-gray-700 overflow-x-auto">
                            <div className="flex gap-1 min-w-max">
                                <button
                                    onClick={() => setMemoryFilter('all')}
                                    className={`px-2 py-1 text-xs rounded-full transition-colors ${
                                        memoryFilter === 'all'
                                            ? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white'
                                            : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800'
                                    }`}
                                >
                                    All
                                </button>
                                <button
                                    onClick={() => setMemoryFilter('pinned')}
                                    className={`px-2 py-1 text-xs rounded-full transition-colors flex items-center gap-1 ${
                                        memoryFilter === 'pinned'
                                            ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300'
                                            : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800'
                                    }`}
                                >
                                    <BookmarkIcon className="h-3 w-3" />
                                    {memoryCounts.pinned > 0 && memoryCounts.pinned}
                                </button>
                                <button
                                    onClick={() => setMemoryFilter('fact')}
                                    className={`px-2 py-1 text-xs rounded-full transition-colors flex items-center gap-1 ${
                                        memoryFilter === 'fact'
                                            ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300'
                                            : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800'
                                    }`}
                                >
                                    <UserIcon className="h-3 w-3" />
                                    {memoryCounts.fact > 0 && memoryCounts.fact}
                                </button>
                                <button
                                    onClick={() => setMemoryFilter('preference')}
                                    className={`px-2 py-1 text-xs rounded-full transition-colors flex items-center gap-1 ${
                                        memoryFilter === 'preference'
                                            ? 'bg-pink-100 dark:bg-pink-900/50 text-pink-700 dark:text-pink-300'
                                            : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800'
                                    }`}
                                >
                                    <HeartIcon className="h-3 w-3" />
                                    {memoryCounts.preference > 0 && memoryCounts.preference}
                                </button>
                                <button
                                    onClick={() => setMemoryFilter('entity')}
                                    className={`px-2 py-1 text-xs rounded-full transition-colors flex items-center gap-1 ${
                                        memoryFilter === 'entity'
                                            ? 'bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300'
                                            : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800'
                                    }`}
                                >
                                    <BuildingOfficeIcon className="h-3 w-3" />
                                    {memoryCounts.entity > 0 && memoryCounts.entity}
                                </button>
                                <button
                                    onClick={() => setMemoryFilter('project')}
                                    className={`px-2 py-1 text-xs rounded-full transition-colors flex items-center gap-1 ${
                                        memoryFilter === 'project'
                                            ? 'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300'
                                            : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800'
                                    }`}
                                >
                                    <FolderIcon className="h-3 w-3" />
                                    {memoryCounts.project > 0 && memoryCounts.project}
                                </button>
                                <button
                                    onClick={() => setMemoryFilter('working')}
                                    className={`px-2 py-1 text-xs rounded-full transition-colors flex items-center gap-1 ${
                                        memoryFilter === 'working'
                                            ? 'bg-yellow-100 dark:bg-yellow-900/50 text-yellow-700 dark:text-yellow-300'
                                            : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800'
                                    }`}
                                >
                                    <ClockIcon className="h-3 w-3" />
                                    {memoryCounts.working > 0 && memoryCounts.working}
                                </button>
                            </div>
                        </div>

                        {/* Quick add working memory */}
                        {memoryFilter === 'working' && (
                            <div className="px-3 py-2 border-b border-gray-200 dark:border-gray-700">
                                <div className="flex gap-1">
                                    <input
                                        type="text"
                                        value={newMemoryInput}
                                        onChange={(e) => setNewMemoryInput(e.target.value)}
                                        onKeyDown={(e) => e.key === 'Enter' && handleAddWorkingMemory()}
                                        placeholder="Add session note..."
                                        className="flex-1 px-2 py-1 text-xs rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                                    />
                                    <button
                                        onClick={handleAddWorkingMemory}
                                        className="px-2 py-1 text-xs bg-yellow-500 text-white rounded hover:bg-yellow-600"
                                    >
                                        +
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* Memory list */}
                        <div className="p-2 space-y-1 max-h-64 overflow-y-auto">
                            {filteredMemories.length === 0 ? (
                                <div className="text-center text-gray-400 dark:text-gray-500 text-xs py-4">
                                    {memoryFilter === 'all'
                                        ? "No memories yet. The AI will remember important things you share."
                                        : `No ${memoryFilter === 'pinned' ? 'pinned' : memoryFilter} memories`}
                                </div>
                            ) : (
                                filteredMemories.map((mem) => {
                                    const typeInfo = getMemoryTypeInfo(mem.memory_type);
                                    const TypeIcon = typeInfo.icon;
                                    return (
                                        <div
                                            key={mem.memory_id}
                                            className={`flex items-start gap-2 px-2 py-1.5 rounded ${typeInfo.bg}`}
                                        >
                                            <TypeIcon className={`h-3 w-3 mt-0.5 flex-shrink-0 ${typeInfo.color}`} />
                                            <span className="flex-1 text-gray-700 dark:text-gray-300 text-xs leading-relaxed">
                                                {mem.content}
                                            </span>
                                            <div className="flex items-center gap-1 flex-shrink-0">
                                                <button
                                                    onClick={() => handleToggleMemoryPinned(mem.memory_id)}
                                                    className={`${mem.is_pinned ? 'text-blue-500' : 'text-gray-400 hover:text-blue-500'}`}
                                                    title={mem.is_pinned ? "Unpin" : "Pin memory"}
                                                >
                                                    {mem.is_pinned ? (
                                                        <BookmarkIcon className="h-3 w-3" />
                                                    ) : (
                                                        <BookmarkOutlineIcon className="h-3 w-3" />
                                                    )}
                                                </button>
                                                <button
                                                    onClick={() => handleDeleteMemory(mem.memory_id)}
                                                    className="text-gray-400 hover:text-red-500"
                                                    title="Delete memory"
                                                >
                                                    <XMarkIcon className="h-3 w-3" />
                                                </button>
                                            </div>
                                        </div>
                                    );
                                })
                            )}
                        </div>
                    </div>

                    {/* Assets in Context Section */}
                    <div className="border-b border-gray-200 dark:border-gray-700">
                        <div className="px-4 py-3 bg-gray-100 dark:bg-gray-800">
                            <div className="flex items-center gap-2">
                                <DocumentIcon className="h-4 w-4 text-orange-600 dark:text-orange-400" />
                                <span className="text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase">
                                    Assets in Context
                                </span>
                            </div>
                        </div>
                        <div className="p-3 space-y-1">
                            {contextAssets.length === 0 ? (
                                <div className="text-center text-gray-400 dark:text-gray-500 text-xs py-2">
                                    No assets loaded
                                </div>
                            ) : (
                                contextAssets.map((asset) => (
                                    <div key={asset.asset_id} className="flex items-center gap-2 px-2 py-1.5 rounded bg-orange-50 dark:bg-orange-900/20 text-sm">
                                        <span className="flex-1 text-gray-700 dark:text-gray-300 text-xs truncate">{asset.name}</span>
                                        <button
                                            onClick={() => handleToggleAssetContext(asset.asset_id)}
                                            className="text-gray-400 hover:text-red-500"
                                            title="Remove from context"
                                        >
                                            <XMarkIcon className="h-3 w-3" />
                                        </button>
                                    </div>
                                ))
                            )}
                            {/* Show other assets that can be added */}
                            {otherAssets.length > 0 && (
                                <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-700">
                                    <div className="text-xs text-gray-500 mb-1">Available:</div>
                                    {otherAssets.slice(0, 3).map((asset) => (
                                        <button
                                            key={asset.asset_id}
                                            onClick={() => handleToggleAssetContext(asset.asset_id)}
                                            className="w-full text-left flex items-center gap-2 px-2 py-1 rounded text-xs text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"
                                        >
                                            <PlusIcon className="h-3 w-3" />
                                            {asset.name}
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Recent Tool Calls Section */}
                    {lastToolHistory && lastToolHistory.length > 0 && (
                        <div className="border-b border-gray-200 dark:border-gray-700">
                            <div className="px-4 py-3 bg-gray-100 dark:bg-gray-800">
                                <div className="flex items-center gap-2">
                                    <CpuChipIcon className="h-4 w-4 text-purple-600 dark:text-purple-400" />
                                    <span className="text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase">
                                        Recent Tool Calls
                                    </span>
                                </div>
                            </div>
                            <div className="p-3 space-y-2">
                                {lastToolHistory.slice(0, 5).map((tool, idx) => (
                                    <button
                                        key={idx}
                                        onClick={() => setSelectedToolHistory(lastToolHistory)}
                                        className="w-full text-left px-2 py-1.5 rounded text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-800 truncate"
                                    >
                                        {tool.tool_name}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
