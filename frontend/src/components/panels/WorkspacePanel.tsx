import { XMarkIcon } from '@heroicons/react/24/solid';
import { ToolCall, WorkspacePayload, ResearchWorkflow } from '../../types/chat';
import { WorkflowInstanceState, WorkflowHandlers, WorkflowEvent } from '../../lib/workflows';
import {
    ToolHistoryView,
    ToolResultView,
    payloadTypeConfig,
    getWorkspaceMode,
    getPayloadView,
    getWorkflowView,
} from './workspace';

interface WorkspacePanelProps {
    selectedToolHistory: ToolCall[] | null;
    selectedTool: ToolCall | null;
    activePayload: WorkspacePayload | null;
    onClose: () => void;
    onSaveAsAsset: (toolCall: ToolCall) => void;
    onSavePayloadAsAsset: (payload: WorkspacePayload, andClose?: boolean) => void;
    isSavingAsset?: boolean;
    onPayloadEdit: (payload: WorkspacePayload) => void;
    // Agent callbacks
    onAcceptAgent?: (payload: WorkspacePayload) => void;
    onRejectAgent?: () => void;
    // Research workflow callbacks (for LLM-orchestrated research)
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
    onClose,
    onSaveAsAsset,
    onSavePayloadAsAsset,
    isSavingAsset = false,
    onPayloadEdit,
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
    isWorkflowProcessing = false,
    currentWorkflowEvent,
    onCloseWorkflowInstance: _onCloseWorkflowInstance
}: WorkspacePanelProps) {
    void _onCloseWorkflowInstance; // Reserved for close button in workflow view

    // Determine workspace mode using single function
    const mode = getWorkspaceMode({
        workflowInstance: workflowInstance || null,
        workflowHandlers: workflowHandlers || null,
        isWorkflowProcessing,
        currentWorkflowEvent: currentWorkflowEvent || null,
        selectedTool,
        selectedToolHistory,
        activePayload,
    });

    // Render based on mode
    switch (mode.mode) {
        case 'workflow_loading':
            return <WorkflowLoadingView mode={mode} />;

        case 'workflow': {
            const WorkflowView = getWorkflowView(mode.instance.workflow_id);
            return (
                <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-950">
                    <WorkflowView
                        instance={mode.instance}
                        handlers={mode.handlers}
                        isProcessing={mode.isProcessing}
                        currentEvent={mode.currentEvent}
                        onSaveAsAsset={onSavePayloadAsAsset}
                        isSavingAsset={isSavingAsset}
                    />
                </div>
            );
        }

        case 'tool':
            return (
                <WorkspaceContainer
                    title="Tool Result"
                    subtitle={mode.tool.tool_name.replace(/_/g, ' ')}
                    onClose={onClose}
                >
                    <ToolResultView
                        toolCall={mode.tool}
                        onSaveAsAsset={onSaveAsAsset}
                    />
                </WorkspaceContainer>
            );

        case 'tool_history':
            return (
                <WorkspaceContainer
                    title="Tool History"
                    subtitle={`${mode.history.length} tool call(s)`}
                    onClose={onClose}
                >
                    <ToolHistoryView
                        toolCalls={mode.history}
                        onSaveAsAsset={onSaveAsAsset}
                    />
                </WorkspaceContainer>
            );

        case 'payload': {
            const PayloadView = getPayloadView(mode.payload.type);
            const config = payloadTypeConfig[mode.payload.type];
            const needsFlexLayout = ['agent_create', 'agent_update', 'table'].includes(mode.payload.type);

            return (
                <WorkspaceContainer
                    title={mode.payload.title}
                    subtitle={config?.label}
                    onClose={onClose}
                    flexContent={needsFlexLayout}
                >
                    <PayloadView
                        payload={mode.payload}
                        onSaveAsAsset={onSavePayloadAsAsset}
                        isSaving={isSavingAsset}
                        onPayloadEdit={onPayloadEdit}
                        onAccept={onAcceptAgent}
                        onReject={onRejectAgent}
                        // Research workflow callbacks
                        onUpdateWorkflow={onUpdateResearchWorkflow}
                        onProceed={onResearchProceed}
                        onRunRetrieval={onResearchRunRetrieval}
                        onPauseRetrieval={onResearchPauseRetrieval}
                        onCompile={onResearchCompile}
                        onComplete={onResearchComplete}
                    />
                </WorkspaceContainer>
            );
        }

        case 'empty':
            return <EmptyWorkspace />;
    }
}

// =============================================================================
// Helper Components
// =============================================================================

function WorkflowLoadingView({ mode }: { mode: { handlers?: WorkflowHandlers | null; currentEvent?: WorkflowEvent | null } }) {
    const stepName = mode.currentEvent?.node_name || 'Initializing';
    const eventType = mode.currentEvent?.event_type;
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
                    {mode.handlers && (
                        <button
                            onClick={() => mode.handlers!.onCancel()}
                            className="mt-4 px-4 py-2 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                        >
                            Cancel
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
}

interface WorkspaceContainerProps {
    title: string;
    subtitle?: string;
    onClose: () => void;
    flexContent?: boolean;
    children: React.ReactNode;
}

function WorkspaceContainer({ title, subtitle, onClose, flexContent = false, children }: WorkspaceContainerProps) {
    return (
        <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-950">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                <div>
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                        {title}
                    </h2>
                    {subtitle && (
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                            {subtitle}
                        </p>
                    )}
                </div>
                <button
                    onClick={onClose}
                    className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                >
                    <XMarkIcon className="h-5 w-5" />
                </button>
            </div>

            {/* Content */}
            <div className={`flex-1 ${flexContent ? 'overflow-hidden flex flex-col' : 'overflow-y-auto p-4'}`}>
                {children}
            </div>
        </div>
    );
}

function EmptyWorkspace() {
    return (
        <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-950">
            <div className="flex-1 flex items-center justify-center p-4">
                <div className="text-center text-gray-400 dark:text-gray-500">
                    <div className="text-6xl mb-4">Workspace</div>
                    <h3 className="text-xl font-medium mb-2">Collaborative Space</h3>
                    <p className="text-sm max-w-md">
                        When the AI generates drafts, summaries, or other structured content,
                        it will appear here. You can edit, save, or iterate on the content.
                    </p>
                </div>
            </div>
        </div>
    );
}
