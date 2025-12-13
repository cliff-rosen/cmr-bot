import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeftIcon, ChevronRightIcon, PlusIcon } from '@heroicons/react/24/solid';
import { useGeneralChat } from '../hooks/useGeneralChat';
import { useProfile } from '../context/ProfileContext';
import { InteractionType, ToolCall, GeneralChatMessage, WorkspacePayload, WorkflowPlan, WorkflowStep, WorkflowStepDefinition } from '../types/chat';
import { memoryApi, Memory, assetApi, Asset, AssetUpdate, workflowApi, StepStatusUpdate, ToolCallRecord, ToolInfo, ToolProgressUpdate, agentApi } from '../lib/api';
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

    // Content state
    const [selectedToolHistory, setSelectedToolHistory] = useState<ToolCall[] | null>(null);
    const [activePayload, setActivePayload] = useState<WorkspacePayload | null>(null);

    // Workflow state
    const [activeWorkflow, setActiveWorkflow] = useState<WorkflowPlan | null>(null);

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
                const [tools, mems, assts] = await Promise.all([
                    workflowApi.getTools(),
                    memoryApi.list(),
                    assetApi.list()
                ]);
                setAvailableTools(tools);
                // Enable all tools by default
                setEnabledTools(new Set(tools.map(t => t.name)));
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
        setActiveWorkflow(null);
        setExecutingStep(null);
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

    // Step execution state
    const [executingStep, setExecutingStep] = useState<WorkflowStep | null>(null);
    const [stepStatus, setStepStatus] = useState<string>('');
    const [stepToolCalls, setStepToolCalls] = useState<ToolCallRecord[]>([]);
    const [currentToolProgress, setCurrentToolProgress] = useState<ToolProgressUpdate[]>([]);
    const [currentToolName, setCurrentToolName] = useState<string | null>(null);

    // Helper to build input data object from multiple sources
    // Returns structured input with content and optional data for each source
    const buildInputData = useCallback((
        workflow: WorkflowPlan,
        step: WorkflowStep
    ): Record<string, { content: string; data?: any }> => {
        const inputData: Record<string, { content: string; data?: any }> = {};
        // Handle both old (input_source) and new (input_sources) formats
        const sources = step.input_sources || [(step as any).input_source || 'user'];
        for (const source of sources) {
            if (source === 'user') {
                inputData['user_input'] = { content: workflow.initial_input };
            } else {
                const sourceStep = workflow.steps.find(s => s.step_number === source);
                inputData[`step_${source}`] = {
                    content: sourceStep?.wip_output?.content || '',
                    data: sourceStep?.wip_output?.data  // Include structured data if available
                };
            }
        }
        return inputData;
    }, []);

    // Helper to execute a step via dedicated step agent with streaming
    const executeStep = useCallback(async (
        workflow: WorkflowPlan,
        step: WorkflowStep
    ) => {
        setExecutingStep(step);
        setStepStatus('Starting...');
        setStepToolCalls([]);
        setCurrentToolProgress([]);
        setCurrentToolName(null);
        setActivePayload(null);

        // Build input data from all sources
        const inputData = buildInputData(workflow, step);

        try {
            let finalResult: StepStatusUpdate['result'] | null = null;

            for await (const update of workflowApi.executeStepStreaming({
                step_number: step.step_number,
                description: step.description,
                input_data: inputData,
                output_format: step.output_description,
                available_tools: step.method.tools
            })) {
                // Update status message
                setStepStatus(update.message);

                // Track tool start - reset progress for new tool
                if (update.status === 'tool_start' && update.tool_name) {
                    setCurrentToolName(update.tool_name);
                    setCurrentToolProgress([]);
                }

                // Track tool progress updates
                if (update.status === 'tool_progress' && update.tool_progress) {
                    setCurrentToolProgress(prev => [...prev, update.tool_progress!]);
                }

                // Track tool completion - add to tool calls list with accumulated progress
                if (update.status === 'tool_complete' && update.tool_name) {
                    setStepToolCalls(prev => [...prev, {
                        tool_name: update.tool_name!,
                        input: update.tool_input || {},
                        output: update.tool_output || ''
                    }]);
                    // Keep progress visible briefly, then clear
                    setCurrentToolName(null);
                }

                // Capture final result
                if (update.status === 'complete' || update.status === 'error') {
                    finalResult = update.result || null;
                }
            }

            setExecutingStep(null);
            setStepStatus('');

            if (finalResult?.success) {
                // Show the output as a WIP payload for user review
                setActivePayload({
                    type: 'wip',
                    title: `Step ${step.step_number}: ${step.description}`,
                    content: finalResult.output,
                    step_number: step.step_number,
                    content_type: finalResult.content_type,
                    data: finalResult.data  // Include structured data if available
                });
            } else {
                sendMessage(
                    `Step ${step.step_number} failed: ${finalResult?.error || 'Unknown error'}. Would you like me to retry?`,
                    InteractionType.TEXT_INPUT
                );
            }
        } catch (err) {
            console.error('Step execution error:', err);
            setExecutingStep(null);
            setStepStatus('');
            sendMessage(
                `Error executing step ${step.step_number}. Please try again.`,
                InteractionType.TEXT_INPUT
            );
        }
    }, [sendMessage, buildInputData]);

    // Workflow handlers
    const handleAcceptPlan = useCallback((payload: WorkspacePayload) => {
        if (payload.type !== 'plan' || !payload.steps) return;

        // Convert payload steps to workflow steps with status
        // Handle both old (input_source) and new (input_sources) formats from LLM
        const workflowSteps: WorkflowStep[] = payload.steps.map((step: WorkflowStepDefinition, idx: number) => ({
            step_number: idx + 1,
            description: step.description,
            input_description: step.input_description,
            input_sources: step.input_sources || [(step as any).input_source || 'user'],
            output_description: step.output_description,
            method: step.method,
            status: idx === 0 ? 'in_progress' : 'pending'
        }));

        // Create the workflow plan
        const workflow: WorkflowPlan = {
            id: `workflow_${Date.now()}`,
            title: payload.title,
            goal: payload.goal || '',
            initial_input: payload.initial_input || '',
            status: 'active',
            steps: workflowSteps,
            created_at: new Date().toISOString()
        };

        setActiveWorkflow(workflow);
        setActivePayload(null);

        // Execute the first step via dedicated step agent
        const firstStep = workflowSteps[0];
        executeStep(workflow, firstStep);
    }, [executeStep]);

    const handleRejectPlan = useCallback(() => {
        setActivePayload(null);
        sendMessage(
            'I\'d like to revise this plan. Let\'s discuss adjustments.',
            InteractionType.TEXT_INPUT
        );
    }, [sendMessage]);

    const handleAcceptWip = useCallback((payload: WorkspacePayload) => {
        if (!activeWorkflow || payload.step_number === undefined) return;

        const stepNumber = payload.step_number;
        const updatedSteps = activeWorkflow.steps.map(step => {
            if (step.step_number === stepNumber) {
                return {
                    ...step,
                    status: 'completed' as const,
                    wip_output: {
                        title: payload.title,
                        content: payload.content,
                        content_type: payload.content_type || 'document',
                        data: payload.data  // Include structured data if available
                    }
                };
            } else if (step.step_number === stepNumber + 1) {
                return { ...step, status: 'in_progress' as const };
            }
            return step;
        });

        const allCompleted = updatedSteps.every(s => s.status === 'completed');

        const updatedWorkflow = {
            ...activeWorkflow,
            steps: updatedSteps,
            status: allCompleted ? 'completed' as const : 'active' as const
        };
        setActiveWorkflow(updatedWorkflow);
        setActivePayload(null);

        if (allCompleted) {
            // Workflow complete - show final output for user review
            const lastStep = updatedSteps[updatedSteps.length - 1];
            if (lastStep.wip_output) {
                setActivePayload({
                    type: 'final',
                    title: lastStep.wip_output.title,
                    content: lastStep.wip_output.content,
                    content_type: lastStep.wip_output.content_type as 'document' | 'data' | 'code',
                    workflow_title: activeWorkflow.title,
                    steps_completed: updatedSteps.length
                });
            }
            // Keep workflow in state until user accepts/dismisses final output
        } else {
            // Execute next step via dedicated step agent
            const nextStep = updatedSteps.find(s => s.status === 'in_progress');
            if (nextStep) {
                // Execute with multi-source input gathering
                executeStep(updatedWorkflow, nextStep);
            }
        }
    }, [activeWorkflow, executeStep, handleSavePayloadAsAsset]);

    const handleEditWip = useCallback((payload: WorkspacePayload) => {
        // For now, just ask the main agent for feedback - TODO: could have step agent revise
        sendMessage(
            `I'd like to request changes to step ${payload.step_number} output. Here's my feedback:`,
            InteractionType.TEXT_INPUT
        );
    }, [sendMessage]);

    const handleRejectWip = useCallback(() => {
        if (!activeWorkflow) return;

        const currentStep = activeWorkflow.steps.find(s => s.status === 'in_progress');
        if (currentStep) {
            // Re-execute the step with multi-source input gathering
            executeStep(activeWorkflow, currentStep);
        }
        setActivePayload(null);
    }, [activeWorkflow, executeStep]);

    const handleAbandonWorkflow = useCallback(() => {
        setActiveWorkflow(null);
        setActivePayload(null);
    }, []);

    const handleAcceptFinal = useCallback((payload: WorkspacePayload) => {
        // Save the final output as an asset
        handleSavePayloadAsAsset({
            type: payload.content_type === 'code' ? 'code' : 'draft',
            title: payload.title,
            content: payload.content
        }, false);
        // Clear workflow and payload
        setActiveWorkflow(null);
        setActivePayload(null);
    }, [handleSavePayloadAsAsset]);

    const handleDismissFinal = useCallback(() => {
        // Just clear the workflow without saving
        setActiveWorkflow(null);
        setActivePayload(null);
    }, []);

    // Agent payload handlers
    const handleAcceptAgent = useCallback(async (payload: WorkspacePayload) => {
        if (!payload.agent_data) return;

        try {
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
            console.error('Failed to save agent:', error);
            sendMessage(`Failed to save agent: ${error instanceof Error ? error.message : 'Unknown error'}`, InteractionType.ACTION_EXECUTED, {
                action_identifier: 'agent_save_failed'
            });
        }

        // Clear the payload
        setActivePayload(null);
    }, [sendMessage]);

    const handleRejectAgent = useCallback(() => {
        setActivePayload(null);
    }, []);

    const handleViewStepOutput = useCallback((stepNumber: number) => {
        if (!activeWorkflow) return;
        const step = activeWorkflow.steps.find(s => s.step_number === stepNumber);
        if (step?.wip_output) {
            setActivePayload({
                type: step.wip_output.content_type === 'code' ? 'code' : 'draft',
                title: step.wip_output.title,
                content: step.wip_output.content
            });
        }
    }, [activeWorkflow]);

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
                onSendMessage={handleSendMessage}
                onCancel={cancelRequest}
                onClearChat={handleClearChat}
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
                    executingStep={executingStep}
                    stepStatus={stepStatus}
                    stepToolCalls={stepToolCalls}
                    currentToolName={currentToolName}
                    currentToolProgress={currentToolProgress}
                    onClose={handleWorkspaceClose}
                    onSaveAsAsset={handleSaveToolOutputAsAsset}
                    onSavePayloadAsAsset={handleSavePayloadAsAsset}
                    onPayloadEdit={handlePayloadEdit}
                    onAcceptPlan={handleAcceptPlan}
                    onRejectPlan={handleRejectPlan}
                    onAcceptWip={handleAcceptWip}
                    onEditWip={handleEditWip}
                    onRejectWip={handleRejectWip}
                    onAcceptFinal={handleAcceptFinal}
                    onDismissFinal={handleDismissFinal}
                    onAcceptAgent={handleAcceptAgent}
                    onRejectAgent={handleRejectAgent}
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
                    workflow={activeWorkflow}
                    onAddWorkingMemory={handleAddWorkingMemory}
                    onToggleMemoryPinned={handleToggleMemoryPinned}
                    onToggleAssetContext={handleToggleAssetContext}
                    onClearAllAssetsFromContext={handleClearAllAssetsFromContext}
                    onToggleTool={handleToggleTool}
                    onToggleProfile={handleToggleProfile}
                    onExpandMemories={() => setIsMemoryModalOpen(true)}
                    onExpandAssets={() => setIsAssetModalOpen(true)}
                    onEditProfile={handleEditProfile}
                    onAbandonWorkflow={handleAbandonWorkflow}
                    onViewStepOutput={handleViewStepOutput}
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
