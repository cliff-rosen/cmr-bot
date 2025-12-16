import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeftIcon, ChevronRightIcon, PlusIcon } from '@heroicons/react/24/solid';
import { useGeneralChat } from '../hooks/useGeneralChat';
import { useProfile } from '../context/ProfileContext';
import { InteractionType, ToolCall, GeneralChatMessage, WorkspacePayload, ResearchWorkflow } from '../types/chat';
import { memoryApi, Memory, assetApi, Asset, AssetUpdate, ToolInfo, toolsApi, agentApi } from '../lib/api';
import {
    ConversationSidebar,
    ChatPanel,
    WorkspacePanel,
    ContextPanel,
    MemoryBrowserModal,
    AssetBrowserModal,
    ToolBrowserModal,
    WorkflowSelectorModal
} from '../components/panels';
import {
    WorkflowInstanceState,
    WorkflowHandlers,
    WorkflowEvent,
    startWorkflowWithUI,
} from '../lib/workflows';
import { toast } from '../components/ui/use-toast';

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
    const { userProfile } = useProfile();

    // Available tools from backend
    const [availableTools, setAvailableTools] = useState<ToolInfo[]>([]);

    // Agent control state (defined first as hook depends on it)
    const [enabledTools, setEnabledTools] = useState<Set<string>>(new Set());
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
        cancelRequest,
        isLoading,
        streamingText,
        statusText,
        activeToolProgress,
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
    const [isToolModalOpen, setIsToolModalOpen] = useState(false);
    const [isWorkflowModalOpen, setIsWorkflowModalOpen] = useState(false);

    // Workflow engine state
    const [workflowInstance, setWorkflowInstance] = useState<WorkflowInstanceState | null>(null);
    const [workflowHandlers, setWorkflowHandlers] = useState<WorkflowHandlers | null>(null);
    const [isWorkflowProcessing, setIsWorkflowProcessing] = useState(false);

    // Workflow testing state - tracks the graph being tested so we can accept it later
    const [testingWorkflowGraph, setTestingWorkflowGraph] = useState<Record<string, any> | null>(null);
    const [currentWorkflowEvent, setCurrentWorkflowEvent] = useState<WorkflowEvent | null>(null);
    const [workflowTestError, setWorkflowTestError] = useState<string | null>(null);
    const [isWorkflowTestRunning, setIsWorkflowTestRunning] = useState(false);

    // Content state
    const [selectedToolHistory, setSelectedToolHistory] = useState<ToolCall[] | null>(null);
    const [selectedTool, setSelectedTool] = useState<ToolCall | null>(null);
    const [activePayload, setActivePayload] = useState<WorkspacePayload | null>(null);
    const [isSavingAsset, setIsSavingAsset] = useState(false);

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

    // Load tools, memories, and assets on mount (profile is loaded by ProfileContext)
    useEffect(() => {
        const loadData = async () => {
            try {
                const [toolsResponse, mems, assts] = await Promise.all([
                    toolsApi.listTools(),
                    memoryApi.list(),
                    assetApi.list()
                ]);
                setAvailableTools(toolsResponse.tools);
                // Enable all tools by default
                setEnabledTools(new Set(toolsResponse.tools.map(t => t.name)));
                setMemories(mems);
                setAssets(assts);
            } catch (err) {
                console.error('Failed to load data:', err);
            }
        };
        loadData();
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

    const handleClearChat = async () => {
        // Delete current conversation if one exists, then start fresh
        if (conversationId) {
            try {
                await deleteConversation(conversationId);
            } catch (err) {
                console.error('Failed to clear chat:', err);
            }
        } else {
            // No conversation yet, just clear via newConversation
            await newConversation();
        }
        // Clear workspace state too
        setActivePayload(null);
        setSelectedToolHistory(null);
        setSelectedTool(null);
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
        setIsSavingAsset(true);
        try {
            const assetName = `${message.role === 'user' ? 'User' : 'Assistant'} message - ${new Date(message.timestamp).toLocaleString()}`;
            const newAsset = await assetApi.create({
                name: assetName,
                asset_type: 'document',
                content: message.content,
                description: `Chat message from ${message.role}`,
                source_conversation_id: conversationId || undefined
            });
            setAssets(prev => [newAsset, ...prev]);
            toast({
                title: "Saved to Assets",
                description: `"${assetName}" has been saved.`,
            });
        } catch (err) {
            console.error('Failed to save message as asset:', err);
            toast({
                title: "Save Failed",
                description: "Could not save the message. Please try again.",
                variant: "destructive",
            });
        } finally {
            setIsSavingAsset(false);
        }
    };

    // Workspace handlers
    const handleSaveToolOutputAsAsset = async (toolCall: ToolCall) => {
        setIsSavingAsset(true);
        try {
            const content = typeof toolCall.output === 'string'
                ? toolCall.output
                : JSON.stringify(toolCall.output, null, 2);

            const assetName = `${toolCall.tool_name} result`;
            const newAsset = await assetApi.create({
                name: assetName,
                asset_type: 'data',
                content,
                description: `Output from ${toolCall.tool_name} tool call`,
                source_conversation_id: conversationId || undefined
            });
            setAssets(prev => [newAsset, ...prev]);
            toast({
                title: "Saved to Assets",
                description: `"${assetName}" has been saved.`,
            });
        } catch (err) {
            console.error('Failed to save as asset:', err);
            toast({
                title: "Save Failed",
                description: "Could not save the tool output. Please try again.",
                variant: "destructive",
            });
        } finally {
            setIsSavingAsset(false);
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
        setIsSavingAsset(true);
        try {
            let assetType: 'document' | 'code' | 'data' | 'file' | 'link' | 'list';
            let content: string;
            let description: string;

            if (payload.type === 'table' && payload.table_data) {
                // For table payloads, save the table data as JSON
                assetType = 'data';
                content = JSON.stringify(payload.table_data, null, 2);
                description = `Table data from ${payload.table_data.source || 'search'}: ${payload.content || ''}`;
            } else if (payload.type === 'research_result') {
                // For research results, save the synthesis as document
                assetType = 'document';
                content = payload.content || (payload as any).synthesis || '';
                description = `Research results: ${payload.title}`;
            } else if (payload.type === 'code') {
                assetType = 'code';
                content = payload.content;
                description = `${payload.type} created from chat`;
            } else {
                assetType = 'document';
                content = payload.content;
                description = `${payload.type} created from chat`;
            }

            const newAsset = await assetApi.create({
                name: payload.title,
                asset_type: assetType,
                content,
                description,
                source_conversation_id: conversationId || undefined
            });
            setAssets(prev => [newAsset, ...prev]);

            toast({
                title: "Saved to Assets",
                description: `"${payload.title}" has been saved.`,
            });

            if (andClose) {
                setActivePayload(null);
            }
        } catch (err) {
            console.error('Failed to save payload as asset:', err);
            toast({
                title: "Save Failed",
                description: "Could not save the asset. Please try again.",
                variant: "destructive",
            });
        } finally {
            setIsSavingAsset(false);
        }
    };

    const handleWorkspaceClose = () => {
        setSelectedToolHistory(null);
        setSelectedTool(null);
        setActivePayload(null);
    };

    // Handler for inline tool chip clicks
    const handleToolClick = (toolCall: ToolCall) => {
        setSelectedToolHistory(null);
        setActivePayload(null);
        setSelectedTool(toolCall);
    };

    // Payload accept handler (agents, workflows, etc.)
    const handleAcceptPayload = useCallback(async (payload: WorkspacePayload) => {
        try {
            // Handle workflow_graph payloads - execute the workflow
            if (payload.type === 'workflow_graph' && payload.workflow_graph_data) {
                const workflowGraph = payload.workflow_graph_data;

                // Start the workflow with the inline graph
                const { handlers } = await startWorkflowWithUI(
                    null, // No template ID
                    { query: 'Execute designed workflow' }, // Initial input
                    {
                        setWorkflowState: setWorkflowInstance,
                        setIsProcessing: setIsWorkflowProcessing,
                        setCurrentEvent: setCurrentWorkflowEvent,
                        conversationId: conversationId ?? undefined,
                        showNotification: (message, type) => {
                            toast({
                                title: type === 'error' ? 'Error' : 'Success',
                                description: message,
                                variant: type === 'error' ? 'destructive' : 'default',
                            });
                        }
                    },
                    workflowGraph as Record<string, any> // Pass the inline graph
                );

                setWorkflowHandlers(handlers);

                // Clear the payload (workflow view will take over)
                setActivePayload(null);
                return;
            }

            // Handle agent payloads
            if (!payload.agent_data) return;

            if (payload.type === 'agent_create') {
                // Create new agent
                await agentApi.create({
                    name: payload.agent_data.name,
                    description: payload.agent_data.description,
                    instructions: payload.agent_data.instructions,
                    lifecycle: payload.agent_data.lifecycle,
                    tools: payload.agent_data.tools,
                    schedule: payload.agent_data.schedule,
                    monitor_interval_minutes: payload.agent_data.monitor_interval_minutes
                });
                // Notify user
                sendMessage(`Agent "${payload.agent_data.name}" has been created successfully.`, InteractionType.ACTION_EXECUTED, {
                    action_identifier: 'agent_created',
                    action_data: { name: payload.agent_data.name }
                });
            } else if (payload.type === 'agent_update' && payload.agent_data.agent_id) {
                // Update existing agent
                await agentApi.update(payload.agent_data.agent_id, {
                    name: payload.agent_data.name,
                    description: payload.agent_data.description,
                    instructions: payload.agent_data.instructions,
                    tools: payload.agent_data.tools,
                    schedule: payload.agent_data.schedule,
                    monitor_interval_minutes: payload.agent_data.monitor_interval_minutes
                });
                // Notify user
                sendMessage(`Agent "${payload.agent_data.name}" has been updated successfully.`, InteractionType.ACTION_EXECUTED, {
                    action_identifier: 'agent_updated',
                    action_data: { agent_id: payload.agent_data.agent_id, name: payload.agent_data.name }
                });
            }
        } catch (error) {
            console.error('Failed to process payload:', error);
            // Error already shown via showNotification in startWorkflowWithUI for workflows
            // Reset processing state in case it wasn't reset
            setIsWorkflowProcessing(false);
        }

        // Clear the payload
        setActivePayload(null);
    }, [sendMessage, conversationId, toast]);

    const handleRejectAgent = useCallback(() => {
        setActivePayload(null);
    }, []);

    // Workflow testing handler
    const handleTestWorkflow = useCallback(async (workflow: Record<string, any>, inputs: Record<string, any>) => {
        // Clear any previous error and mark as running
        setWorkflowTestError(null);
        setIsWorkflowTestRunning(true);

        try {
            // Save the workflow graph for later acceptance
            setTestingWorkflowGraph(workflow);

            // Start the workflow with the user's test inputs
            const { handlers } = await startWorkflowWithUI(
                null, // No template ID - using inline graph
                inputs, // User-provided test inputs
                {
                    setWorkflowState: setWorkflowInstance,
                    setIsProcessing: setIsWorkflowProcessing,
                    setCurrentEvent: setCurrentWorkflowEvent,
                    conversationId: conversationId ?? undefined,
                    showNotification: (message, type) => {
                        // Don't show toast for errors - we'll show them inline
                        if (type !== 'error') {
                            toast({
                                title: 'Success',
                                description: message,
                            });
                        }
                    }
                },
                workflow // Pass the inline graph
            );

            setWorkflowHandlers(handlers);
            setIsWorkflowTestRunning(false);

            // Clear the design payload (workflow execution view will take over)
            setActivePayload(null);
        } catch (error) {
            console.error('Failed to test workflow:', error);
            // Extract error message and display inline
            const errorMessage = error instanceof Error ? error.message : 'Failed to start workflow';
            setWorkflowTestError(errorMessage);
            setIsWorkflowTestRunning(false);
            // Reset processing state in case it wasn't reset
            setIsWorkflowProcessing(false);
            // Keep the activePayload so the workflow graph stays visible with the error
        }
    }, [conversationId, toast]);

    // Clear workflow test error
    const handleClearWorkflowTestError = useCallback(() => {
        setWorkflowTestError(null);
    }, []);

    // Accept workflow template handler (stub - saves to local state only for now)
    const handleAcceptWorkflowTemplate = useCallback(async (workflow: Record<string, any>) => {
        try {
            // TODO: Call backend API to save workflow template
            // For now, just log and show success message
            console.log('[STUB] Saving workflow template:', workflow);

            // Show success message with instructions
            const workflowName = workflow.name || 'Untitled Workflow';
            toast({
                title: 'Workflow Saved!',
                description: `"${workflowName}" has been saved as a template. You can run it anytime from the Workflows menu in the context panel.`,
                duration: 8000,
            });

            // Clear the testing state and workflow instance
            setTestingWorkflowGraph(null);
            setWorkflowInstance(null);
            setWorkflowHandlers(null);
            setIsWorkflowProcessing(false);
            setCurrentWorkflowEvent(null);
        } catch (error) {
            console.error('Failed to save workflow template:', error);
            toast({
                title: 'Error',
                description: `Failed to save workflow: ${error instanceof Error ? error.message : 'Unknown error'}`,
                variant: 'destructive',
            });
        }
    }, [toast]);

    // Research workflow handlers
    const handleUpdateResearchWorkflow = useCallback((workflow: ResearchWorkflow) => {
        // Update the activePayload with the new workflow state
        setActivePayload(prev => {
            if (!prev || prev.type !== 'research') return prev;
            return {
                ...prev,
                research_data: workflow
            };
        });
    }, []);

    const handleResearchProceed = useCallback(() => {
        if (!activePayload || activePayload.type !== 'research' || !activePayload.research_data) return;
        const workflow = activePayload.research_data;

        // Determine the appropriate action based on current stage
        let action = 'approve_question';
        if (workflow.stage === 'checklist') {
            action = 'approve_checklist';
        }

        // Include the full workflow state so LLM can pass it to the tool
        const workflowStateJson = JSON.stringify(workflow);
        sendMessage(
            `Please call research_workflow with action="${action}" and workflow_state=${workflowStateJson}`,
            InteractionType.ACTION_EXECUTED,
            {
                action_identifier: 'research_proceed',
                action_data: { workflow_id: workflow.id, current_stage: workflow.stage }
            }
        );
    }, [activePayload, sendMessage]);

    const handleResearchRunRetrieval = useCallback(() => {
        if (!activePayload || activePayload.type !== 'research' || !activePayload.research_data) return;
        const workflow = activePayload.research_data;

        // Include the full workflow state so LLM can pass it to the tool
        const workflowStateJson = JSON.stringify(workflow);
        sendMessage(
            `Please call research_workflow with action="run_iteration" and workflow_state=${workflowStateJson}`,
            InteractionType.ACTION_EXECUTED,
            {
                action_identifier: 'research_run_retrieval',
                action_data: { workflow_id: workflow.id }
            }
        );
    }, [activePayload, sendMessage]);

    const handleResearchPauseRetrieval = useCallback(() => {
        if (!activePayload || activePayload.type !== 'research' || !activePayload.research_data) return;
        const workflow = activePayload.research_data;

        // Update retrieval state to paused
        handleUpdateResearchWorkflow({
            ...workflow,
            retrieval: workflow.retrieval ? {
                ...workflow.retrieval,
                status: 'paused'
            } : undefined
        });
    }, [activePayload, handleUpdateResearchWorkflow]);

    const handleResearchCompile = useCallback(() => {
        if (!activePayload || activePayload.type !== 'research' || !activePayload.research_data) return;
        const workflow = activePayload.research_data;

        // Include the full workflow state so LLM can pass it to the tool
        const workflowStateJson = JSON.stringify(workflow);
        sendMessage(
            `Please call research_workflow with action="compile" and workflow_state=${workflowStateJson}`,
            InteractionType.ACTION_EXECUTED,
            {
                action_identifier: 'research_compile',
                action_data: { workflow_id: workflow.id }
            }
        );
    }, [activePayload, sendMessage]);

    const handleResearchComplete = useCallback(() => {
        if (!activePayload || activePayload.type !== 'research' || !activePayload.research_data) return;
        const workflow = activePayload.research_data;

        // Save final answer as an asset if present
        if (workflow.final?.answer) {
            handleSavePayloadAsAsset({
                type: 'draft',
                title: `Research: ${workflow.question?.refined || workflow.original_query}`,
                content: workflow.final.answer
            }, false);
        }

        // Clear the research workflow
        setActivePayload(null);
    }, [activePayload, handleSavePayloadAsAsset]);

    // Workflow engine handlers
    const handleStartWorkflow = useCallback(async (workflowId: string, initialInput: Record<string, any>) => {
        try {
            const { handlers } = await startWorkflowWithUI(workflowId, initialInput, {
                setWorkflowState: setWorkflowInstance,
                setIsProcessing: setIsWorkflowProcessing,
                setCurrentEvent: setCurrentWorkflowEvent,
                showNotification: (message, type) => {
                    console.log(`[${type}] ${message}`);
                    // TODO: Add toast notification
                },
                conversationId: conversationId || undefined,
            });
            setWorkflowHandlers(handlers);
            // Clear other workspace content
            setActivePayload(null);
            setSelectedToolHistory(null);
        } catch (err) {
            console.error('Failed to start workflow:', err);
            setIsWorkflowProcessing(false);
            setCurrentWorkflowEvent(null);
        }
    }, [conversationId]);

    const handleCloseWorkflowInstance = useCallback(() => {
        setWorkflowInstance(null);
        setWorkflowHandlers(null);
        setIsWorkflowProcessing(false);
        setCurrentWorkflowEvent(null);
    }, []);

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
                    confirmDeleteId={confirmDeleteConvId}
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
                activeToolProgress={activeToolProgress}
                isSavingAsset={isSavingAsset}
                onSendMessage={handleSendMessage}
                onCancel={cancelRequest}
                onClearChat={handleClearChat}
                onValueSelect={handleValueSelect}
                onActionClick={handleActionClick}
                onToolHistoryClick={(history) => {
                    setActivePayload(null);
                    setSelectedTool(null);
                    setSelectedToolHistory(history);
                }}
                onToolClick={handleToolClick}
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
                    selectedTool={selectedTool}
                    activePayload={activePayload}
                    onClose={handleWorkspaceClose}
                    onSaveAsAsset={handleSaveToolOutputAsAsset}
                    onSavePayloadAsAsset={handleSavePayloadAsAsset}
                    isSavingAsset={isSavingAsset}
                    onPayloadEdit={handlePayloadEdit}
                    onAcceptAgent={handleAcceptPayload}
                    onRejectAgent={handleRejectAgent}
                    onTestWorkflow={handleTestWorkflow}
                    onUpdateResearchWorkflow={handleUpdateResearchWorkflow}
                    onResearchProceed={handleResearchProceed}
                    onResearchRunRetrieval={handleResearchRunRetrieval}
                    onResearchPauseRetrieval={handleResearchPauseRetrieval}
                    onResearchCompile={handleResearchCompile}
                    onResearchComplete={handleResearchComplete}
                    workflowInstance={workflowInstance}
                    workflowHandlers={workflowHandlers}
                    isWorkflowProcessing={isWorkflowProcessing}
                    currentWorkflowEvent={currentWorkflowEvent}
                    onCloseWorkflowInstance={handleCloseWorkflowInstance}
                    testingWorkflowGraph={testingWorkflowGraph}
                    onAcceptWorkflowTemplate={handleAcceptWorkflowTemplate}
                    workflowTestError={workflowTestError}
                    onClearWorkflowTestError={handleClearWorkflowTestError}
                    isWorkflowTestRunning={isWorkflowTestRunning}
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
                    availableTools={availableTools}
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
                    onExpandTools={() => setIsToolModalOpen(true)}
                    onEditProfile={handleEditProfile}
                    onOpenWorkflows={() => setIsWorkflowModalOpen(true)}
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

            {/* Tool Browser Modal */}
            <ToolBrowserModal
                isOpen={isToolModalOpen}
                onClose={() => setIsToolModalOpen(false)}
            />

            {/* Workflow Selector Modal */}
            <WorkflowSelectorModal
                isOpen={isWorkflowModalOpen}
                onClose={() => setIsWorkflowModalOpen(false)}
                onStartWorkflow={handleStartWorkflow}
            />
        </div>
    );
}
