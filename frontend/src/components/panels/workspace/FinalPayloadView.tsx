/**
 * Final workflow output view
 * Shows completed workflow output with save/dismiss options
 */

import { CheckCircleIcon, DocumentTextIcon, ArchiveBoxArrowDownIcon } from '@heroicons/react/24/solid';
import { MarkdownRenderer } from '../../common';
import { WorkspacePayload } from '../../../types/chat';
import { payloadTypeConfig } from './types';

interface FinalPayloadViewProps {
    payload: WorkspacePayload;
    onAccept: (payload: WorkspacePayload) => void;
    onDismiss: () => void;
}

export default function FinalPayloadView({ payload, onAccept, onDismiss }: FinalPayloadViewProps) {
    const config = payloadTypeConfig.final;

    return (
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
                            {payload.workflow_title && `"${payload.workflow_title}" `}
                            completed successfully
                            {payload.steps_completed && ` (${payload.steps_completed} steps)`}
                        </p>
                    </div>
                </div>
            </div>

            {/* Final Output Header */}
            <div className="flex-shrink-0 px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <DocumentTextIcon className="h-5 w-5 text-gray-500" />
                    <span className="font-medium text-gray-900 dark:text-white">
                        {payload.title}
                    </span>
                </div>
            </div>

            {/* Final Content - scrollable */}
            <div className="flex-1 overflow-y-auto p-4">
                {payload.content_type === 'code' ? (
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

            {/* Final Actions - fixed at bottom */}
            <div className="flex-shrink-0 px-4 py-3 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 flex items-center justify-between">
                <p className="text-sm text-gray-500 dark:text-gray-400">
                    Save this output as an asset to keep it
                </p>
                <div className="flex items-center gap-3">
                    <button
                        onClick={onDismiss}
                        className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                    >
                        Dismiss
                    </button>
                    <button
                        onClick={() => onAccept(payload)}
                        className="px-4 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg transition-colors flex items-center gap-2"
                    >
                        <ArchiveBoxArrowDownIcon className="h-4 w-4" />
                        Save as Asset
                    </button>
                </div>
            </div>
        </div>
    );
}
