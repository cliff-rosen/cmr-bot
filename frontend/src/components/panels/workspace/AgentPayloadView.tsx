/**
 * Agent payload view
 * Shows an agent create/update proposal for user to accept or reject
 */

import { WorkspacePayload } from '../../../types/chat';
import { payloadTypeConfig } from './types';
import { CpuChipIcon } from '@heroicons/react/24/solid';

interface AgentPayloadViewProps {
    payload: WorkspacePayload;
    onAccept: (payload: WorkspacePayload) => void;
    onReject: () => void;
}

export default function AgentPayloadView({ payload, onAccept, onReject }: AgentPayloadViewProps) {
    const isUpdate = payload.type === 'agent_update';
    const config = payloadTypeConfig[payload.type] || {
        icon: CpuChipIcon,
        color: 'text-cyan-500',
        bg: 'bg-cyan-50 dark:bg-cyan-900/20',
        border: 'border-cyan-200 dark:border-cyan-800',
        label: isUpdate ? 'Update Agent' : 'Create Agent'
    };
    const PayloadIcon = config.icon;
    const agentData = payload.agent_data;

    if (!agentData) {
        return (
            <div className="p-4 text-gray-500 dark:text-gray-400">
                Invalid agent payload - missing agent data
            </div>
        );
    }

    const lifecycleLabels: Record<string, string> = {
        'one_shot': 'One-Shot (run once)',
        'scheduled': 'Scheduled (run on schedule)',
        'monitor': 'Monitor (watch for conditions)'
    };

    return (
        <div className={`flex flex-col h-full rounded-lg border ${config.border} ${config.bg} overflow-hidden`}>
            {/* Header */}
            <div className="flex-shrink-0 px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <PayloadIcon className={`h-5 w-5 ${config.color}`} />
                    <span className="font-medium text-gray-900 dark:text-white">
                        {payload.title}
                    </span>
                </div>
                <span className={`px-2 py-0.5 text-xs font-medium rounded ${isUpdate ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300' : 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'}`}>
                    {isUpdate ? 'Update' : 'New Agent'}
                </span>
            </div>

            {/* Content - scrollable */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {/* Agent Name */}
                <div>
                    <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-1">Name</h4>
                    <p className="text-sm font-medium text-gray-900 dark:text-white">{agentData.name}</p>
                </div>

                {/* Description */}
                {agentData.description && (
                    <div>
                        <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-1">Description</h4>
                        <p className="text-sm text-gray-700 dark:text-gray-300">{agentData.description}</p>
                    </div>
                )}

                {/* Lifecycle */}
                <div>
                    <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-1">Lifecycle</h4>
                    <p className="text-sm text-gray-700 dark:text-gray-300">
                        {lifecycleLabels[agentData.lifecycle] || agentData.lifecycle}
                    </p>
                </div>

                {/* Monitor Interval */}
                {agentData.lifecycle === 'monitor' && agentData.monitor_interval_minutes && (
                    <div>
                        <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-1">Check Interval</h4>
                        <p className="text-sm text-gray-700 dark:text-gray-300">
                            Every {agentData.monitor_interval_minutes} minutes
                        </p>
                    </div>
                )}

                {/* Tools */}
                {agentData.tools && agentData.tools.length > 0 && (
                    <div>
                        <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-2">Tools ({agentData.tools.length})</h4>
                        <div className="flex flex-wrap gap-1">
                            {agentData.tools.map((tool, idx) => (
                                <span
                                    key={idx}
                                    className="px-2 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded text-xs"
                                >
                                    {tool}
                                </span>
                            ))}
                        </div>
                    </div>
                )}

                {/* Instructions */}
                <div>
                    <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-2">Instructions</h4>
                    <div className="p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 max-h-64 overflow-y-auto">
                        <pre className="whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-300 font-mono">
                            {agentData.instructions}
                        </pre>
                    </div>
                </div>

                {/* Explanatory content from payload */}
                {payload.content && (
                    <div>
                        <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-2">Notes</h4>
                        <p className="text-sm text-gray-600 dark:text-gray-400">{payload.content}</p>
                    </div>
                )}
            </div>

            {/* Actions - fixed at bottom */}
            <div className="flex-shrink-0 px-4 py-3 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 flex items-center justify-end gap-3">
                <button
                    onClick={onReject}
                    className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                >
                    Dismiss
                </button>
                <button
                    onClick={() => onAccept(payload)}
                    className="px-4 py-2 text-sm font-medium text-white bg-cyan-600 hover:bg-cyan-700 rounded-lg transition-colors"
                >
                    {isUpdate ? 'Update Agent' : 'Create Agent'}
                </button>
            </div>
        </div>
    );
}
