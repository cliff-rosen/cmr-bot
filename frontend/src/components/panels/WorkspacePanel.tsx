import { XMarkIcon } from '@heroicons/react/24/solid';
import { ToolCall, WorkspacePayload, WorkflowStep } from '../../types/chat';
import { ToolCallRecord, ToolProgressUpdate } from '../../lib/api';
import {
    StepExecutingView,
    PlanPayloadView,
    WipPayloadView,
    FinalPayloadView,
    StandardPayloadView,
    ToolHistoryView,
    AgentPayloadView,
    TablePayloadView,
    payloadTypeConfig
} from './workspace';

interface WorkspacePanelProps {
    selectedToolHistory: ToolCall[] | null;
    activePayload: WorkspacePayload | null;
    executingStep: WorkflowStep | null;
    stepStatus: string;
    stepToolCalls: ToolCallRecord[];
    currentToolName: string | null;
    currentToolProgress: ToolProgressUpdate[];
    onClose: () => void;
    onSaveAsAsset: (toolCall: ToolCall) => void;
    onSavePayloadAsAsset: (payload: WorkspacePayload, andClose?: boolean) => void;
    onPayloadEdit: (payload: WorkspacePayload) => void;
    // Workflow callbacks
    onAcceptPlan?: (payload: WorkspacePayload) => void;
    onRejectPlan?: () => void;
    onAcceptWip?: (payload: WorkspacePayload) => void;
    onEditWip?: (payload: WorkspacePayload) => void;
    onRejectWip?: () => void;
    onAcceptFinal?: (payload: WorkspacePayload) => void;
    onDismissFinal?: () => void;
    // Agent callbacks
    onAcceptAgent?: (payload: WorkspacePayload) => void;
    onRejectAgent?: () => void;
}

export default function WorkspacePanel({
    selectedToolHistory,
    activePayload,
    executingStep,
    stepStatus,
    stepToolCalls,
    currentToolName,
    currentToolProgress,
    onClose,
    onSaveAsAsset,
    onSavePayloadAsAsset,
    onPayloadEdit,
    onAcceptPlan,
    onRejectPlan,
    onAcceptWip,
    onEditWip,
    onRejectWip,
    onAcceptFinal,
    onDismissFinal,
    onAcceptAgent,
    onRejectAgent
}: WorkspacePanelProps) {
    const config = activePayload ? payloadTypeConfig[activePayload.type] : null;

    // Determine what to show
    const showExecuting = executingStep !== null;
    const showPayload = activePayload && !selectedToolHistory && !showExecuting;
    const showToolHistory = selectedToolHistory && selectedToolHistory.length > 0 && !showExecuting;
    const showEmpty = !showPayload && !showToolHistory && !showExecuting;

    return (
        <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-950">
            {/* Workspace Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                <div>
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                        {showExecuting
                            ? `Executing Step ${executingStep.step_number}`
                            : showToolHistory
                                ? 'Tool History'
                                : showPayload
                                    ? activePayload.title
                                    : 'Workspace'}
                    </h2>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                        {showExecuting
                            ? 'Please wait...'
                            : showToolHistory
                                ? `${selectedToolHistory.length} tool call(s)`
                                : showPayload
                                    ? config?.label
                                    : 'Collaborative space'}
                    </p>
                </div>
                {(showToolHistory || showPayload) && (
                    <button
                        onClick={onClose}
                        className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                    >
                        <XMarkIcon className="h-5 w-5" />
                    </button>
                )}
            </div>

            {/* Workspace Content */}
            <div className={`flex-1 ${showExecuting || (showPayload && (activePayload?.type === 'plan' || activePayload?.type === 'wip' || activePayload?.type === 'final' || activePayload?.type === 'agent_create' || activePayload?.type === 'agent_update' || activePayload?.type === 'table')) ? 'overflow-hidden flex flex-col' : 'overflow-y-auto p-4'}`}>
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

                {/* Plan Payload View */}
                {showPayload && activePayload.type === 'plan' && (
                    <PlanPayloadView
                        payload={activePayload}
                        onAccept={onAcceptPlan || (() => {})}
                        onReject={onRejectPlan || (() => {})}
                    />
                )}

                {/* WIP Payload View */}
                {showPayload && activePayload.type === 'wip' && (
                    <WipPayloadView
                        payload={activePayload}
                        onAccept={onAcceptWip || (() => {})}
                        onEdit={onEditWip || (() => {})}
                        onReject={onRejectWip || (() => {})}
                        onPayloadEdit={onPayloadEdit}
                    />
                )}

                {/* Final Workflow Output View */}
                {showPayload && activePayload.type === 'final' && (
                    <FinalPayloadView
                        payload={activePayload}
                        onAccept={onAcceptFinal || (() => {})}
                        onDismiss={onDismissFinal || (() => {})}
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
                    />
                )}

                {/* Standard Payload View (draft, summary, data, code) */}
                {showPayload && activePayload.type !== 'plan' && activePayload.type !== 'wip' && activePayload.type !== 'final' && activePayload.type !== 'agent_create' && activePayload.type !== 'agent_update' && activePayload.type !== 'table' && (
                    <StandardPayloadView
                        payload={activePayload}
                        onSaveAsAsset={onSavePayloadAsAsset}
                        onPayloadEdit={onPayloadEdit}
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
