import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeftIcon, ChevronRightIcon, PlusIcon } from '@heroicons/react/24/solid';
import { useGeneralChat } from '../hooks/useGeneralChat';
import { useProfile } from '../context/ProfileContext';
import { InteractionType, ToolCall, GeneralChatMessage, WorkspacePayload } from '../types/chat';
import { memoryApi, Memory, assetApi, Asset, AssetUpdate, profileApi } from '../lib/api';
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
    const navigate = useNavigate();
    const { userProfile, setUserProfile } = useProfile();

    // Agent control state (defined first as hook depends on it)
    const [enabledTools, setEnabledTools] = useState<Set<string>>(
        new Set(['web_search', 'fetch_webpage', 'save_memory', 'search_memory'])
    );
    const [includeProfile, setIncludeProfile] = useState(true);

    // Convert Set to array for the hook (memoized to avoid recreating on every render)
    const enabledToolsArray = useMemo(() => Array.from(enabledTools), [enabledTools]);

    // Memories and assets state (defined before useGeneralChat so callback can use setters)
    const [memories, setMemories] = useState<Memory[]>([]);
    const [assets, setAssets] = useState<Asset[]>([]);

    // Callback to refresh data when tools modify memories
    const handleToolCallsComplete = useCallback(async (toolNames: string[]) => {
        const memoryTools = ['save_memory', 'delete_memory', 'update_memory'];
        const shouldRefreshMemories = toolNames.some(t => memoryTools.includes(t));

        if (shouldRefreshMemories) {
            try {
                const mems = await memoryApi.list();
                setMemories(mems);
            } catch (err) {
                console.error('Failed to refresh memories:', err);
            }
        }
    }, []);

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
    } = useGeneralChat({
        enabledTools: enabledToolsArray,
        includeProfile,
        onToolCallsComplete: handleToolCallsComplete
    });

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
    const [activePayload, setActivePayload] = useState<WorkspacePayload | null>(null);

    const containerRef = useRef<HTMLDivElement>(null);

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

    // Load memories, assets, and profile on mount
    useEffect(() => {
        const loadData = async () => {
            try {
                const [mems, assts, prof] = await Promise.all([
                    memoryApi.list(),
                    assetApi.list(),
                    profileApi.get()
                ]);
                setMemories(mems);
                setAssets(assts);
                setUserProfile(prof);
            } catch (err) {
                console.error('Failed to load data:', err);
            }
        };
        loadData();
    }, [setUserProfile]);

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

    const [confirmDeleteConvId, setConfirmDeleteConvId] = useState<number | null>(null);

    const handleDeleteConversation = async (convId: number, e: React.MouseEvent) => {
        e.stopPropagation();
        if (confirmDeleteConvId === convId) {
            // Second click - actually delete
            try {
                await deleteConversation(convId);
            } catch (err) {
                console.error('Failed to delete conversation:', err);
            }
            setConfirmDeleteConvId(null);
        } else {
            // First click - set confirm state
            setConfirmDeleteConvId(convId);
            // Auto-reset after 3 seconds
            setTimeout(() => setConfirmDeleteConvId(null), 3000);
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

    const handleUpdateAsset = async (assetId: number, updates: AssetUpdate) => {
        try {
            const updated = await assetApi.update(assetId, updates);
            setAssets(prev => prev.map(a =>
                a.asset_id === assetId ? { ...a, ...updated } : a
            ));
        } catch (err) {
            console.error('Failed to update asset:', err);
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

    // Agent control handlers
    const handleToggleTool = (toolId: string) => {
        setEnabledTools(prev => {
            const next = new Set(prev);
            if (next.has(toolId)) {
                next.delete(toolId);
            } else {
                next.add(toolId);
            }
            return next;
        });
    };

    const handleToggleProfile = () => {
        setIncludeProfile(prev => !prev);
    };

    const handleEditProfile = () => {
        navigate('/profile');
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

    // Payload handlers
    const handlePayloadClick = (payload: WorkspacePayload) => {
        setSelectedToolHistory(null); // Clear tool history when viewing a payload
        setActivePayload(payload);
    };

    const handlePayloadEdit = (updatedPayload: WorkspacePayload) => {
        setActivePayload(updatedPayload);
    };

    const handleSavePayloadAsAsset = async (payload: WorkspacePayload, andClose?: boolean) => {
        try {
            const assetType = payload.type === 'code' ? 'code' : 'document';
            const newAsset = await assetApi.create({
                name: payload.title,
                asset_type: assetType,
                content: payload.content,
                description: `${payload.type} created from chat`,
                source_conversation_id: conversationId || undefined
            });
            setAssets(prev => [newAsset, ...prev]);
            if (andClose) {
                setActivePayload(null);
            }
        } catch (err) {
            console.error('Failed to save payload as asset:', err);
        }
    };

    const handleWorkspaceClose = () => {
        setSelectedToolHistory(null);
        setActivePayload(null);
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

            {/* Sidebar Toggle + New Chat Button */}
            <div className="flex-shrink-0 flex flex-col bg-gray-100 dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700">
                {/* New Chat Button (visible when sidebar collapsed) */}
                {!isSidebarOpen && (
                    <button
                        onClick={handleNewConversation}
                        className="w-8 h-8 m-1 flex items-center justify-center bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors"
                        title="New conversation"
                    >
                        <PlusIcon className="h-4 w-4" />
                    </button>
                )}
                {/* Toggle Button */}
                <button
                    onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                    className="flex-1 w-8 flex items-center justify-center hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                    title={isSidebarOpen ? 'Hide conversations' : 'Show conversations'}
                >
                    {isSidebarOpen ? (
                        <ChevronLeftIcon className="h-4 w-4 text-gray-500" />
                    ) : (
                        <ChevronRightIcon className="h-4 w-4 text-gray-500" />
                    )}
                </button>
            </div>

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
                onToolHistoryClick={(history) => {
                    setActivePayload(null);
                    setSelectedToolHistory(history);
                }}
                onSaveMessageAsAsset={handleSaveMessageAsAsset}
                onPayloadClick={handlePayloadClick}
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
                    activePayload={activePayload}
                    onClose={handleWorkspaceClose}
                    onSaveAsAsset={handleSaveToolOutputAsAsset}
                    onSavePayloadAsAsset={handleSavePayloadAsAsset}
                    onPayloadEdit={handlePayloadEdit}
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
                    profile={userProfile}
                    enabledTools={enabledTools}
                    includeProfile={includeProfile}
                    onAddWorkingMemory={handleAddWorkingMemory}
                    onToggleMemoryPinned={handleToggleMemoryPinned}
                    onToggleAssetContext={handleToggleAssetContext}
                    onClearAllAssetsFromContext={handleClearAllAssetsFromContext}
                    onToggleTool={handleToggleTool}
                    onToggleProfile={handleToggleProfile}
                    onExpandMemories={() => setIsMemoryModalOpen(true)}
                    onExpandAssets={() => setIsAssetModalOpen(true)}
                    onEditProfile={handleEditProfile}
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
                onUpdateAsset={handleUpdateAsset}
            />
        </div>
    );
}
