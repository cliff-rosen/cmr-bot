import { useState, useEffect } from 'react';
import {
    WrenchScrewdriverIcon, XMarkIcon, ArchiveBoxArrowDownIcon,
    DocumentTextIcon, TableCellsIcon, CodeBracketIcon,
    ClipboardDocumentListIcon, PencilIcon, CheckIcon,
    PlayIcon, ArrowPathIcon
} from '@heroicons/react/24/solid';
import { JsonRenderer, MarkdownRenderer } from '../common';
import { ToolCall, WorkspacePayload, WorkflowStepDefinition, WorkflowStep } from '../../types/chat';

interface WorkspacePanelProps {
    selectedToolHistory: ToolCall[] | null;
    activePayload: WorkspacePayload | null;
    executingStep: WorkflowStep | null;
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
    }
};

export default function WorkspacePanel({
    selectedToolHistory,
    activePayload,
    executingStep,
    onClose,
    onSaveAsAsset,
    onSavePayloadAsAsset,
    onPayloadEdit,
    onAcceptPlan,
    onRejectPlan,
    onAcceptWip,
    onEditWip,
    onRejectWip
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
            <div className="flex-1 overflow-y-auto p-4">
                {/* Step Executing View */}
                {showExecuting && (
                    <div className="flex flex-col items-center justify-center h-full text-center">
                        <div className="mb-6">
                            <div className="w-16 h-16 rounded-full border-4 border-indigo-200 dark:border-indigo-800 border-t-indigo-500 animate-spin" />
                        </div>
                        <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
                            Executing Step {executingStep.step_number}
                        </h3>
                        <p className="text-gray-600 dark:text-gray-400 mb-4 max-w-md">
                            {executingStep.description}
                        </p>
                        <div className="text-sm text-gray-500 dark:text-gray-500">
                            {executingStep.method.tools.length > 0 ? (
                                <span>Using: {executingStep.method.tools.join(', ')}</span>
                            ) : (
                                <span>Processing...</span>
                            )}
                        </div>
                    </div>
                )}

                {/* Plan Payload View */}
                {showPayload && activePayload.type === 'plan' && config && (
                    <div className={`rounded-lg border ${config.border} ${config.bg} overflow-hidden`}>
                        {/* Plan Header */}
                        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <PayloadIcon className={`h-5 w-5 ${config.color}`} />
                                <span className="font-medium text-gray-900 dark:text-white">
                                    {activePayload.title}
                                </span>
                            </div>
                        </div>

                        {/* Plan Content */}
                        <div className="p-4 space-y-4">
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
                                                            <p><span className="font-medium">Input:</span> {step.input_description} (from {step.input_source === 'user' ? 'user' : `step ${step.input_source}`})</p>
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

                        {/* Plan Actions */}
                        <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 flex items-center justify-end gap-3">
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
                    <div className={`rounded-lg border ${config.border} ${config.bg} overflow-hidden`}>
                        {/* WIP Header */}
                        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
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

                        {/* WIP Content */}
                        <div className="p-4">
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

                        {/* WIP Actions */}
                        {!isEditing && (
                            <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 flex items-center justify-end gap-3">
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

                {/* Standard Payload View (draft, summary, data, code) */}
                {showPayload && activePayload.type !== 'plan' && activePayload.type !== 'wip' && config && (
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
