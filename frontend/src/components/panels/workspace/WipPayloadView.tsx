/**
 * Work-in-progress payload view
 * Shows step output for user review with accept/edit/reject options
 */

import { useState, useEffect } from 'react';
import { PencilIcon } from '@heroicons/react/24/solid';
import { MarkdownRenderer } from '../../common';
import { WorkspacePayload } from '../../../types/chat';
import { payloadTypeConfig } from './types';

interface WipPayloadViewProps {
    payload: WorkspacePayload;
    onAccept: (payload: WorkspacePayload) => void;
    onEdit: (payload: WorkspacePayload) => void;
    onReject: () => void;
    onPayloadEdit: (payload: WorkspacePayload) => void;
}

export default function WipPayloadView({
    payload,
    onAccept,
    onEdit,
    onReject,
    onPayloadEdit
}: WipPayloadViewProps) {
    const [isEditing, setIsEditing] = useState(false);
    const [editContent, setEditContent] = useState(payload.content);

    const config = payloadTypeConfig.wip;
    const PayloadIcon = config.icon;

    // Reset editing state when payload changes
    useEffect(() => {
        setIsEditing(false);
        setEditContent(payload.content);
    }, [payload]);

    const handleStartEdit = () => {
        setEditContent(payload.content);
        setIsEditing(true);
    };

    const handleSaveEdit = () => {
        if (editContent !== payload.content) {
            onPayloadEdit({ ...payload, content: editContent });
        }
        setIsEditing(false);
    };

    const handleCancelEdit = () => {
        setEditContent(payload.content);
        setIsEditing(false);
    };

    return (
        <div className={`flex flex-col h-full rounded-lg border ${config.border} ${config.bg} overflow-hidden`}>
            {/* WIP Header */}
            <div className="flex-shrink-0 px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <PayloadIcon className={`h-5 w-5 ${config.color}`} />
                    <span className="font-medium text-gray-900 dark:text-white">
                        {payload.title}
                    </span>
                    {payload.step_number !== undefined && (
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                            (Step {payload.step_number})
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
                ) : payload.content_type === 'code' ? (
                    <pre className="p-3 bg-gray-900 dark:bg-black rounded-lg text-sm text-gray-100 overflow-x-auto whitespace-pre-wrap">
                        {payload.content}
                    </pre>
                ) : payload.content_type === 'data' ? (
                    <div className="bg-gray-50 dark:bg-gray-900 rounded p-3 text-sm overflow-x-auto">
                        <pre className="whitespace-pre-wrap text-gray-700 dark:text-gray-300">{payload.content}</pre>
                    </div>
                ) : (
                    <div className="prose prose-sm dark:prose-invert max-w-none">
                        <MarkdownRenderer content={payload.content} />
                    </div>
                )}
            </div>

            {/* WIP Actions - fixed at bottom */}
            {!isEditing && (
                <div className="flex-shrink-0 px-4 py-3 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 flex items-center justify-end gap-3">
                    <button
                        onClick={onReject}
                        className="px-4 py-2 text-sm font-medium text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                    >
                        Reject & Redo
                    </button>
                    <button
                        onClick={() => onEdit(payload)}
                        className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                    >
                        Request Changes
                    </button>
                    <button
                        onClick={() => onAccept(payload)}
                        className="px-4 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg transition-colors"
                    >
                        Accept & Continue
                    </button>
                </div>
            )}
        </div>
    );
}
