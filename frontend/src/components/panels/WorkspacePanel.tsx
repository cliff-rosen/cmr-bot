import { useState, useEffect } from 'react';
import {
    WrenchScrewdriverIcon, XMarkIcon, ArchiveBoxArrowDownIcon,
    DocumentTextIcon, TableCellsIcon, CodeBracketIcon,
    ClipboardDocumentListIcon, PencilIcon, CheckIcon,
    PlayIcon, ArrowPathIcon, CheckCircleIcon
} from '@heroicons/react/24/solid';
import { JsonRenderer, MarkdownRenderer } from '../common';
import { ToolCall, WorkspacePayload, WorkflowStepDefinition, WorkflowStep } from '../../types/chat';
import { ToolCallRecord, ToolProgressUpdate } from '../../lib/api';

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
}

const payloadTypeConfig = {
    draft: {
        icon: DocumentTextIcon,
        color: 'text-blue-500',
        bg: 'bg-blue-50 dark:bg-blue-900/20',
        border: 'border-blue-200 dark:border-blue-800',
        label: 'Draft',
        editable: true
    },
    summary: {
        icon: ClipboardDocumentListIcon,
        color: 'text-green-500',
        bg: 'bg-green-50 dark:bg-green-900/20',
        border: 'border-green-200 dark:border-green-800',
        label: 'Summary',
        editable: false
    },
    data: {
        icon: TableCellsIcon,
        color: 'text-purple-500',
        bg: 'bg-purple-50 dark:bg-purple-900/20',
        border: 'border-purple-200 dark:border-purple-800',
        label: 'Data',
        editable: false
    },
    code: {
        icon: CodeBracketIcon,
        color: 'text-orange-500',
        bg: 'bg-orange-50 dark:bg-orange-900/20',
        border: 'border-orange-200 dark:border-orange-800',
        label: 'Code',
        editable: true
    },
    plan: {
        icon: PlayIcon,
        color: 'text-indigo-500',
        bg: 'bg-indigo-50 dark:bg-indigo-900/20',
        border: 'border-indigo-200 dark:border-indigo-800',
        label: 'Workflow Plan',
        editable: false
    },
    wip: {
        icon: ArrowPathIcon,
        color: 'text-amber-500',
        bg: 'bg-amber-50 dark:bg-amber-900/20',
        border: 'border-amber-200 dark:border-amber-800',
        label: 'Work in Progress',
        editable: true
    },
    final: {
        icon: CheckCircleIcon,
        color: 'text-green-500',
        bg: 'bg-green-50 dark:bg-green-900/20',
        border: 'border-green-200 dark:border-green-800',
        label: 'Workflow Complete',
        editable: false
    }
};

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
    onDismissFinal
}: WorkspacePanelProps) {
    const [isEditing, setIsEditing] = useState(false);
    const [editContent, setEditContent] = useState('');

    // Reset editing state when payload changes
    useEffect(() => {
        setIsEditing(false);
        setEditContent(activePayload?.content || '');
    }, [activePayload]);

    const handleStartEdit = () => {
        setEditContent(activePayload?.content || '');
        setIsEditing(true);
    };

    const handleSaveEdit = () => {
        if (activePayload && editContent !== activePayload.content) {
            onPayloadEdit({ ...activePayload, content: editContent });
        }
        setIsEditing(false);
    };

    const handleCancelEdit = () => {
        setEditContent(activePayload?.content || '');
        setIsEditing(false);
    };

    const config = activePayload ? payloadTypeConfig[activePayload.type] : null;
    const PayloadIcon = config?.icon || DocumentTextIcon;

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
            <div className={`flex-1 p-4 ${showExecuting || (showPayload && (activePayload?.type === 'plan' || activePayload?.type === 'wip' || activePayload?.type === 'final')) ? 'overflow-hidden flex flex-col' : 'overflow-y-auto'}`}>
                {/* Step Executing View */}
                {showExecuting && (
                    <div className="flex flex-col h-full min-h-0 overflow-hidden">
                        {/* Header area with spinner and status */}
                        <div className="flex items-center gap-4 mb-4 flex-shrink-0">
                            <div className="flex-shrink-0">
                                <div className="w-10 h-10 rounded-full border-4 border-indigo-200 dark:border-indigo-800 border-t-indigo-500 animate-spin" />
                            </div>
                            <div>
                                <h3 className="text-base font-medium text-gray-900 dark:text-white">
                                    Step {executingStep.step_number}: {executingStep.description}
                                </h3>
                                <p className="text-sm text-indigo-600 dark:text-indigo-400">
                                    {stepStatus || 'Starting...'}
                                </p>
                            </div>
                        </div>

                        {/* Tool activity section - takes all remaining space */}
                        <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
                            {(stepToolCalls.length > 0 || currentToolName) && (
                                <div className="flex flex-col h-full min-h-0">
                                    <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-2 flex-shrink-0">
                                        Tool Activity
                                    </h4>
                                    <div className="flex-1 min-h-0 overflow-y-auto space-y-2">
                                        {/* Completed tool calls */}
                                        {stepToolCalls.map((tc, idx) => (
                                            <div
                                                key={idx}
                                                className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700"
                                            >
                                                <div className="flex items-center gap-2 mb-1">
                                                    <CheckIcon className="h-4 w-4 text-green-500" />
                                                    <span className="font-medium text-sm text-gray-900 dark:text-white">
                                                        {tc.tool_name}
                                                    </span>
                                                </div>
                                                {tc.output && (
                                                    <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                                                        {tc.output.slice(0, 150)}...
                                                    </p>
                                                )}
                                            </div>
                                        ))}

                                        {/* Currently running tool with progress */}
                                        {currentToolName && (
                                            <div className="bg-indigo-50 dark:bg-indigo-900/20 rounded-lg p-3 border border-indigo-200 dark:border-indigo-700">
                                                <div className="flex items-center gap-2 mb-2">
                                                    <div className="h-4 w-4 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin" />
                                                    <span className="font-medium text-sm text-indigo-700 dark:text-indigo-300">
                                                        {currentToolName}
                                                    </span>
                                                </div>

                                                {/* Progress updates from this tool */}
                                                {currentToolProgress.length > 0 && (
                                                    <div className="ml-6 space-y-1 max-h-64 overflow-y-auto">
                                                        {currentToolProgress.map((prog, idx) => (
                                                            <div
                                                                key={idx}
                                                                className="text-xs border-l-2 border-indigo-300 dark:border-indigo-600 pl-2 py-0.5"
                                                            >
                                                                <span className="text-indigo-600 dark:text-indigo-400">
                                                                    {prog.message}
                                                                </span>
                                                                {/* Show checklist if present */}
                                                                {prog.data?.checklist && (
                                                                    <div className="mt-1 space-y-0.5">
                                                                        {(prog.data.checklist as Array<{question: string; status: string}>).map((item, i) => (
                                                                            <div key={i} className="flex items-start gap-1 text-[10px]">
                                                                                <span className={
                                                                                    item.status === 'complete' ? 'text-green-500' :
                                                                                    item.status === 'partial' ? 'text-yellow-500' :
                                                                                    'text-gray-400'
                                                                                }>
                                                                                    {item.status === 'complete' ? '✓' : item.status === 'partial' ? '◐' : '○'}
                                                                                </span>
                                                                                <span className="text-gray-600 dark:text-gray-400">
                                                                                    {item.question}
                                                                                </span>
                                                                            </div>
                                                                        ))}
                                                                    </div>
                                                                )}
                                                                {/* Show queries if present */}
                                                                {prog.data?.queries && (
                                                                    <div className="mt-1 flex flex-wrap gap-1">
                                                                        {(prog.data.queries as string[]).map((q, i) => (
                                                                            <span key={i} className="bg-gray-200 dark:bg-gray-700 px-1.5 py-0.5 rounded text-[10px] text-gray-600 dark:text-gray-400">
                                                                                {q}
                                                                            </span>
                                                                        ))}
                                                                    </div>
                                                                )}
                                                                {/* Show URLs if present */}
                                                                {prog.data?.urls && (
                                                                    <div className="mt-1 space-y-0.5">
                                                                        {(prog.data.urls as string[]).slice(0, 3).map((url, i) => (
                                                                            <div key={i} className="text-[10px] text-blue-500 dark:text-blue-400 truncate">
                                                                                {url}
                                                                            </div>
                                                                        ))}
                                                                    </div>
                                                                )}
                                                                {/* Progress bar if present */}
                                                                {prog.progress !== undefined && prog.progress !== null && (
                                                                    <div className="mt-1 h-1 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                                                                        <div
                                                                            className="h-full bg-indigo-500 transition-all"
                                                                            style={{ width: `${prog.progress * 100}%` }}
                                                                        />
                                                                    </div>
                                                                )}
                                                            </div>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}

                            {/* Empty state when no tool calls yet */}
                            {stepToolCalls.length === 0 && !currentToolName && (
                                <div className="flex-1 flex items-center justify-center">
                                    <p className="text-gray-400 dark:text-gray-500 text-sm">
                                        Waiting for tool activity...
                                    </p>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* Plan Payload View */}
                {showPayload && activePayload.type === 'plan' && config && (
                    <div className={`flex flex-col h-full rounded-lg border ${config.border} ${config.bg} overflow-hidden`}>
                        {/* Plan Header */}
                        <div className="flex-shrink-0 px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <PayloadIcon className={`h-5 w-5 ${config.color}`} />
                                <span className="font-medium text-gray-900 dark:text-white">
                                    {activePayload.title}
                                </span>
                            </div>
                        </div>

                        {/* Plan Content - scrollable */}
                        <div className="flex-1 overflow-y-auto p-4 space-y-4">
                            {/* Goal */}
                            {activePayload.goal && (
                                <div>
                                    <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-2">Goal</h4>
                                    <p className="text-sm text-gray-700 dark:text-gray-300">{activePayload.goal}</p>
                                </div>
                            )}

                            {/* Initial Input */}
                            {activePayload.initial_input && (
                                <div>
                                    <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-2">Initial Input</h4>
                                    <p className="text-sm text-gray-600 dark:text-gray-400 italic">{activePayload.initial_input}</p>
                                </div>
                            )}

                            {/* Steps */}
                            {activePayload.steps && activePayload.steps.length > 0 && (
                                <div>
                                    <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-2">Steps</h4>
                                    <div className="space-y-3">
                                        {activePayload.steps.map((step: WorkflowStepDefinition, idx: number) => (
                                            <div key={idx} className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700">
                                                <div className="flex items-start gap-3">
                                                    <span className="flex-shrink-0 inline-flex items-center justify-center w-6 h-6 rounded-full bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 text-sm font-medium">
                                                        {idx + 1}
                                                    </span>
                                                    <div className="flex-1 min-w-0">
                                                        <p className="font-medium text-gray-900 dark:text-white text-sm">
                                                            {step.description}
                                                        </p>
                                                        <div className="mt-2 space-y-1 text-xs text-gray-500 dark:text-gray-400">
                                                            <p><span className="font-medium">Input:</span> {step.input_description} (from {(step.input_sources || [(step as any).input_source || 'user']).map(s => s === 'user' ? 'user' : `step ${s}`).join(', ')})</p>
                                                            <p><span className="font-medium">Output:</span> {step.output_description}</p>
                                                            <p><span className="font-medium">Method:</span> {step.method.approach}</p>
                                                            {step.method.tools.length > 0 && (
                                                                <div className="flex flex-wrap gap-1 mt-1">
                                                                    {step.method.tools.map((tool, tidx) => (
                                                                        <span key={tidx} className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-[10px]">
                                                                            {tool}
                                                                        </span>
                                                                    ))}
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Plan Actions - fixed at bottom */}
                        <div className="flex-shrink-0 px-4 py-3 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 flex items-center justify-end gap-3">
                            <button
                                onClick={onRejectPlan}
                                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                            >
                                Reject
                            </button>
                            <button
                                onClick={() => onAcceptPlan?.(activePayload)}
                                className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg transition-colors"
                            >
                                Accept Plan
                            </button>
                        </div>
                    </div>
                )}

                {/* WIP Payload View */}
                {showPayload && activePayload.type === 'wip' && config && (
                    <div className={`flex flex-col h-full rounded-lg border ${config.border} ${config.bg} overflow-hidden`}>
                        {/* WIP Header */}
                        <div className="flex-shrink-0 px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <PayloadIcon className={`h-5 w-5 ${config.color}`} />
                                <span className="font-medium text-gray-900 dark:text-white">
                                    {activePayload.title}
                                </span>
                                {activePayload.step_number !== undefined && (
                                    <span className="text-xs text-gray-500 dark:text-gray-400">
                                        (Step {activePayload.step_number})
                                    </span>
                                )}
                            </div>
                            {!isEditing && (
                                <button
                                    onClick={handleStartEdit}
                                    className="flex items-center gap-1 px-2 py-1 text-xs text-gray-600 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded transition-colors"
                                    title="Edit content"
                                >
                                    <PencilIcon className="h-3 w-3" />
                                    Edit
                                </button>
                            )}
                        </div>

                        {/* WIP Content - scrollable */}
                        <div className="flex-1 overflow-y-auto p-4">
                            {isEditing ? (
                                <div className="space-y-3">
                                    <textarea
                                        value={editContent}
                                        onChange={(e) => setEditContent(e.target.value)}
                                        className="w-full h-64 p-3 text-sm font-mono bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-lg resize-y focus:outline-none focus:ring-2 focus:ring-amber-500 text-gray-900 dark:text-white"
                                        placeholder="Enter content..."
                                    />
                                    <div className="flex justify-end gap-2">
                                        <button
                                            onClick={handleCancelEdit}
                                            className="px-3 py-1.5 text-xs text-gray-600 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded transition-colors"
                                        >
                                            Cancel
                                        </button>
                                        <button
                                            onClick={handleSaveEdit}
                                            className="px-3 py-1.5 text-xs text-white bg-amber-600 hover:bg-amber-700 rounded transition-colors"
                                        >
                                            Save Changes
                                        </button>
                                    </div>
                                </div>
                            ) : activePayload.content_type === 'code' ? (
                                <pre className="p-3 bg-gray-900 dark:bg-black rounded-lg text-sm text-gray-100 overflow-x-auto whitespace-pre-wrap">
                                    {activePayload.content}
                                </pre>
                            ) : activePayload.content_type === 'data' ? (
                                <div className="bg-gray-50 dark:bg-gray-900 rounded p-3 text-sm overflow-x-auto">
                                    <pre className="whitespace-pre-wrap text-gray-700 dark:text-gray-300">{activePayload.content}</pre>
                                </div>
                            ) : (
                                <div className="prose prose-sm dark:prose-invert max-w-none">
                                    <MarkdownRenderer content={activePayload.content} />
                                </div>
                            )}
                        </div>

                        {/* WIP Actions - fixed at bottom */}
                        {!isEditing && (
                            <div className="flex-shrink-0 px-4 py-3 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 flex items-center justify-end gap-3">
                                <button
                                    onClick={onRejectWip}
                                    className="px-4 py-2 text-sm font-medium text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                                >
                                    Reject & Redo
                                </button>
                                <button
                                    onClick={() => onEditWip?.(activePayload)}
                                    className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                                >
                                    Request Changes
                                </button>
                                <button
                                    onClick={() => onAcceptWip?.(activePayload)}
                                    className="px-4 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg transition-colors"
                                >
                                    Accept & Continue
                                </button>
                            </div>
                        )}
                    </div>
                )}

                {/* Final Workflow Output View */}
                {showPayload && activePayload.type === 'final' && config && (
                    <div className={`flex flex-col h-full rounded-lg border ${config.border} ${config.bg} overflow-hidden`}>
                        {/* Final Header with success indicator */}
                        <div className="flex-shrink-0 px-4 py-4 border-b border-green-200 dark:border-green-800 bg-green-100 dark:bg-green-900/30">
                            <div className="flex items-center gap-3">
                                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-green-500 flex items-center justify-center">
                                    <CheckCircleIcon className="h-6 w-6 text-white" />
                                </div>
                                <div>
                                    <h3 className="font-semibold text-green-800 dark:text-green-200 text-lg">
                                        Workflow Complete
                                    </h3>
                                    <p className="text-sm text-green-600 dark:text-green-400">
                                        {activePayload.workflow_title && `"${activePayload.workflow_title}" `}
                                        completed successfully
                                        {activePayload.steps_completed && ` (${activePayload.steps_completed} steps)`}
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Final Output Header */}
                        <div className="flex-shrink-0 px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <DocumentTextIcon className="h-5 w-5 text-gray-500" />
                                <span className="font-medium text-gray-900 dark:text-white">
                                    {activePayload.title}
                                </span>
                            </div>
                        </div>

                        {/* Final Content - scrollable */}
                        <div className="flex-1 overflow-y-auto p-4">
                            {activePayload.content_type === 'code' ? (
                                <pre className="p-3 bg-gray-900 dark:bg-black rounded-lg text-sm text-gray-100 overflow-x-auto whitespace-pre-wrap">
                                    {activePayload.content}
                                </pre>
                            ) : activePayload.content_type === 'data' ? (
                                <div className="bg-gray-50 dark:bg-gray-900 rounded p-3 text-sm overflow-x-auto">
                                    <pre className="whitespace-pre-wrap text-gray-700 dark:text-gray-300">{activePayload.content}</pre>
                                </div>
                            ) : (
                                <div className="prose prose-sm dark:prose-invert max-w-none">
                                    <MarkdownRenderer content={activePayload.content} />
                                </div>
                            )}
                        </div>

                        {/* Final Actions - fixed at bottom */}
                        <div className="flex-shrink-0 px-4 py-3 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 flex items-center justify-between">
                            <p className="text-sm text-gray-500 dark:text-gray-400">
                                Save this output as an asset to keep it
                            </p>
                            <div className="flex items-center gap-3">
                                <button
                                    onClick={onDismissFinal}
                                    className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                                >
                                    Dismiss
                                </button>
                                <button
                                    onClick={() => onAcceptFinal?.(activePayload)}
                                    className="px-4 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg transition-colors flex items-center gap-2"
                                >
                                    <ArchiveBoxArrowDownIcon className="h-4 w-4" />
                                    Save as Asset
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                {/* Standard Payload View (draft, summary, data, code) */}
                {showPayload && activePayload.type !== 'plan' && activePayload.type !== 'wip' && activePayload.type !== 'final' && config && (
                    <div className={`rounded-lg border ${config.border} ${config.bg} overflow-hidden`}>
                        {/* Payload Header */}
                        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <PayloadIcon className={`h-5 w-5 ${config.color}`} />
                                <span className="font-medium text-gray-900 dark:text-white">
                                    {activePayload.title}
                                </span>
                            </div>
                            <div className="flex items-center gap-2">
                                {config.editable && !isEditing && (
                                    <button
                                        onClick={handleStartEdit}
                                        className="flex items-center gap-1 px-2 py-1 text-xs text-gray-600 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded transition-colors"
                                        title="Edit content"
                                    >
                                        <PencilIcon className="h-3 w-3" />
                                        Edit
                                    </button>
                                )}
                                {isEditing && (
                                    <>
                                        <button
                                            onClick={handleSaveEdit}
                                            className="flex items-center gap-1 px-2 py-1 text-xs text-green-600 hover:text-green-700 dark:text-green-400 dark:hover:text-green-300 hover:bg-green-50 dark:hover:bg-green-900/20 rounded transition-colors"
                                            title="Save changes"
                                        >
                                            <CheckIcon className="h-3 w-3" />
                                            Save
                                        </button>
                                        <button
                                            onClick={handleCancelEdit}
                                            className="flex items-center gap-1 px-2 py-1 text-xs text-gray-600 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded transition-colors"
                                            title="Cancel editing"
                                        >
                                            <XMarkIcon className="h-3 w-3" />
                                            Cancel
                                        </button>
                                    </>
                                )}
                                <button
                                    onClick={() => onSavePayloadAsAsset(activePayload, false)}
                                    className="flex items-center gap-1 px-2 py-1 text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors"
                                    title="Save as asset"
                                >
                                    <ArchiveBoxArrowDownIcon className="h-3 w-3" />
                                    Save
                                </button>
                                <button
                                    onClick={() => onSavePayloadAsAsset(activePayload, true)}
                                    className="flex items-center gap-1 px-2 py-1 text-xs text-green-600 hover:text-green-700 dark:text-green-400 dark:hover:text-green-300 hover:bg-green-50 dark:hover:bg-green-900/20 rounded transition-colors"
                                    title="Save as asset and close"
                                >
                                    <CheckIcon className="h-3 w-3" />
                                    Save & Close
                                </button>
                            </div>
                        </div>

                        {/* Payload Content */}
                        <div className="p-4">
                            {isEditing ? (
                                <textarea
                                    value={editContent}
                                    onChange={(e) => setEditContent(e.target.value)}
                                    className="w-full h-64 p-3 text-sm font-mono bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-lg resize-y focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 dark:text-white"
                                    placeholder="Enter content..."
                                />
                            ) : activePayload.type === 'code' ? (
                                <pre className="p-3 bg-gray-900 dark:bg-black rounded-lg text-sm text-gray-100 overflow-x-auto whitespace-pre-wrap">
                                    {activePayload.content}
                                </pre>
                            ) : (
                                <div className="prose prose-sm dark:prose-invert max-w-none">
                                    <MarkdownRenderer content={activePayload.content} />
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* Tool History View */}
                {showToolHistory && (
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
                                                onClick={() => onSaveAsAsset(toolCall)}
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
