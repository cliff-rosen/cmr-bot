/**
 * MapReduce progress visualization
 * Shows real-time progress of map and reduce phases
 */

import { ToolProgressUpdate } from '../../../lib/api';

interface MapReduceProgressProps {
    progressUpdates: ToolProgressUpdate[];
}

interface MapItemState {
    result: string;
    success: boolean;
    error?: string;
}

export default function MapReduceProgress({ progressUpdates }: MapReduceProgressProps) {
    // Extract items list from map_starting event
    const startingEvent = progressUpdates.find(p => p.stage === 'map_starting' && p.data?.items);
    const items = (startingEvent?.data?.items as string[]) || [];

    // Build map of completed items
    const completedItems = new Map<number, MapItemState>();
    progressUpdates
        .filter(p => p.stage === 'map_item_complete' && p.data?.index !== undefined)
        .forEach(p => {
            completedItems.set(p.data!.index as number, {
                result: p.data!.result as string || '',
                success: p.data!.success as boolean,
                error: p.data!.error as string | undefined
            });
        });

    // Check for reduce phase
    const reduceStarting = progressUpdates.find(p => p.stage === 'reduce_starting');
    const reduceComplete = progressUpdates.find(p => p.stage === 'reduce_complete');
    const reduceSuccess = reduceComplete?.data?.success as boolean;

    // Get latest progress
    const latestProgress = progressUpdates[progressUpdates.length - 1];
    const mapCompleted = latestProgress?.data?.completed as number || completedItems.size;
    const total = latestProgress?.data?.total as number || items.length;
    const mapSuccessful = reduceStarting?.data?.map_successful as number;
    const mapFailed = reduceStarting?.data?.map_failed as number;

    // Calculate phase
    const inMapPhase = !reduceStarting;
    const inReducePhase = reduceStarting && !reduceComplete;
    const isComplete = reduceComplete !== undefined;

    return (
        <div className="ml-6 space-y-3">
            {/* Phase indicator */}
            <div className="flex items-center gap-3 text-xs">
                <div className={`flex items-center gap-1.5 px-2 py-1 rounded ${
                    inMapPhase
                        ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                        : 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                }`}>
                    <span className={inMapPhase ? 'animate-pulse' : ''}>
                        {inMapPhase ? '1. Mapping...' : '1. Map'}
                    </span>
                    {!inMapPhase && <span className="text-green-500">✓</span>}
                </div>
                <span className="text-gray-400">→</span>
                <div className={`flex items-center gap-1.5 px-2 py-1 rounded ${
                    inReducePhase
                        ? 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300'
                        : isComplete
                            ? reduceSuccess
                                ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                                : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300'
                            : 'bg-gray-100 dark:bg-gray-800 text-gray-500'
                }`}>
                    <span className={inReducePhase ? 'animate-pulse' : ''}>
                        {inReducePhase ? '2. Reducing...' : isComplete ? '2. Reduce' : '2. Reduce'}
                    </span>
                    {isComplete && reduceSuccess && <span className="text-green-500">✓</span>}
                    {isComplete && !reduceSuccess && <span className="text-red-500">✗</span>}
                </div>
            </div>

            {/* Map phase progress */}
            {inMapPhase && (
                <>
                    <div className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400">
                        <span>{mapCompleted}/{total} mapped</span>
                        <div className="flex-1 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                            <div
                                className="h-full bg-blue-500 transition-all"
                                style={{ width: `${total > 0 ? (mapCompleted / total) * 100 : 0}%` }}
                            />
                        </div>
                    </div>

                    {/* Items list */}
                    <div className="space-y-1 max-h-48 overflow-y-auto">
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
                                                    ? (completion.result.length > 80
                                                        ? completion.result.slice(0, 80) + '...'
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
                </>
            )}

            {/* Reduce phase */}
            {(inReducePhase || isComplete) && (
                <div className="space-y-2">
                    {/* Map summary */}
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                        Map completed: {mapSuccessful || completedItems.size} successful
                        {mapFailed !== undefined && mapFailed > 0 && (
                            <span className="text-red-500"> ({mapFailed} failed)</span>
                        )}
                    </div>

                    {/* Reduce status */}
                    {inReducePhase && (
                        <div className="flex items-center gap-2 text-xs">
                            <div className="h-3 w-3 rounded-full border-2 border-purple-500 border-t-transparent animate-spin" />
                            <span className="text-purple-600 dark:text-purple-400">
                                Combining results...
                            </span>
                        </div>
                    )}

                    {isComplete && (
                        <div className={`flex items-center gap-2 text-xs ${
                            reduceSuccess
                                ? 'text-green-600 dark:text-green-400'
                                : 'text-red-600 dark:text-red-400'
                        }`}>
                            <span>{reduceSuccess ? '✓' : '✗'}</span>
                            <span>
                                {reduceSuccess
                                    ? 'Reduce complete'
                                    : `Reduce failed: ${reduceComplete?.data?.error || 'Unknown error'}`
                                }
                            </span>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
