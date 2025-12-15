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
import { WorkflowInstanceState, WorkflowHandlers, WorkflowEvent } from '../../../lib/workflows';
import { MarkdownRenderer } from '../../common/MarkdownRenderer';

interface WorkflowExecutionViewProps {
    instance: WorkflowInstanceState;
    handlers: WorkflowHandlers;
    isProcessing?: boolean;
    currentEvent?: WorkflowEvent | null;
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
    isLoading,
    currentEvent,
}: {
    checkpoint: {
        title: string;
        description: string;
        allowed_actions: string[];
        editable_fields: string[];
    };
    stepData: any;
    handlers: WorkflowHandlers;
    isLoading?: boolean;
    currentEvent?: WorkflowEvent | null;
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

    // Render checklist items with findings
    const renderChecklistItems = (items: any[]) => (
        <div className="space-y-3">
            {items.map((item: any) => (
                <div
                    key={item.id}
                    className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg"
                >
                    <div className="flex items-start gap-3">
                        <span className={`w-2 h-2 mt-2 rounded-full flex-shrink-0 ${
                            item.status === 'complete' ? 'bg-emerald-500' :
                            item.status === 'partial' ? 'bg-amber-500' : 'bg-gray-300 dark:bg-gray-600'
                        }`} />
                        <div className="flex-1 min-w-0">
                            <div className="font-medium text-gray-900 dark:text-white text-sm">
                                {item.description}
                            </div>
                            <div className="flex items-center gap-2 mt-1">
                                <span className={`text-xs px-1.5 py-0.5 rounded ${
                                    item.priority === 'high' ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400' :
                                    item.priority === 'medium' ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400' :
                                    'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
                                }`}>
                                    {item.priority}
                                </span>
                                {item.findings && item.findings.length > 0 && (
                                    <span className="text-xs text-gray-500 dark:text-gray-400">
                                        {item.findings.length} finding{item.findings.length !== 1 ? 's' : ''}
                                    </span>
                                )}
                            </div>
                        </div>
                    </div>
                    {/* Show findings if present */}
                    {item.findings && item.findings.length > 0 && (
                        <div className="mt-2 ml-5 space-y-1.5">
                            {item.findings.slice(0, 5).map((finding: any, idx: number) => (
                                <div key={idx} className="text-xs bg-white dark:bg-gray-900 p-2 rounded border border-gray-200 dark:border-gray-700">
                                    <p className="text-gray-700 dark:text-gray-300">{finding.content}</p>
                                    {finding.source && (
                                        <a
                                            href={finding.source}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="text-blue-500 hover:underline mt-1 block truncate"
                                        >
                                            {finding.source}
                                        </a>
                                    )}
                                </div>
                            ))}
                            {item.findings.length > 5 && (
                                <p className="text-xs text-gray-500 dark:text-gray-400 italic">
                                    +{item.findings.length - 5} more findings
                                </p>
                            )}
                        </div>
                    )}
                </div>
            ))}
        </div>
    );

    // Render data based on its structure
    const renderStepData = () => {
        if (!stepData) return null;

        if (typeof stepData === 'string') {
            return <MarkdownRenderer content={stepData} />;
        }

        // Checklist items with retrieval findings (from run_retrieval step)
        if (stepData.items && Array.isArray(stepData.items)) {
            const completedCount = stepData.items.filter((i: any) => i.status === 'complete').length;
            const partialCount = stepData.items.filter((i: any) => i.status === 'partial').length;

            return (
                <div className="text-gray-900 dark:text-gray-100">
                    <p className="mb-3"><strong>Question:</strong> {stepData.refined_question}</p>

                    {/* Show retrieval stats if present */}
                    {(stepData.current_iteration || stepData.sources) && (
                        <div className="mb-3 p-2 bg-blue-50 dark:bg-blue-900/20 rounded text-sm">
                            {stepData.current_iteration && (
                                <span className="mr-4">Iterations: {stepData.current_iteration}</span>
                            )}
                            {stepData.sources && (
                                <span>Sources consulted: {stepData.sources.length}</span>
                            )}
                        </div>
                    )}

                    <p className="font-medium text-sm text-gray-700 dark:text-gray-300 mb-2">
                        Checklist Progress: {completedCount} complete, {partialCount} partial, {stepData.items.length - completedCount - partialCount} pending
                    </p>
                    {renderChecklistItems(stepData.items)}
                </div>
            );
        }

        // Display content (markdown)
        if (stepData.display_content) {
            return <MarkdownRenderer content={stepData.display_content} />;
        }

        // Question/scope data
        if (stepData.refined_question && !stepData.items) {
            return (
                <div className="text-gray-900 dark:text-gray-100">
                    <p><strong>Question:</strong> {stepData.refined_question}</p>
                    {stepData.scope && <p className="mt-2"><strong>Scope:</strong> {stepData.scope}</p>}
                    {stepData.key_terms && stepData.key_terms.length > 0 && (
                        <div className="mt-2">
                            <strong>Key Terms:</strong>
                            <div className="flex flex-wrap gap-1 mt-1">
                                {stepData.key_terms.map((term: string, i: number) => (
                                    <span key={i} className="px-2 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-sm">
                                        {term}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            );
        }

        // Final answer
        if (stepData.answer) {
            return <MarkdownRenderer content={stepData.answer} />;
        }

        // Vendor list (from vendor_finder workflow)
        if (stepData.vendors && Array.isArray(stepData.vendors)) {
            return (
                <div className="text-gray-900 dark:text-gray-100">
                    <p className="font-medium text-sm text-gray-700 dark:text-gray-300 mb-3">
                        {stepData.vendors.length} Vendor{stepData.vendors.length !== 1 ? 's' : ''} Found
                    </p>
                    <div className="space-y-3">
                        {stepData.vendors.map((vendor: any) => (
                            <div
                                key={vendor.id || vendor.name}
                                className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg"
                            >
                                <div className="flex items-start justify-between gap-2">
                                    <div className="flex-1 min-w-0">
                                        <div className="font-medium text-gray-900 dark:text-white">
                                            {vendor.name}
                                            {vendor.overall_rating && (
                                                <span className="ml-2 text-sm text-amber-600 dark:text-amber-400">
                                                    {vendor.overall_rating}/5
                                                </span>
                                            )}
                                            {vendor.overall_sentiment && (
                                                <span className="ml-1">
                                                    {vendor.overall_sentiment === 'positive' ? '👍' :
                                                     vendor.overall_sentiment === 'negative' ? '👎' :
                                                     vendor.overall_sentiment === 'mixed' ? '😐' : ''}
                                                </span>
                                            )}
                                        </div>
                                        {vendor.description && (
                                            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                                                {vendor.description}
                                            </p>
                                        )}
                                        {vendor.location && (
                                            <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
                                                📍 {vendor.location}
                                            </p>
                                        )}
                                        {vendor.website && (
                                            <a
                                                href={vendor.website}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="text-xs text-blue-500 hover:underline mt-1 block truncate"
                                            >
                                                {vendor.website}
                                            </a>
                                        )}
                                        {vendor.services && vendor.services.length > 0 && (
                                            <div className="flex flex-wrap gap-1 mt-2">
                                                {vendor.services.slice(0, 4).map((service: string, idx: number) => (
                                                    <span key={idx} className="text-xs px-1.5 py-0.5 bg-gray-200 dark:bg-gray-700 rounded">
                                                        {service}
                                                    </span>
                                                ))}
                                                {vendor.services.length > 4 && (
                                                    <span className="text-xs text-gray-500">+{vendor.services.length - 4}</span>
                                                )}
                                            </div>
                                        )}
                                        {vendor.price_tier && (
                                            <span className="text-xs text-green-600 dark:text-green-400 mt-1 block">
                                                {vendor.price_tier}
                                            </span>
                                        )}
                                        {/* Review summaries */}
                                        {vendor.reviews && vendor.reviews.length > 0 && (
                                            <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-700">
                                                <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Reviews:</p>
                                                <div className="space-y-1">
                                                    {vendor.reviews.map((review: any, idx: number) => (
                                                        <div key={idx} className="text-xs">
                                                            <span className="font-medium capitalize">{review.source}</span>
                                                            {review.rating && <span className="ml-1">({review.rating}/5)</span>}
                                                            <span className="ml-1 text-gray-500">
                                                                {review.sentiment === 'positive' ? '👍' :
                                                                 review.sentiment === 'negative' ? '👎' : '😐'}
                                                            </span>
                                                            {review.highlights && review.highlights.length > 0 && (
                                                                <span className="ml-2 text-green-600 dark:text-green-400">
                                                                    +{review.highlights[0]}
                                                                </span>
                                                            )}
                                                            {review.concerns && review.concerns.length > 0 && (
                                                                <span className="ml-2 text-red-600 dark:text-red-400">
                                                                    -{review.concerns[0]}
                                                                </span>
                                                            )}
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            );
        }

        // Fallback: JSON (with truncation for large objects)
        const jsonString = JSON.stringify(stepData, null, 2);
        const isTruncated = jsonString.length > 2000;
        return (
            <pre className="text-xs overflow-x-auto text-gray-900 dark:text-gray-100">
                {isTruncated ? jsonString.slice(0, 2000) + '\n... (truncated)' : jsonString}
            </pre>
        );
    };

    // When loading, show a processing state instead of the checkpoint content
    if (isLoading) {
        const eventType = currentEvent?.event_type;
        const stepName = currentEvent?.node_name;
        const progressMessage = currentEvent?.data?.message;
        const progress = currentEvent?.data?.progress;

        const statusText = eventType === 'step_progress' && progressMessage
            ? progressMessage
            : eventType === 'step_start' && stepName
                ? `Running: ${stepName}`
                : eventType === 'step_complete' && stepName
                    ? `Completed: ${stepName}`
                    : 'Running next step';

        return (
            <div className="bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-xl p-4">
                <div className="flex items-center gap-3">
                    <ArrowPathIcon className="h-5 w-5 text-blue-600 dark:text-blue-400 animate-spin flex-shrink-0" />
                    <div className="flex-1">
                        <h3 className="font-semibold text-gray-900 dark:text-white">
                            Processing...
                        </h3>
                        <p className="text-sm text-gray-600 dark:text-gray-400">
                            {statusText}
                        </p>
                        {/* Progress bar if available */}
                        {eventType === 'step_progress' && progress != null && (
                            <div className="mt-2 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-blue-500 transition-all duration-300"
                                    style={{ width: `${Math.round(progress * 100)}%` }}
                                />
                            </div>
                        )}
                    </div>
                </div>
            </div>
        );
    }

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
                <div className="bg-white dark:bg-gray-900 rounded-lg p-4 border border-gray-200 dark:border-gray-700 max-h-[60vh] overflow-y-auto">
                    <div className="prose dark:prose-invert prose-sm max-w-none">
                        {renderStepData()}
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
    instance,
    handlers,
    isProcessing = false,
    currentEvent,
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
            ...Object.keys(instance.node_states || {}),
            ...Object.keys(instance.step_data),
        ]);

        return Array.from(nodeIds).map((id) => ({
            id,
            name: id.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
            description: '',
        }));
    }, [instance.node_states, instance.step_data]);

    // Determine if we're at a checkpoint
    const isAtCheckpoint = instance.status === 'waiting';
    const currentNodeId = instance.current_node?.id;

    // Mock checkpoint config - in real implementation, this comes from the node definition
    const checkpointConfig = isAtCheckpoint
        ? {
              title: instance.current_node?.name || 'Review',
              description: 'Please review and take action',
              allowed_actions: ['approve', 'edit', 'reject'] as string[],
              editable_fields: ['refined_question', 'scope'] as string[],
          }
        : null;

    // Get the data for the previous step (to show at checkpoint)
    const checkpointStepData = useMemo(() => {
        if (!isAtCheckpoint || !currentNodeId) return null;

        // Map checkpoint nodes to their preceding execute nodes
        const checkpointToDataMap: Record<string, string> = {
            // Research workflow
            'question_checkpoint': 'formulate_question',
            'checklist_checkpoint': 'build_checklist',
            'retrieval_checkpoint': 'run_retrieval',
            'final_checkpoint': 'compile_final',
            // Vendor finder workflow
            'criteria_checkpoint': 'define_criteria',
            'vendor_list_checkpoint': 'build_vendor_list',
            // Simple search workflow
            'answer_checkpoint': 'generate_answer',
        };

        // If we have a mapping for this checkpoint, use it
        const dataNodeId = checkpointToDataMap[currentNodeId];
        if (dataNodeId && instance.step_data[dataNodeId]) {
            return instance.step_data[dataNodeId];
        }

        // Fallback: find the most recently completed node's data
        const nodeStates = instance.node_states || {};
        const completedNodes = Object.entries(nodeStates)
            .filter(([_, state]) => state.status === 'completed')
            .map(([id]) => id);

        if (completedNodes.length === 0) {
            // Last fallback: just get the last key in step_data
            const stepDataKeys = Object.keys(instance.step_data);
            if (stepDataKeys.length === 0) return null;
            return instance.step_data[stepDataKeys[stepDataKeys.length - 1]];
        }

        // Return data from the last completed node
        const lastCompleted = completedNodes[completedNodes.length - 1];
        return instance.step_data[lastCompleted];
    }, [isAtCheckpoint, currentNodeId, instance.step_data, instance.node_states]);

    return (
        <div className="h-full flex flex-col p-4">
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                        Workflow Execution
                    </h2>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                        {instance.workflow_id}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <StatusBadge status={instance.status} />
                    {instance.status === 'running' && (
                        <button
                            onClick={() => handlers.onPause()}
                            className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
                        >
                            Pause
                        </button>
                    )}
                    {instance.status !== 'completed' && instance.status !== 'cancelled' && (
                        <button
                            onClick={() => handlers.onCancel()}
                            className="px-3 py-1.5 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
                        >
                            Cancel
                        </button>
                    )}
                </div>
            </div>

            {/* Checkpoint panel (shown when waiting at checkpoint) */}
            {isAtCheckpoint && checkpointConfig && (
                <div className="mb-6">
                    <CheckpointPanel
                        checkpoint={checkpointConfig}
                        stepData={checkpointStepData}
                        handlers={handlers}
                        isLoading={isProcessing}
                        currentEvent={currentEvent}
                    />
                </div>
            )}

            {/* Processing indicator (shown when processing but not at checkpoint yet) */}
            {isProcessing && !isAtCheckpoint && (
                <div className="mb-6 bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-xl p-4">
                    <div className="flex items-center gap-3">
                        <ArrowPathIcon className="h-5 w-5 text-blue-600 dark:text-blue-400 animate-spin" />
                        <div className="flex-1">
                            <div className="font-medium text-gray-900 dark:text-white">Processing...</div>
                            <div className="text-sm text-gray-500 dark:text-gray-400">
                                {currentEvent?.event_type === 'step_progress' && currentEvent?.data?.message
                                    ? currentEvent.data.message
                                    : currentEvent?.event_type === 'step_start' && currentEvent?.node_name
                                        ? `Running: ${currentEvent.node_name}`
                                        : currentEvent?.event_type === 'step_complete' && currentEvent?.node_name
                                            ? `Completed: ${currentEvent.node_name}`
                                            : instance.current_node?.name || 'Running workflow'}
                            </div>
                            {/* Progress bar if available */}
                            {currentEvent?.event_type === 'step_progress' && currentEvent?.data?.progress != null && (
                                <div className="mt-2 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                                    <div
                                        className="h-full bg-blue-500 transition-all duration-300"
                                        style={{ width: `${Math.round(currentEvent.data.progress * 100)}%` }}
                                    />
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* Nodes list */}
            <div className="flex-1 overflow-y-auto space-y-3">
                {nodes.map((node) => (
                    <StepItem
                        key={node.id}
                        step={node}
                        stepState={instance.node_states?.[node.id]}
                        isCurrent={node.id === currentNodeId}
                        isExpanded={expandedSteps.has(node.id)}
                        onToggle={() => toggleStep(node.id)}
                        stepData={instance.step_data[node.id]}
                    />
                ))}
            </div>

            {/* Completed state */}
            {instance.status === 'completed' && (
                <div className="mt-4 p-4 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl">
                    <div className="flex items-center gap-2">
                        <CheckCircleIcon className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                        <span className="font-medium text-gray-900 dark:text-white">Workflow completed</span>
                    </div>
                </div>
            )}

            {/* Failed state */}
            {instance.status === 'failed' && (
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
