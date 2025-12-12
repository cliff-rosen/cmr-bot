/**
 * Tool history view
 * Shows a list of tool calls with their inputs and outputs
 */

import { WrenchScrewdriverIcon, ArchiveBoxArrowDownIcon } from '@heroicons/react/24/solid';
import { JsonRenderer } from '../../common';
import { ToolCall } from '../../../types/chat';

interface ToolHistoryViewProps {
    toolCalls: ToolCall[];
    onSaveAsAsset: (toolCall: ToolCall) => void;
}

export default function ToolHistoryView({ toolCalls, onSaveAsAsset }: ToolHistoryViewProps) {
    return (
        <div className="space-y-4">
            {toolCalls.map((toolCall, idx) => (
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
    );
}
