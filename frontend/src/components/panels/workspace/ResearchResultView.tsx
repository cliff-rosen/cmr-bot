/**
 * ResearchResultView - Display completed research results from deep_research tool
 *
 * Shows:
 * - Research goal and topic
 * - Synthesized answer (markdown)
 * - Checklist progress and findings
 * - Sources and queries used
 */

import { useState } from 'react';
import {
    BeakerIcon,
    CheckCircleIcon,
    ExclamationCircleIcon,
    ClockIcon,
    ChevronRightIcon,
    ChevronDownIcon,
    LinkIcon,
    MagnifyingGlassIcon,
    ArchiveBoxArrowDownIcon
} from '@heroicons/react/24/solid';
import { MarkdownRenderer } from '../../common';
import { WorkspacePayload, ResearchChecklistItem } from '../../../types/chat';

interface ResearchResultViewProps {
    payload: WorkspacePayload;
    onSaveAsAsset: (payload: WorkspacePayload, andClose?: boolean) => void;
    isSaving?: boolean;
}

// Status colors and icons for checklist items
const STATUS_CONFIG = {
    complete: {
        icon: CheckCircleIcon,
        color: 'text-green-500',
        bg: 'bg-green-50 dark:bg-green-900/20',
        border: 'border-green-200 dark:border-green-800',
        label: 'Complete'
    },
    partial: {
        icon: ExclamationCircleIcon,
        color: 'text-yellow-500',
        bg: 'bg-yellow-50 dark:bg-yellow-900/20',
        border: 'border-yellow-200 dark:border-yellow-800',
        label: 'Partial'
    },
    unfilled: {
        icon: ClockIcon,
        color: 'text-gray-400',
        bg: 'bg-gray-50 dark:bg-gray-800',
        border: 'border-gray-200 dark:border-gray-700',
        label: 'Unfilled'
    }
};

export default function ResearchResultView({
    payload,
    onSaveAsAsset,
    isSaving = false
}: ResearchResultViewProps) {
    const [showChecklist, setShowChecklist] = useState(false);
    const [showSources, setShowSources] = useState(false);
    const [showQueries, setShowQueries] = useState(false);
    const [expandedItems, setExpandedItems] = useState<Set<number>>(new Set());

    // Extract research result data - it may be in research_result_data or directly on payload
    const data = payload.research_result_data || {
        topic: (payload as any).topic || payload.title,
        goal: (payload as any).goal || '',
        synthesis: (payload as any).synthesis || payload.content || '',
        checklist: (payload as any).checklist || [],
        checklist_summary: (payload as any).checklist_summary || { unfilled: 0, partial: 0, complete: 0 },
        sources: (payload as any).sources || [],
        iterations: (payload as any).iterations || 0,
        queries_used: (payload as any).queries_used || []
    };

    const { topic, goal, synthesis, checklist, checklist_summary, sources, iterations, queries_used } = data;

    const totalItems = checklist_summary.unfilled + checklist_summary.partial + checklist_summary.complete;
    const completionPercent = totalItems > 0 ? Math.round((checklist_summary.complete / totalItems) * 100) : 0;

    const toggleItemExpanded = (index: number) => {
        setExpandedItems(prev => {
            const next = new Set(prev);
            if (next.has(index)) {
                next.delete(index);
            } else {
                next.add(index);
            }
            return next;
        });
    };

    return (
        <div className="flex flex-col h-full bg-white dark:bg-gray-900">
            {/* Header */}
            <div className="flex-shrink-0 px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3">
                        <BeakerIcon className="h-6 w-6 text-purple-500" />
                        <div>
                            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                                {payload.title || `Research: ${topic}`}
                            </h2>
                            {goal && (
                                <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                                    {goal}
                                </p>
                            )}
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => onSaveAsAsset(payload, false)}
                            disabled={isSaving}
                            className="flex items-center gap-1 px-3 py-1.5 text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            title="Save as asset"
                        >
                            {isSaving ? (
                                <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                            ) : (
                                <ArchiveBoxArrowDownIcon className="h-4 w-4" />
                            )}
                            {isSaving ? 'Saving...' : 'Save as Asset'}
                        </button>
                    </div>
                </div>

                {/* Stats bar */}
                <div className="flex items-center gap-6 text-sm">
                    {/* Completion progress */}
                    <div className="flex items-center gap-2">
                        <div className="w-24 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                            <div
                                className="h-full bg-purple-500 rounded-full transition-all"
                                style={{ width: `${completionPercent}%` }}
                            />
                        </div>
                        <span className="text-gray-600 dark:text-gray-400">
                            {completionPercent}% complete
                        </span>
                    </div>

                    {/* Stats pills */}
                    <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 rounded text-xs">
                            {checklist_summary.complete} complete
                        </span>
                        {checklist_summary.partial > 0 && (
                            <span className="px-2 py-0.5 bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300 rounded text-xs">
                                {checklist_summary.partial} partial
                            </span>
                        )}
                        {checklist_summary.unfilled > 0 && (
                            <span className="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded text-xs">
                                {checklist_summary.unfilled} unfilled
                            </span>
                        )}
                    </div>

                    {/* Iterations */}
                    <span className="text-gray-500 dark:text-gray-400">
                        {iterations} iteration{iterations !== 1 ? 's' : ''}
                    </span>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {/* Synthesis/Answer */}
                <div className="prose prose-sm dark:prose-invert max-w-none">
                    <MarkdownRenderer content={synthesis} />
                </div>

                {/* Checklist section */}
                <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
                    <button
                        onClick={() => setShowChecklist(!showChecklist)}
                        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                    >
                        <div className="flex items-center gap-2">
                            {showChecklist ? (
                                <ChevronDownIcon className="h-4 w-4 text-gray-500" />
                            ) : (
                                <ChevronRightIcon className="h-4 w-4 text-gray-500" />
                            )}
                            <span className="font-medium text-gray-900 dark:text-white">
                                Research Checklist
                            </span>
                            <span className="text-sm text-gray-500">
                                ({totalItems} items)
                            </span>
                        </div>
                    </button>

                    {showChecklist && checklist.length > 0 && (
                        <div className="divide-y divide-gray-200 dark:divide-gray-700">
                            {checklist.map((item: ResearchChecklistItem, index: number) => {
                                const config = STATUS_CONFIG[item.status];
                                const StatusIcon = config.icon;
                                const isExpanded = expandedItems.has(index);

                                return (
                                    <div key={index} className={`${config.bg}`}>
                                        <button
                                            onClick={() => toggleItemExpanded(index)}
                                            className="w-full flex items-start gap-3 p-4 text-left hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                                        >
                                            <StatusIcon className={`h-5 w-5 ${config.color} flex-shrink-0 mt-0.5`} />
                                            <div className="flex-1 min-w-0">
                                                <p className="font-medium text-gray-900 dark:text-white">
                                                    {item.question}
                                                </p>
                                                <p className="text-xs text-gray-500 mt-1">
                                                    {item.findings.length} finding{item.findings.length !== 1 ? 's' : ''}
                                                    {item.sources.length > 0 && ` from ${item.sources.length} source${item.sources.length !== 1 ? 's' : ''}`}
                                                </p>
                                            </div>
                                            {isExpanded ? (
                                                <ChevronDownIcon className="h-4 w-4 text-gray-400 flex-shrink-0" />
                                            ) : (
                                                <ChevronRightIcon className="h-4 w-4 text-gray-400 flex-shrink-0" />
                                            )}
                                        </button>

                                        {/* Expanded findings */}
                                        {isExpanded && item.findings.length > 0 && (
                                            <div className="px-4 pb-4 pl-12 space-y-2">
                                                {item.findings.map((finding, fIndex) => (
                                                    <div
                                                        key={fIndex}
                                                        className="p-3 bg-white dark:bg-gray-900 rounded-lg text-sm text-gray-700 dark:text-gray-300"
                                                    >
                                                        {finding}
                                                    </div>
                                                ))}
                                                {item.sources.length > 0 && (
                                                    <div className="flex flex-wrap gap-2 mt-2">
                                                        {item.sources.map((source, sIndex) => (
                                                            <span
                                                                key={sIndex}
                                                                className="inline-flex items-center gap-1 px-2 py-1 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 rounded text-xs"
                                                            >
                                                                <LinkIcon className="h-3 w-3" />
                                                                {source.length > 50 ? source.slice(0, 50) + '...' : source}
                                                            </span>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>

                {/* Sources section */}
                {sources.length > 0 && (
                    <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
                        <button
                            onClick={() => setShowSources(!showSources)}
                            className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                        >
                            <div className="flex items-center gap-2">
                                {showSources ? (
                                    <ChevronDownIcon className="h-4 w-4 text-gray-500" />
                                ) : (
                                    <ChevronRightIcon className="h-4 w-4 text-gray-500" />
                                )}
                                <LinkIcon className="h-4 w-4 text-blue-500" />
                                <span className="font-medium text-gray-900 dark:text-white">
                                    Sources
                                </span>
                                <span className="text-sm text-gray-500">
                                    ({sources.length})
                                </span>
                            </div>
                        </button>

                        {showSources && (
                            <div className="p-4 space-y-2">
                                {sources.map((source: string, index: number) => (
                                    <div
                                        key={index}
                                        className="flex items-center gap-2 p-2 bg-gray-50 dark:bg-gray-800 rounded"
                                    >
                                        <LinkIcon className="h-4 w-4 text-blue-500 flex-shrink-0" />
                                        {source.startsWith('http') ? (
                                            <a
                                                href={source}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="text-sm text-blue-600 dark:text-blue-400 hover:underline truncate"
                                            >
                                                {source}
                                            </a>
                                        ) : (
                                            <span className="text-sm text-gray-700 dark:text-gray-300 truncate">
                                                {source}
                                            </span>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {/* Queries section */}
                {queries_used.length > 0 && (
                    <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
                        <button
                            onClick={() => setShowQueries(!showQueries)}
                            className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                        >
                            <div className="flex items-center gap-2">
                                {showQueries ? (
                                    <ChevronDownIcon className="h-4 w-4 text-gray-500" />
                                ) : (
                                    <ChevronRightIcon className="h-4 w-4 text-gray-500" />
                                )}
                                <MagnifyingGlassIcon className="h-4 w-4 text-purple-500" />
                                <span className="font-medium text-gray-900 dark:text-white">
                                    Search Queries
                                </span>
                                <span className="text-sm text-gray-500">
                                    ({queries_used.length})
                                </span>
                            </div>
                        </button>

                        {showQueries && (
                            <div className="p-4 flex flex-wrap gap-2">
                                {queries_used.map((query: string, index: number) => (
                                    <span
                                        key={index}
                                        className="px-3 py-1.5 bg-purple-50 dark:bg-purple-900/20 text-purple-700 dark:text-purple-300 rounded-full text-sm"
                                    >
                                        {query}
                                    </span>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
