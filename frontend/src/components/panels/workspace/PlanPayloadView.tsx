/**
 * Workflow plan payload view
 * Shows a workflow plan for user to accept or reject
 */

import { WorkspacePayload, WorkflowStepDefinition } from '../../../types/chat';
import { payloadTypeConfig } from './types';

interface PlanPayloadViewProps {
    payload: WorkspacePayload;
    onAccept: (payload: WorkspacePayload) => void;
    onReject: () => void;
}

export default function PlanPayloadView({ payload, onAccept, onReject }: PlanPayloadViewProps) {
    const config = payloadTypeConfig.plan;
    const PayloadIcon = config.icon;

    return (
        <div className={`flex flex-col h-full rounded-lg border ${config.border} ${config.bg} overflow-hidden`}>
            {/* Plan Header */}
            <div className="flex-shrink-0 px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <PayloadIcon className={`h-5 w-5 ${config.color}`} />
                    <span className="font-medium text-gray-900 dark:text-white">
                        {payload.title}
                    </span>
                </div>
            </div>

            {/* Plan Content - scrollable */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {/* Goal */}
                {payload.goal && (
                    <div>
                        <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-2">Goal</h4>
                        <p className="text-sm text-gray-700 dark:text-gray-300">{payload.goal}</p>
                    </div>
                )}

                {/* Initial Input */}
                {payload.initial_input && (
                    <div>
                        <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-2">Initial Input</h4>
                        <p className="text-sm text-gray-600 dark:text-gray-400 italic">{payload.initial_input}</p>
                    </div>
                )}

                {/* Steps */}
                {payload.steps && payload.steps.length > 0 && (
                    <div>
                        <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-2">Steps</h4>
                        <div className="space-y-3">
                            {payload.steps.map((step: WorkflowStepDefinition, idx: number) => (
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
                                                <p>
                                                    <span className="font-medium">Input:</span> {step.input_description} (from {(step.input_sources || [(step as any).input_source || 'user']).map(s => s === 'user' ? 'user' : `step ${s}`).join(', ')})
                                                </p>
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
                    onClick={onReject}
                    className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                >
                    Reject
                </button>
                <button
                    onClick={() => onAccept(payload)}
                    className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg transition-colors"
                >
                    Accept Plan
                </button>
            </div>
        </div>
    );
}
