import { XMarkIcon } from '@heroicons/react/24/solid';
import { ToolCall, WorkspacePayload, WorkflowStep, WorkflowPlan, ResearchWorkflow } from '../../types/chat';
import { ToolCallRecord, ToolProgressUpdate } from '../../lib/api';
import { WorkflowInstanceState, WorkflowHandlers, WorkflowEvent } from '../../lib/workflows';
import {
    StepExecutingView,
    StandardPayloadView,
    ToolHistoryView,
    ToolResultView,
    AgentPayloadView,
    TablePayloadView,
    WorkflowPipelineView,
    ResearchWorkflowView,
    ResearchResultView,
    WorkflowExecutionView,
    payloadTypeConfig
} from './workspace';

interface WorkspacePanelProps {
    selectedToolHistory: ToolCall[] | null;
    selectedTool: ToolCall | null;
    activePayload: WorkspacePayload | null;
    executingStep: WorkflowStep | null;
    stepStatus: string;
    stepToolCalls: ToolCallRecord[];
    currentToolName: string | null;
    currentToolProgress: ToolProgressUpdate[];
    onClose: () => void;
    onSaveAsAsset: (toolCall: ToolCall) => void;
    onSavePayloadAsAsset: (payload: WorkspacePayload, andClose?: boolean) => void;
    isSavingAsset?: boolean;
    onPayloadEdit: (payload: WorkspacePayload) => void;
    // Workflow state and callbacks
    activeWorkflow?: WorkflowPlan | null;
    onAcceptPlan?: (payload: WorkspacePayload) => void;
    onRejectPlan?: () => void;
    onAcceptWip?: (payload: WorkspacePayload) => void;
    onEditWip?: (payload: WorkspacePayload) => void;
    onRejectWip?: () => void;
    onAcceptFinal?: (payload: WorkspacePayload) => void;
    onDismissFinal?: () => void;
    onAbandonWorkflow?: () => void;
    // Agent callbacks
    onAcceptAgent?: (payload: WorkspacePayload) => void;
    onRejectAgent?: () => void;
    // Research workflow callbacks
    onUpdateResearchWorkflow?: (workflow: ResearchWorkflow) => void;
    onResearchProceed?: () => void;
    onResearchRunRetrieval?: () => void;
    onResearchPauseRetrieval?: () => void;
    onResearchCompile?: () => void;
    onResearchComplete?: () => void;
    // Workflow engine props
    workflowInstance?: WorkflowInstanceState | null;
    workflowHandlers?: WorkflowHandlers | null;
    isWorkflowProcessing?: boolean;
    currentWorkflowEvent?: WorkflowEvent | null;
    onCloseWorkflowInstance?: () => void;
}

export default function WorkspacePanel({
    selectedToolHistory,
    selectedTool,
    activePayload,
    executingStep,
    stepStatus,
    stepToolCalls,
    currentToolName,
    currentToolProgress,
    onClose,
    onSaveAsAsset,
    onSavePayloadAsAsset,
    isSavingAsset = false,
    onPayloadEdit,
    activeWorkflow,
    onAcceptPlan,
    onRejectPlan,
    onAcceptWip,
    onEditWip,
    onRejectWip,
    onAcceptFinal,
    onDismissFinal,
    onAbandonWorkflow,
    onAcceptAgent,
    onRejectAgent,
    onUpdateResearchWorkflow,
    onResearchProceed,
    onResearchRunRetrieval,
    onResearchPauseRetrieval,
    onResearchCompile,
    onResearchComplete,
    workflowInstance,
    workflowHandlers,
    isWorkflowProcessing,
    currentWorkflowEvent,
    onCloseWorkflowInstance: _onCloseWorkflowInstance
}: WorkspacePanelProps) {
    void _onCloseWorkflowInstance; // Reserved for close button in workflow view
    const config = activePayload ? payloadTypeConfig[activePayload.type] : null;

    // Check if we're in workflow engine mode
    const isWorkflowEngineMode = workflowInstance && workflowHandlers;

    // Check if we're in workflow mode (active workflow OR proposed plan)
    const isWorkflowMode = activeWorkflow || (activePayload?.type === 'plan');
    const isWorkflowRelatedPayload = activePayload?.type === 'plan' || activePayload?.type === 'wip' || activePayload?.type === 'final';
    const isResearchWorkflow = activePayload?.type === 'research';
    const isResearchResult = activePayload?.type === 'research_result';

    // Determine what to show
    const showWorkflowEngine = isWorkflowEngineMode && !selectedToolHistory && !selectedTool;
    const showWorkflowPipeline = !showWorkflowEngine && (isWorkflowMode || (isWorkflowRelatedPayload && !selectedToolHistory && !selectedTool));
    const showResearchWorkflow = !showWorkflowEngine && isResearchWorkflow && !selectedToolHistory && !selectedTool;
    const showResearchResult = !showWorkflowEngine && isResearchResult && !selectedToolHistory && !selectedTool;
    const showExecuting = !showWorkflowEngine && executingStep !== null && !showWorkflowPipeline && !showResearchWorkflow && !showResearchResult;
    const showPayload = !showWorkflowEngine && activePayload && !selectedToolHistory && !selectedTool && !showExecuting && !showWorkflowPipeline && !showResearchWorkflow && !showResearchResult;
    const showToolResult = !showWorkflowEngine && selectedTool && !showExecuting && !showWorkflowPipeline && !showResearchWorkflow && !showResearchResult;
    const showToolHistory = !showWorkflowEngine && selectedToolHistory && selectedToolHistory.length > 0 && !selectedTool && !showExecuting && !showWorkflowPipeline && !showResearchWorkflow && !showResearchResult;
    const showEmpty = !showPayload && !showToolHistory && !showToolResult && !showExecuting && !showWorkflowPipeline && !showResearchWorkflow && !showResearchResult && !showWorkflowEngine;

    // Show initial loading state when workflow is starting but no instance yet
    if (isWorkflowProcessing && !workflowInstance) {
        const stepName = currentWorkflowEvent?.node_name || 'Initializing';
        const eventType = currentWorkflowEvent?.event_type;
        const statusText = eventType === 'step_start' ? `Running: ${stepName}` :
                          eventType === 'step_complete' ? `Completed: ${stepName}` :
                          stepName;

        return (
            <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-950">
                <div className="flex-1 flex items-center justify-center">
                    <div className="text-center">
                        <div className="inline-flex items-center justify-center w-12 h-12 bg-blue-100 dark:bg-blue-900/30 rounded-full mb-4">
                            <svg className="w-6 h-6 text-blue-600 dark:text-blue-400 animate-spin" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                            </svg>
                        </div>
                        <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-1">Starting Workflow</h3>
                        <p className="text-sm text-gray-500 dark:text-gray-400">{statusText}</p>
                    </div>
                </div>
            </div>
        );
    }

    // For workflow engine, render with WorkflowExecutionView
    if (showWorkflowEngine && workflowInstance && workflowHandlers) {
        return (
            <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-950">
                <WorkflowExecutionView
                    instanceState={workflowInstance}
                    handlers={workflowHandlers}
                    isProcessing={isWorkflowProcessing}
                    currentEvent={currentWorkflowEvent}
                />
            </div>
        );
    }

    // For research workflow, render with the ResearchWorkflowView
    if (showResearchWorkflow && activePayload) {
        return (
            <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-950">
                <ResearchWorkflowView
                    payload={activePayload}
                    onUpdateWorkflow={onUpdateResearchWorkflow || (() => {})}
                    onProceedToNextStage={onResearchProceed || (() => {})}
                    onRunRetrieval={onResearchRunRetrieval || (() => {})}
                    onPauseRetrieval={onResearchPauseRetrieval || (() => {})}
                    onCompileFinal={onResearchCompile || (() => {})}
                    onComplete={onResearchComplete || (() => {})}
                />
            </div>
        );
    }

    // For research result (from deep_research tool), render with ResearchResultView
    if (showResearchResult && activePayload) {
        return (
            <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-950">
                <ResearchResultView
                    payload={activePayload}
                    onSaveAsAsset={onSavePayloadAsAsset}
                    isSaving={isSavingAsset}
                />
            </div>
        );
    }

    // For workflow pipeline, render without the standard header (it has its own)
    if (showWorkflowPipeline) {
        return (
            <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-950 p-4">
                <WorkflowPipelineView
                    // Proposed plan props
                    proposedPlan={activePayload?.type === 'plan' ? activePayload : undefined}
                    onAcceptPlan={onAcceptPlan}
                    onRejectPlan={onRejectPlan}
                    // Active workflow props
                    workflow={activeWorkflow}
                    executingStep={executingStep}
                    stepStatus={stepStatus}
                    stepToolCalls={stepToolCalls}
                    currentToolName={currentToolName}
                    currentToolProgress={currentToolProgress}
                    // Step output review props
                    stepOutput={activePayload?.type === 'wip' || activePayload?.type === 'final' ? activePayload : null}
                    onAcceptStep={onAcceptWip}
                    onEditStep={onEditWip}
                    onRejectStep={onRejectWip}
                    onPayloadEdit={onPayloadEdit}
                    // Final workflow props
                    onAcceptFinal={onAcceptFinal}
                    onDismissFinal={onDismissFinal}
                    // Abandon
                    onAbandon={onAbandonWorkflow}
                />
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-950">
            {/* Workspace Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                <div>
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                        {showExecuting
                            ? `Executing Step ${executingStep.step_number}`
                            : showToolResult
                                ? 'Tool Result'
                                : showToolHistory
                                    ? 'Tool History'
                                    : showPayload
                                        ? activePayload.title
                                        : 'Workspace'}
                    </h2>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                        {showExecuting
                            ? 'Please wait...'
                            : showToolResult
                                ? selectedTool.tool_name.replace(/_/g, ' ')
                                : showToolHistory
                                    ? `${selectedToolHistory.length} tool call(s)`
                                    : showPayload
                                        ? config?.label
                                        : 'Collaborative space'}
                    </p>
                </div>
                {(showToolResult || showToolHistory || showPayload) && (
                    <button
                        onClick={onClose}
                        className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                    >
                        <XMarkIcon className="h-5 w-5" />
                    </button>
                )}
            </div>

            {/* Workspace Content */}
            <div className={`flex-1 ${showExecuting || (showPayload && (activePayload?.type === 'agent_create' || activePayload?.type === 'agent_update' || activePayload?.type === 'table')) ? 'overflow-hidden flex flex-col' : 'overflow-y-auto p-4'}`}>
                {/* Step Executing View */}
                {showExecuting && (
                    <StepExecutingView
                        executingStep={executingStep}
                        stepStatus={stepStatus}
                        stepToolCalls={stepToolCalls}
                        currentToolName={currentToolName}
                        currentToolProgress={currentToolProgress}
                    />
                )}

                {/* Agent Payload View (create/update) */}
                {showPayload && (activePayload.type === 'agent_create' || activePayload.type === 'agent_update') && (
                    <AgentPayloadView
                        payload={activePayload}
                        onAccept={onAcceptAgent || (() => {})}
                        onReject={onRejectAgent || (() => {})}
                    />
                )}

                {/* Table Payload View (TABILIZER) */}
                {showPayload && activePayload.type === 'table' && (
                    <TablePayloadView
                        payload={activePayload}
                        onSaveAsAsset={onSavePayloadAsAsset}
                        isSaving={isSavingAsset}
                    />
                )}

                {/* Standard Payload View (draft, summary, data, code) */}
                {showPayload && activePayload.type !== 'plan' && activePayload.type !== 'wip' && activePayload.type !== 'final' && activePayload.type !== 'agent_create' && activePayload.type !== 'agent_update' && activePayload.type !== 'table' && (
                    <StandardPayloadView
                        payload={activePayload}
                        onSaveAsAsset={onSavePayloadAsAsset}
                        isSaving={isSavingAsset}
                        onPayloadEdit={onPayloadEdit}
                    />
                )}

                {/* Single Tool Result View */}
                {showToolResult && selectedTool && (
                    <ToolResultView
                        toolCall={selectedTool}
                        onSaveAsAsset={onSaveAsAsset}
                    />
                )}

                {/* Tool History View */}
                {showToolHistory && (
                    <ToolHistoryView
                        toolCalls={selectedToolHistory}
                        onSaveAsAsset={onSaveAsAsset}
                    />
                )}

                {/* Empty State */}
                {showEmpty && (
                    <div className="flex items-center justify-center h-full">
                        <div className="text-center text-gray-400 dark:text-gray-500">
                            <div className="text-6xl mb-4">Workspace</div>
                            <h3 className="text-xl font-medium mb-2">Collaborative Space</h3>
                            <p className="text-sm max-w-md">
                                When the AI generates drafts, summaries, or other structured content,
                                it will appear here. You can edit, save, or iterate on the content.
                            </p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
