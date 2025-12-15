/**
 * WorkflowExecutionView
 *
 * Generic component for displaying workflow execution in the workspace.
 * Shows steps, current progress, and checkpoint interactions.
 */

import { useState, useMemo } from 'react';
import {
    CheckCircleIcon,
    PlayIcon,
    ClockIcon,
    XCircleIcon,
    ExclamationTriangleIcon,
    ChevronDownIcon,
    ChevronRightIcon,
    PencilIcon,
    ArrowPathIcon,
} from '@heroicons/react/24/solid';
import { WorkflowInstanceState, WorkflowHandlers } from '../../../lib/workflows';
import { MarkdownRenderer } from '../../common/MarkdownRenderer';

interface WorkflowExecutionViewProps {
    instanceState: WorkflowInstanceState;
    handlers: WorkflowHandlers;
}

// Status badge component
function StatusBadge({ status }: { status: string }) {
    const config = {
        pending: { icon: ClockIcon, color: 'text-gray-500 dark:text-gray-400', bg: 'bg-gray-100 dark:bg-gray-800' },
        running: { icon: ArrowPathIcon, color: 'text-blue-600 dark:text-blue-400', bg: 'bg-gray-100 dark:bg-gray-800', animate: true },
        waiting: { icon: PlayIcon, color: 'text-amber-600 dark:text-amber-400', bg: 'bg-gray-100 dark:bg-gray-800' },
        completed: { icon: CheckCircleIcon, color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-gray-100 dark:bg-gray-800' },
        failed: { icon: XCircleIcon, color: 'text-red-600 dark:text-red-400', bg: 'bg-gray-100 dark:bg-gray-800' },
        cancelled: { icon: XCircleIcon, color: 'text-gray-500 dark:text-gray-400', bg: 'bg-gray-100 dark:bg-gray-800' },
        paused: { icon: ClockIcon, color: 'text-orange-600 dark:text-orange-400', bg: 'bg-gray-100 dark:bg-gray-800' },
    }[status] || { icon: ClockIcon, color: 'text-gray-500 dark:text-gray-400', bg: 'bg-gray-100 dark:bg-gray-800' };

    const Icon = config.icon;

    return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${config.bg}`}>
            <Icon className={`h-3.5 w-3.5 ${config.color} ${config.animate ? 'animate-spin' : ''}`} />
            <span className={config.color}>{status}</span>
        </span>
    );
}

// Step item component
function StepItem({
    step,
    stepState,
    isCurrent,
    isExpanded,
    onToggle,
    stepData,
}: {
    step: { id: string; name: string; description: string };
    stepState?: { status: string; execution_count: number; error?: string };
    isCurrent: boolean;
    isExpanded: boolean;
    onToggle: () => void;
    stepData?: any;
}) {
    const status = stepState?.status || 'pending';
    const hasData = stepData !== undefined;

    const statusIcon = {
        pending: ClockIcon,
        running: ArrowPathIcon,
        completed: CheckCircleIcon,
        failed: XCircleIcon,
        skipped: XCircleIcon,
    }[status] || ClockIcon;

    const StatusIcon = statusIcon;

    const statusColor = {
        pending: 'text-gray-400 dark:text-gray-500',
        running: 'text-blue-600 dark:text-blue-400',
        completed: 'text-emerald-600 dark:text-emerald-400',
        failed: 'text-red-600 dark:text-red-400',
        skipped: 'text-gray-400 dark:text-gray-500',
    }[status] || 'text-gray-400 dark:text-gray-500';

    return (
        <div
            className={`border rounded-lg transition-colors ${
                isCurrent
                    ? 'border-blue-300 dark:border-blue-600/50 bg-blue-50/50 dark:bg-blue-900/10'
                    : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900'
            }`}
        >
            <button
                onClick={onToggle}
                className="w-full flex items-center gap-3 p-3 text-left"
                disabled={!hasData}
            >
                <StatusIcon
                    className={`h-5 w-5 flex-shrink-0 ${statusColor} ${
                        status === 'running' ? 'animate-spin' : ''
                    }`}
                />
                <div className="flex-1 min-w-0">
                    <div className="font-medium text-gray-900 dark:text-white">{step.name}</div>
                    <div className="text-sm text-gray-500 dark:text-gray-400 truncate">
                        {step.description}
                    </div>
                </div>
                {hasData && (
                    isExpanded ? (
                        <ChevronDownIcon className="h-5 w-5 text-gray-400" />
                    ) : (
                        <ChevronRightIcon className="h-5 w-5 text-gray-400" />
                    )
                )}
            </button>

            {isExpanded && stepData && (
                <div className="px-3 pb-3 border-t border-gray-200 dark:border-gray-700 mt-2 pt-3">
                    <div className="prose dark:prose-invert prose-sm max-w-none">
                        {typeof stepData === 'string' ? (
                            <MarkdownRenderer content={stepData} />
                        ) : stepData.display_content ? (
                            <MarkdownRenderer content={stepData.display_content} />
                        ) : (
                            <pre className="text-xs overflow-x-auto text-gray-900 dark:text-gray-100">
                                {JSON.stringify(stepData, null, 2)}
                            </pre>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

// Checkpoint panel component
function CheckpointPanel({
    checkpoint,
    stepData,
    handlers,
}: {
    checkpoint: {
        title: string;
        description: string;
        allowed_actions: string[];
        editable_fields: string[];
    };
    stepData: any;
    handlers: WorkflowHandlers;
}) {
    const [isEditing, setIsEditing] = useState(false);
    const [editValues, setEditValues] = useState<Record<string, string>>({});

    const handleEdit = () => {
        // Initialize edit values from step data
        const initial: Record<string, string> = {};
        for (const field of checkpoint.editable_fields) {
            initial[field] = typeof stepData?.[field] === 'string' ? stepData[field] : '';
        }
        setEditValues(initial);
        setIsEditing(true);
    };

    const handleSaveEdit = () => {
        handlers.onEdit(editValues);
        setIsEditing(false);
    };

    const handleCancelEdit = () => {
        setIsEditing(false);
        setEditValues({});
    };

    return (
        <div className="bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-xl p-4 space-y-4">
            <div>
                <h3 className="font-semibold text-gray-900 dark:text-white">
                    {checkpoint.title}
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                    {checkpoint.description}
                </p>
            </div>

            {/* Current output display */}
            {stepData && !isEditing && (
                <div className="bg-white dark:bg-gray-900 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                    <div className="prose dark:prose-invert prose-sm max-w-none">
                        {typeof stepData === 'string' ? (
                            <MarkdownRenderer content={stepData} />
                        ) : stepData.display_content ? (
                            <MarkdownRenderer content={stepData.display_content} />
                        ) : stepData.refined_question ? (
                            <div className="text-gray-900 dark:text-gray-100">
                                <p><strong>Question:</strong> {stepData.refined_question}</p>
                                {stepData.scope && <p className="mt-2"><strong>Scope:</strong> {stepData.scope}</p>}
                            </div>
                        ) : (
                            <pre className="text-xs overflow-x-auto text-gray-900 dark:text-gray-100">
                                {JSON.stringify(stepData, null, 2)}
                            </pre>
                        )}
                    </div>
                </div>
            )}

            {/* Edit mode */}
            {isEditing && (
                <div className="space-y-3">
                    {checkpoint.editable_fields.map((field) => (
                        <div key={field}>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1 capitalize">
                                {field.replace(/_/g, ' ')}
                            </label>
                            <textarea
                                value={editValues[field] || ''}
                                onChange={(e) =>
                                    setEditValues((prev) => ({ ...prev, [field]: e.target.value }))
                                }
                                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white resize-none"
                                rows={3}
                            />
                        </div>
                    ))}
                    <div className="flex gap-2">
                        <button
                            onClick={handleSaveEdit}
                            className="px-4 py-2 bg-gray-900 dark:bg-white text-white dark:text-gray-900 rounded-lg hover:bg-gray-800 dark:hover:bg-gray-100 transition-colors"
                        >
                            Save Changes
                        </button>
                        <button
                            onClick={handleCancelEdit}
                            className="px-4 py-2 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors"
                        >
                            Cancel
                        </button>
                    </div>
                </div>
            )}

            {/* Action buttons */}
            {!isEditing && (
                <div className="flex flex-wrap gap-2 pt-2 border-t border-gray-200 dark:border-gray-700">
                    {checkpoint.allowed_actions.includes('approve') && (
                        <button
                            onClick={() => handlers.onApprove()}
                            className="flex items-center gap-2 px-4 py-2 bg-gray-900 dark:bg-white text-white dark:text-gray-900 rounded-lg hover:bg-gray-800 dark:hover:bg-gray-100 transition-colors"
                        >
                            <CheckCircleIcon className="h-4 w-4" />
                            Continue
                        </button>
                    )}
                    {checkpoint.allowed_actions.includes('edit') &&
                        checkpoint.editable_fields.length > 0 && (
                            <button
                                onClick={handleEdit}
                                className="flex items-center gap-2 px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                            >
                                <PencilIcon className="h-4 w-4" />
                                Edit
                            </button>
                        )}
                    {checkpoint.allowed_actions.includes('reject') && (
                        <button
                            onClick={() => handlers.onReject()}
                            className="flex items-center gap-2 px-4 py-2 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
                        >
                            <XCircleIcon className="h-4 w-4" />
                            Cancel
                        </button>
                    )}
                </div>
            )}
        </div>
    );
}

export default function WorkflowExecutionView({
    instanceState,
    handlers,
}: WorkflowExecutionViewProps) {
    const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set());

    // Toggle step expansion
    const toggleStep = (stepId: string) => {
        setExpandedSteps((prev) => {
            const next = new Set(prev);
            if (next.has(stepId)) next.delete(stepId);
            else next.add(stepId);
            return next;
        });
    };

    // Get node info - we only have node IDs from the state, not full node definitions
    // In a real implementation, we'd fetch the workflow template
    const nodes = useMemo(() => {
        // Build node list from node_states and step_data
        const nodeIds = new Set([
            ...Object.keys(instanceState.node_states || {}),
            ...Object.keys(instanceState.step_data),
        ]);

        return Array.from(nodeIds).map((id) => ({
            id,
            name: id.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
            description: '',
        }));
    }, [instanceState.node_states, instanceState.step_data]);

    // Determine if we're at a checkpoint
    const isAtCheckpoint = instanceState.status === 'waiting';
    const currentNodeId = instanceState.current_node?.id;

    // Mock checkpoint config - in real implementation, this comes from the node definition
    const checkpointConfig = isAtCheckpoint
        ? {
              title: instanceState.current_node?.name || 'Review',
              description: 'Please review and take action',
              allowed_actions: ['approve', 'edit', 'reject'] as string[],
              editable_fields: ['refined_question', 'scope'] as string[],
          }
        : null;

    // Get the data for the previous step (to show at checkpoint)
    const checkpointStepData = useMemo(() => {
        if (!isAtCheckpoint || !currentNodeId) return null;

        // Map checkpoint nodes to their preceding execute nodes
        // This is based on the research workflow graph structure
        const checkpointToDataMap: Record<string, string> = {
            'question_checkpoint': 'formulate_question',
            'checklist_checkpoint': 'build_checklist',
            'retrieval_checkpoint': 'run_retrieval',
            'final_checkpoint': 'compile_final',
        };

        // If we have a mapping for this checkpoint, use it
        const dataNodeId = checkpointToDataMap[currentNodeId];
        if (dataNodeId && instanceState.step_data[dataNodeId]) {
            return instanceState.step_data[dataNodeId];
        }

        // Fallback: find the most recently completed node's data
        const nodeStates = instanceState.node_states || {};
        const completedNodes = Object.entries(nodeStates)
            .filter(([_, state]) => state.status === 'completed')
            .map(([id]) => id);

        if (completedNodes.length === 0) {
            // Last fallback: just get the last key in step_data
            const stepDataKeys = Object.keys(instanceState.step_data);
            if (stepDataKeys.length === 0) return null;
            return instanceState.step_data[stepDataKeys[stepDataKeys.length - 1]];
        }

        // Return data from the last completed node
        const lastCompleted = completedNodes[completedNodes.length - 1];
        return instanceState.step_data[lastCompleted];
    }, [isAtCheckpoint, currentNodeId, instanceState.step_data, instanceState.node_states]);

    return (
        <div className="h-full flex flex-col p-4">
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                        Workflow Execution
                    </h2>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                        {instanceState.workflow_id}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <StatusBadge status={instanceState.status} />
                    {instanceState.status === 'running' && (
                        <button
                            onClick={() => handlers.onPause()}
                            className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
                        >
                            Pause
                        </button>
                    )}
                    {instanceState.status !== 'completed' && instanceState.status !== 'cancelled' && (
                        <button
                            onClick={() => handlers.onCancel()}
                            className="px-3 py-1.5 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
                        >
                            Cancel
                        </button>
                    )}
                </div>
            </div>

            {/* Checkpoint panel (shown when waiting) */}
            {isAtCheckpoint && checkpointConfig && (
                <div className="mb-6">
                    <CheckpointPanel
                        checkpoint={checkpointConfig}
                        stepData={checkpointStepData}
                        handlers={handlers}
                    />
                </div>
            )}

            {/* Nodes list */}
            <div className="flex-1 overflow-y-auto space-y-3">
                {nodes.map((node) => (
                    <StepItem
                        key={node.id}
                        step={node}
                        stepState={instanceState.node_states?.[node.id]}
                        isCurrent={node.id === currentNodeId}
                        isExpanded={expandedSteps.has(node.id)}
                        onToggle={() => toggleStep(node.id)}
                        stepData={instanceState.step_data[node.id]}
                    />
                ))}
            </div>

            {/* Completed state */}
            {instanceState.status === 'completed' && (
                <div className="mt-4 p-4 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl">
                    <div className="flex items-center gap-2">
                        <CheckCircleIcon className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                        <span className="font-medium text-gray-900 dark:text-white">Workflow completed</span>
                    </div>
                </div>
            )}

            {/* Failed state */}
            {instanceState.status === 'failed' && (
                <div className="mt-4 p-4 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl">
                    <div className="flex items-center gap-2">
                        <ExclamationTriangleIcon className="h-5 w-5 text-red-600 dark:text-red-400" />
                        <span className="font-medium text-gray-900 dark:text-white">Workflow failed</span>
                    </div>
                </div>
            )}
        </div>
    );
}
