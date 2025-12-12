/**
 * Step execution view
 * Shows the progress of a workflow step being executed
 */

import { CheckIcon } from '@heroicons/react/24/solid';
import { WorkflowStep } from '../../../types/chat';
import { ToolCallRecord, ToolProgressUpdate } from '../../../lib/api';
import IteratorProgress from './IteratorProgress';
import ToolProgress from './ToolProgress';

interface StepExecutingViewProps {
    executingStep: WorkflowStep;
    stepStatus: string;
    stepToolCalls: ToolCallRecord[];
    currentToolName: string | null;
    currentToolProgress: ToolProgressUpdate[];
}

export default function StepExecutingView({
    executingStep,
    stepStatus,
    stepToolCalls,
    currentToolName,
    currentToolProgress
}: StepExecutingViewProps) {
    return (
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

                                    {/* Tool-specific progress visualization */}
                                    {currentToolName === 'iterate' && currentToolProgress.length > 0 ? (
                                        <IteratorProgress progressUpdates={currentToolProgress} />
                                    ) : currentToolProgress.length > 0 ? (
                                        <ToolProgress progressUpdates={currentToolProgress} />
                                    ) : null}
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
    );
}
