import { useState, useEffect } from 'react';
import {
    WrenchScrewdriverIcon, XMarkIcon, ArchiveBoxArrowDownIcon,
    DocumentTextIcon, TableCellsIcon, CodeBracketIcon,
    ClipboardDocumentListIcon, PencilIcon, CheckIcon
} from '@heroicons/react/24/solid';
import { JsonRenderer, MarkdownRenderer } from '../common';
import { ToolCall, WorkspacePayload } from '../../types/chat';

interface WorkspacePanelProps {
    selectedToolHistory: ToolCall[] | null;
    activePayload: WorkspacePayload | null;
    onClose: () => void;
    onSaveAsAsset: (toolCall: ToolCall) => void;
    onSavePayloadAsAsset: (payload: WorkspacePayload) => void;
    onPayloadEdit: (payload: WorkspacePayload) => void;
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
        icon: ClipboardDocumentListIcon,
        color: 'text-cyan-500',
        bg: 'bg-cyan-50 dark:bg-cyan-900/20',
        border: 'border-cyan-200 dark:border-cyan-800',
        label: 'Plan',
        editable: true
    }
};

export default function WorkspacePanel({
    selectedToolHistory,
    activePayload,
    onClose,
    onSaveAsAsset,
    onSavePayloadAsAsset,
    onPayloadEdit
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
    const showPayload = activePayload && !selectedToolHistory;
    const showToolHistory = selectedToolHistory && selectedToolHistory.length > 0;
    const showEmpty = !showPayload && !showToolHistory;

    return (
        <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-950">
            {/* Workspace Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                <div>
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                        {showToolHistory ? 'Tool History' : showPayload ? activePayload.title : 'Workspace'}
                    </h2>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                        {showToolHistory
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
                {/* Payload View */}
                {showPayload && config && (
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
                                    onClick={() => onSavePayloadAsAsset(activePayload)}
                                    className="flex items-center gap-1 px-2 py-1 text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors"
                                    title="Save as asset"
                                >
                                    <ArchiveBoxArrowDownIcon className="h-3 w-3" />
                                    Save
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
