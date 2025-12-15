/**
 * Standard payload view
 * Shows draft, summary, data, or code payloads with edit/save options
 */

import { useState, useEffect } from 'react';
import { PencilIcon, CheckIcon, XMarkIcon, ArchiveBoxArrowDownIcon } from '@heroicons/react/24/solid';
import { MarkdownRenderer } from '../../common';
import { WorkspacePayload } from '../../../types/chat';
import { payloadTypeConfig } from './types';

interface StandardPayloadViewProps {
    payload: WorkspacePayload;
    onSaveAsAsset: (payload: WorkspacePayload, andClose?: boolean) => void;
    isSaving?: boolean;
    onPayloadEdit: (payload: WorkspacePayload) => void;
}

export default function StandardPayloadView({
    payload,
    onSaveAsAsset,
    isSaving = false,
    onPayloadEdit
}: StandardPayloadViewProps) {
    const [isEditing, setIsEditing] = useState(false);
    const [editContent, setEditContent] = useState(payload.content);

    const config = payloadTypeConfig[payload.type];
    const PayloadIcon = config?.icon;

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

    if (!config) {
        return null;
    }

    return (
        <div className={`rounded-lg border ${config.border} ${config.bg} overflow-hidden`}>
            {/* Payload Header */}
            <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    {PayloadIcon && <PayloadIcon className={`h-5 w-5 ${config.color}`} />}
                    <span className="font-medium text-gray-900 dark:text-white">
                        {payload.title}
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
                        onClick={() => onSaveAsAsset(payload, false)}
                        disabled={isSaving}
                        className="flex items-center gap-1 px-2 py-1 text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        title="Save as asset"
                    >
                        {isSaving ? (
                            <svg className="animate-spin h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                        ) : (
                            <ArchiveBoxArrowDownIcon className="h-3 w-3" />
                        )}
                        {isSaving ? 'Saving...' : 'Save as Asset'}
                    </button>
                    <button
                        onClick={() => onSaveAsAsset(payload, true)}
                        disabled={isSaving}
                        className="flex items-center gap-1 px-2 py-1 text-xs text-green-600 hover:text-green-700 dark:text-green-400 dark:hover:text-green-300 hover:bg-green-50 dark:hover:bg-green-900/20 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        title="Save as asset and close"
                    >
                        {isSaving ? (
                            <svg className="animate-spin h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                        ) : (
                            <CheckIcon className="h-3 w-3" />
                        )}
                        {isSaving ? 'Saving...' : 'Save & Close'}
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
                ) : payload.type === 'code' ? (
                    <pre className="p-3 bg-gray-900 dark:bg-black rounded-lg text-sm text-gray-100 overflow-x-auto whitespace-pre-wrap">
                        {payload.content}
                    </pre>
                ) : (
                    <div className="prose prose-sm dark:prose-invert max-w-none">
                        <MarkdownRenderer content={payload.content} />
                    </div>
                )}
            </div>
        </div>
    );
}
