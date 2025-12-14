/**
 * Tool result view - shows a single tool call with special rendering for specific tools
 *
 * For deep_research: shows the full research structure (checklist, sources, etc.)
 * For other tools: shows input/output in a clean format
 */

import { useState } from 'react';
import {
    WrenchScrewdriverIcon,
    ArchiveBoxArrowDownIcon,
    ChevronDownIcon,
    ChevronRightIcon,
    CheckCircleIcon,
    ExclamationCircleIcon,
    MinusCircleIcon,
    MagnifyingGlassIcon,
    DocumentTextIcon,
    LinkIcon
} from '@heroicons/react/24/solid';
import { JsonRenderer } from '../../common';
import { ToolCall } from '../../../types/chat';

interface ToolResultViewProps {
    toolCall: ToolCall;
    onSaveAsAsset: (toolCall: ToolCall) => void;
}

// Deep research specific types
interface ChecklistItem {
    question: string;
    status: 'unfilled' | 'partial' | 'complete';
    findings: string[];
    sources: string[];
}

interface DeepResearchData {
    type: 'research_result';
    topic: string;
    goal: string;
    checklist: ChecklistItem[];
    sources: string[];
    iterations: number;
    synthesis?: string;
}

function isDeepResearchData(data: any): data is DeepResearchData {
    return data && data.type === 'research_result' && Array.isArray(data.checklist);
}

// Status icon component
function StatusIcon({ status }: { status: 'unfilled' | 'partial' | 'complete' }) {
    switch (status) {
        case 'complete':
            return <CheckCircleIcon className="h-5 w-5 text-green-500" />;
        case 'partial':
            return <MinusCircleIcon className="h-5 w-5 text-yellow-500" />;
        default:
            return <ExclamationCircleIcon className="h-5 w-5 text-gray-400" />;
    }
}

// Deep Research Result View
function DeepResearchResultView({ data }: { data: DeepResearchData }) {
    const [expandedItems, setExpandedItems] = useState<Set<number>>(new Set());
    const [showSources, setShowSources] = useState(false);

    const toggleItem = (index: number) => {
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

    const completedCount = data.checklist.filter(c => c.status === 'complete').length;
    const partialCount = data.checklist.filter(c => c.status === 'partial').length;

    return (
        <div className="space-y-6">
            {/* Research Overview */}
            <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 border border-blue-200 dark:border-blue-800">
                <div className="flex items-start gap-3">
                    <MagnifyingGlassIcon className="h-6 w-6 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
                    <div>
                        <h3 className="font-semibold text-gray-900 dark:text-white">{data.topic}</h3>
                        <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">{data.goal}</p>
                        <div className="flex items-center gap-4 mt-2 text-xs text-gray-500 dark:text-gray-400">
                            <span>{data.iterations} iterations</span>
                            <span>{data.sources.length} sources</span>
                            <span>{completedCount} complete, {partialCount} partial</span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Research Checklist */}
            <div>
                <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
                    <DocumentTextIcon className="h-4 w-4" />
                    Research Checklist
                </h4>
                <div className="space-y-2">
                    {data.checklist.map((item, idx) => (
                        <div key={idx} className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
                            <button
                                onClick={() => toggleItem(idx)}
                                className="w-full px-4 py-3 flex items-start gap-3 text-left hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
                            >
                                <StatusIcon status={item.status} />
                                <span className="flex-1 text-sm text-gray-900 dark:text-white">
                                    {item.question}
                                </span>
                                {item.findings.length > 0 && (
                                    expandedItems.has(idx) ? (
                                        <ChevronDownIcon className="h-4 w-4 text-gray-400" />
                                    ) : (
                                        <ChevronRightIcon className="h-4 w-4 text-gray-400" />
                                    )
                                )}
                            </button>
                            {expandedItems.has(idx) && item.findings.length > 0 && (
                                <div className="px-4 pb-3 pl-12">
                                    <ul className="space-y-2">
                                        {item.findings.map((finding, fIdx) => (
                                            <li key={fIdx} className="text-sm text-gray-600 dark:text-gray-300 flex gap-2">
                                                <span className="text-gray-400">•</span>
                                                <span>{finding}</span>
                                            </li>
                                        ))}
                                    </ul>
                                    {item.sources.length > 0 && (
                                        <div className="mt-2 text-xs text-gray-400">
                                            Sources: {item.sources.length} page(s)
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            </div>

            {/* Sources */}
            <div>
                <button
                    onClick={() => setShowSources(!showSources)}
                    className="flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 hover:text-gray-900 dark:hover:text-white"
                >
                    <LinkIcon className="h-4 w-4" />
                    Sources ({data.sources.length})
                    {showSources ? (
                        <ChevronDownIcon className="h-4 w-4" />
                    ) : (
                        <ChevronRightIcon className="h-4 w-4" />
                    )}
                </button>
                {showSources && (
                    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                        <ul className="space-y-2">
                            {data.sources.map((url, idx) => (
                                <li key={idx}>
                                    <a
                                        href={url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-sm text-blue-600 dark:text-blue-400 hover:underline break-all"
                                    >
                                        {url}
                                    </a>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>

            {/* Synthesis / Text Summary */}
            {data.synthesis && (
                <div>
                    <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
                        Synthesized Summary
                    </h4>
                    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                        <div className="prose prose-sm dark:prose-invert max-w-none">
                            <pre className="whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-300 font-sans">
                                {data.synthesis}
                            </pre>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

// Generic Tool Result View
function GenericToolResultView({ toolCall }: { toolCall: ToolCall }) {
    return (
        <div className="space-y-4">
            {/* Input */}
            <div>
                <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase mb-2">Input</h4>
                <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <JsonRenderer data={toolCall.input} />
                </div>
            </div>

            {/* Output */}
            <div>
                <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase mb-2">Output</h4>
                <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 max-h-96 overflow-y-auto">
                    {typeof toolCall.output === 'string' ? (
                        <pre className="whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-300">
                            {toolCall.output}
                        </pre>
                    ) : (
                        <JsonRenderer data={toolCall.output} />
                    )}
                </div>
            </div>
        </div>
    );
}

export default function ToolResultView({ toolCall, onSaveAsAsset }: ToolResultViewProps) {
    const displayName = toolCall.tool_name.replace(/_/g, ' ');

    // Check if this is a deep_research result with structured data
    const isDeepResearch = toolCall.tool_name === 'deep_research' &&
        typeof toolCall.output === 'object' &&
        isDeepResearchData(toolCall.output);

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <WrenchScrewdriverIcon className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                    <span className="font-semibold text-gray-900 dark:text-white capitalize">
                        {displayName}
                    </span>
                </div>
                <button
                    onClick={() => onSaveAsAsset(toolCall)}
                    className="flex items-center gap-1 px-3 py-1.5 text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-lg transition-colors"
                >
                    <ArchiveBoxArrowDownIcon className="h-4 w-4" />
                    Save as Asset
                </button>
            </div>

            {/* Content - either deep research view or generic view */}
            {isDeepResearch ? (
                <DeepResearchResultView
                    data={toolCall.output as DeepResearchData}
                />
            ) : (
                <GenericToolResultView toolCall={toolCall} />
            )}
        </div>
    );
}
