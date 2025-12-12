/**
 * Iterator tool progress visualization
 * Shows a list of items being processed with their completion status
 */

import { ToolProgressUpdate } from '../../../lib/api';

interface IteratorProgressProps {
    progressUpdates: ToolProgressUpdate[];
}

interface CompletedItem {
    result: string;
    success: boolean;
    error?: string;
}

export default function IteratorProgress({ progressUpdates }: IteratorProgressProps) {
    // Extract items list from starting event
    const startingEvent = progressUpdates.find(p => p.stage === 'starting' && p.data?.items);
    const items = (startingEvent?.data?.items as string[]) || [];

    // Build map of completed items
    const completedItems = new Map<number, CompletedItem>();
    progressUpdates
        .filter(p => p.stage === 'item_complete' && p.data?.index !== undefined)
        .forEach(p => {
            completedItems.set(p.data!.index as number, {
                result: p.data!.result as string || '',
                success: p.data!.success as boolean,
                error: p.data!.error as string | undefined
            });
        });

    const latestProgress = progressUpdates[progressUpdates.length - 1];
    const completed = latestProgress?.data?.completed as number || completedItems.size;
    const total = latestProgress?.data?.total as number || items.length;

    if (items.length === 0) {
        return null;
    }

    return (
        <div className="ml-6 space-y-2">
            {/* Progress summary */}
            <div className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400">
                <span>{completed}/{total} completed</span>
                <div className="flex-1 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                    <div
                        className="h-full bg-indigo-500 transition-all"
                        style={{ width: `${total > 0 ? (completed / total) * 100 : 0}%` }}
                    />
                </div>
            </div>

            {/* Items list */}
            <div className="space-y-1 max-h-64 overflow-y-auto">
                {items.map((item, idx) => {
                    const completion = completedItems.get(idx);
                    const isPending = !completion;
                    const isSuccess = completion?.success;

                    return (
                        <div
                            key={idx}
                            className={`flex items-start gap-2 text-xs p-1.5 rounded ${
                                isPending
                                    ? 'bg-gray-50 dark:bg-gray-800/50'
                                    : isSuccess
                                        ? 'bg-green-50 dark:bg-green-900/20'
                                        : 'bg-red-50 dark:bg-red-900/20'
                            }`}
                        >
                            <span className={`flex-shrink-0 ${
                                isPending
                                    ? 'text-gray-400'
                                    : isSuccess
                                        ? 'text-green-500'
                                        : 'text-red-500'
                            }`}>
                                {isPending ? '○' : isSuccess ? '✓' : '✗'}
                            </span>
                            <div className="flex-1 min-w-0">
                                <div className="font-medium text-gray-700 dark:text-gray-300 truncate">
                                    {item}
                                </div>
                                {completion && (
                                    <div className={`mt-0.5 text-[10px] ${
                                        isSuccess
                                            ? 'text-gray-500 dark:text-gray-400'
                                            : 'text-red-600 dark:text-red-400'
                                    }`}>
                                        {isSuccess
                                            ? (completion.result.length > 100
                                                ? completion.result.slice(0, 100) + '...'
                                                : completion.result)
                                            : `Error: ${completion.error}`
                                        }
                                    </div>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
