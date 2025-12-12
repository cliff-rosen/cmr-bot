/**
 * Standard tool progress visualization
 * Shows progress updates with checklist, queries, URLs, and progress bar
 */

import { ToolProgressUpdate } from '../../../lib/api';

interface ToolProgressProps {
    progressUpdates: ToolProgressUpdate[];
}

export default function ToolProgress({ progressUpdates }: ToolProgressProps) {
    if (progressUpdates.length === 0) {
        return null;
    }

    return (
        <div className="ml-6 space-y-1 max-h-64 overflow-y-auto">
            {progressUpdates.map((prog, idx) => (
                <div
                    key={idx}
                    className="text-xs border-l-2 border-indigo-300 dark:border-indigo-600 pl-2 py-0.5"
                >
                    <span className="text-indigo-600 dark:text-indigo-400">
                        {prog.message}
                    </span>

                    {/* Show checklist if present */}
                    {prog.data?.checklist && (
                        <div className="mt-1 space-y-0.5">
                            {(prog.data.checklist as Array<{question: string; status: string}>).map((item, i) => (
                                <div key={i} className="flex items-start gap-1 text-[10px]">
                                    <span className={
                                        item.status === 'complete' ? 'text-green-500' :
                                        item.status === 'partial' ? 'text-yellow-500' :
                                        'text-gray-400'
                                    }>
                                        {item.status === 'complete' ? '✓' : item.status === 'partial' ? '◐' : '○'}
                                    </span>
                                    <span className="text-gray-600 dark:text-gray-400">
                                        {item.question}
                                    </span>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Show queries if present */}
                    {prog.data?.queries && (
                        <div className="mt-1 flex flex-wrap gap-1">
                            {(prog.data.queries as string[]).map((q, i) => (
                                <span key={i} className="bg-gray-200 dark:bg-gray-700 px-1.5 py-0.5 rounded text-[10px] text-gray-600 dark:text-gray-400">
                                    {q}
                                </span>
                            ))}
                        </div>
                    )}

                    {/* Show URLs if present */}
                    {prog.data?.urls && (
                        <div className="mt-1 space-y-0.5">
                            {(prog.data.urls as string[]).slice(0, 3).map((url, i) => (
                                <div key={i} className="text-[10px] text-blue-500 dark:text-blue-400 truncate">
                                    {url}
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Progress bar if present */}
                    {prog.progress !== undefined && prog.progress !== null && (
                        <div className="mt-1 h-1 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                            <div
                                className="h-full bg-indigo-500 transition-all"
                                style={{ width: `${prog.progress * 100}%` }}
                            />
                        </div>
                    )}
                </div>
            ))}
        </div>
    );
}
