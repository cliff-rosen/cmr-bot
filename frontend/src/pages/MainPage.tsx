import { useState, useRef, useEffect, useCallback } from 'react';
import { ChevronLeftIcon, ChevronRightIcon } from '@heroicons/react/24/solid';
import { useGeneralChat } from '../hooks/useGeneralChat';
import { InteractionType, ToolCall, GeneralChatMessage } from '../types/chat';
import { memoryApi, Memory, assetApi, Asset } from '../lib/api';
import {
    ConversationSidebar,
    ChatPanel,
    WorkspacePanel,
    ContextPanel,
    MemoryBrowserModal,
    AssetBrowserModal
} from '../components/panels';

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

    // Panel state
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);
    const [isContextPanelOpen, setIsContextPanelOpen] = useState(true);
    const [workspaceWidth, setWorkspaceWidth] = useState(400);
    const [isDragging, setIsDragging] = useState(false);

    // Modal state
    const [isMemoryModalOpen, setIsMemoryModalOpen] = useState(false);
    const [isAssetModalOpen, setIsAssetModalOpen] = useState(false);

    // Content state
    const [selectedToolHistory, setSelectedToolHistory] = useState<ToolCall[] | null>(null);
    const [memories, setMemories] = useState<Memory[]>([]);
    const [assets, setAssets] = useState<Asset[]>([]);

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
            const newWorkspaceWidth = containerRect.right - contextPanelW - 6 - e.clientX;
            const availableWidth = containerRect.width - sidebarW - 6 - contextPanelW - 6;

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

    // Conversation handlers
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

    // Chat handlers
    const handleSendMessage = (message: string) => {
        sendMessage(message, InteractionType.TEXT_INPUT);
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

    // Memory handlers
    const handleAddWorkingMemory = async (content: string) => {
        try {
            const newMem = await memoryApi.create({
                content,
                memory_type: 'working',
                source_conversation_id: conversationId || undefined
            });
            setMemories(prev => [newMem, ...prev]);
        } catch (err) {
            console.error('Failed to add memory:', err);
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

    const handleClearAllAssetsFromContext = async () => {
        try {
            const contextAssets = assets.filter(a => a.is_in_context);
            await Promise.all(contextAssets.map(a => assetApi.toggleContext(a.asset_id)));
            setAssets(prev => prev.map(a => ({ ...a, is_in_context: false })));
        } catch (err) {
            console.error('Failed to clear assets from context:', err);
        }
    };

    const handleSaveMessageAsAsset = async (message: GeneralChatMessage) => {
        try {
            const newAsset = await assetApi.create({
                name: `${message.role === 'user' ? 'User' : 'Assistant'} message - ${new Date(message.timestamp).toLocaleString()}`,
                asset_type: 'document',
                content: message.content,
                description: `Chat message from ${message.role}`,
                source_conversation_id: conversationId || undefined
            });
            setAssets(prev => [newAsset, ...prev]);
        } catch (err) {
            console.error('Failed to save message as asset:', err);
        }
    };

    // Workspace handlers
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

    return (
        <div ref={containerRef} className={`flex h-full ${isDragging ? 'select-none' : ''}`}>
            {/* Left Sidebar - Conversation List (Collapsible) */}
            <div
                className={`flex flex-col border-r border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 transition-all duration-300 ${
                    isSidebarOpen ? 'w-64' : 'w-0'
                } overflow-hidden`}
            >
                <ConversationSidebar
                    conversations={conversations}
                    currentConversationId={conversationId}
                    isLoading={isLoadingConversations}
                    onNewConversation={handleNewConversation}
                    onSelectConversation={handleSelectConversation}
                    onDeleteConversation={handleDeleteConversation}
                />
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
            <ChatPanel
                messages={messages}
                conversationId={conversationId}
                isLoading={isLoading}
                streamingText={streamingText}
                statusText={statusText}
                onSendMessage={handleSendMessage}
                onValueSelect={handleValueSelect}
                onActionClick={handleActionClick}
                onToolHistoryClick={setSelectedToolHistory}
                onSaveMessageAsAsset={handleSaveMessageAsAsset}
            />

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
                className="flex-shrink-0"
            >
                <WorkspacePanel
                    selectedToolHistory={selectedToolHistory}
                    onClose={() => setSelectedToolHistory(null)}
                    onSaveAsAsset={handleSaveToolOutputAsAsset}
                />
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
                <ContextPanel
                    memories={memories}
                    assets={assets}
                    lastToolHistory={lastToolHistory}
                    onAddWorkingMemory={handleAddWorkingMemory}
                    onToggleMemoryPinned={handleToggleMemoryPinned}
                    onToggleAssetContext={handleToggleAssetContext}
                    onClearAllAssetsFromContext={handleClearAllAssetsFromContext}
                    onToolHistoryClick={setSelectedToolHistory}
                    onExpandMemories={() => setIsMemoryModalOpen(true)}
                    onExpandAssets={() => setIsAssetModalOpen(true)}
                />
            </div>

            {/* Memory Browser Modal */}
            <MemoryBrowserModal
                isOpen={isMemoryModalOpen}
                memories={memories}
                onClose={() => setIsMemoryModalOpen(false)}
                onTogglePinned={handleToggleMemoryPinned}
                onDelete={handleDeleteMemory}
            />

            {/* Asset Browser Modal */}
            <AssetBrowserModal
                isOpen={isAssetModalOpen}
                assets={assets}
                onClose={() => setIsAssetModalOpen(false)}
                onToggleContext={handleToggleAssetContext}
                onDelete={handleDeleteAsset}
            />
        </div>
    );
}
