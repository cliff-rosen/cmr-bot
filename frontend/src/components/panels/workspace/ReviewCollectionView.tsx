/**
 * Review Collection View
 *
 * Custom workspace view for the collect_reviews tool results.
 * Shows the journey of collecting reviews with phases, steps, and artifacts.
 */

import { useState } from 'react';
import {
    CheckCircleIcon,
    XCircleIcon,
    ExclamationTriangleIcon,
    ChevronDownIcon,
    ChevronRightIcon,
    MagnifyingGlassIcon,
    GlobeAltIcon,
    StarIcon,
    ClockIcon,
    ExclamationCircleIcon,
    LinkIcon
} from '@heroicons/react/24/solid';
import { WorkspacePayload } from '../../../types/chat';

// =============================================================================
// Types
// =============================================================================

interface Step {
    action: 'search' | 'fetch';
    input: string;
    status: 'success' | 'failed' | 'blocked' | 'timeout';
    duration_ms: number;
    findings: string[];
    content_size?: number;
    was_js_rendered?: boolean;
    was_blocked?: boolean;
}

interface Phase {
    name: 'entity_resolution' | 'artifact_collection';
    status: 'success' | 'failed' | 'partial' | 'skipped';
    duration_ms: number;
    steps: Step[];
    conclusion: string;
}

interface Obstacle {
    type: string;
    description: string;
    impact: string;
    url?: string;
}

interface ToolCallStats {
    searches: { attempted: number; successful: number };
    fetches: { attempted: number; successful: number; blocked: number };
}

interface Journey {
    started_at: string;
    completed_at: string;
    duration_ms: number;
    phases: Phase[];
    tool_calls: ToolCallStats;
    obstacles: Obstacle[];
}

interface Entity {
    name: string;
    url: string;
    platform_id?: string;
    rating?: number;
    review_count?: number;
    match_confidence: 'exact' | 'probable' | 'uncertain';
    match_reason: string;
}

interface ReviewArtifact {
    rating?: number;
    text: string;
    author?: string;
    date?: string;
    url?: string;
}

interface RedditArtifact {
    text: string;
    author: string;
    subreddit: string;
    url: string;
    title?: string;
    score?: number;
    date?: string;
}

interface Analysis {
    sentiment: string;
    themes: string[];
    notable_quotes: string[];
}

interface Outcome {
    success: boolean;
    status: 'complete' | 'entity_not_found' | 'entity_ambiguous' | 'blocked' | 'partial' | 'error';
    confidence: 'high' | 'medium' | 'low';
    summary: string;
}

interface Request {
    business_name: string;
    location: string;
    source: string;
}

interface ReviewCollectionData {
    outcome: Outcome;
    request: Request;
    entity?: Entity;
    artifacts: (ReviewArtifact | RedditArtifact)[];
    journey: Journey;
    analysis?: Analysis;
}

interface ReviewCollectionViewProps {
    payload: WorkspacePayload;
    onSaveAsAsset: (payload: WorkspacePayload, andClose?: boolean) => void;
    isSaving?: boolean;
    onPayloadEdit: (payload: WorkspacePayload) => void;
}

// =============================================================================
// Helper Components
// =============================================================================

function StatusBadge({ status, confidence }: { status: string; confidence: string }) {
    const statusConfig: Record<string, { bg: string; text: string; icon: React.ReactNode }> = {
        complete: {
            bg: 'bg-green-100 dark:bg-green-900/30',
            text: 'text-green-700 dark:text-green-300',
            icon: <CheckCircleIcon className="h-4 w-4" />
        },
        partial: {
            bg: 'bg-yellow-100 dark:bg-yellow-900/30',
            text: 'text-yellow-700 dark:text-yellow-300',
            icon: <ExclamationTriangleIcon className="h-4 w-4" />
        },
        blocked: {
            bg: 'bg-orange-100 dark:bg-orange-900/30',
            text: 'text-orange-700 dark:text-orange-300',
            icon: <ExclamationCircleIcon className="h-4 w-4" />
        },
        entity_not_found: {
            bg: 'bg-red-100 dark:bg-red-900/30',
            text: 'text-red-700 dark:text-red-300',
            icon: <XCircleIcon className="h-4 w-4" />
        },
        entity_ambiguous: {
            bg: 'bg-red-100 dark:bg-red-900/30',
            text: 'text-red-700 dark:text-red-300',
            icon: <XCircleIcon className="h-4 w-4" />
        },
        error: {
            bg: 'bg-red-100 dark:bg-red-900/30',
            text: 'text-red-700 dark:text-red-300',
            icon: <XCircleIcon className="h-4 w-4" />
        }
    };

    const config = statusConfig[status] || statusConfig.error;

    return (
        <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-sm font-medium ${config.bg} ${config.text}`}>
            {config.icon}
            <span className="uppercase">{status.replace(/_/g, ' ')}</span>
            <span className="opacity-60">• {confidence}</span>
        </div>
    );
}

function StarRating({ rating }: { rating: number }) {
    const fullStars = Math.floor(rating);
    const hasHalf = rating % 1 >= 0.5;

    return (
        <div className="flex items-center gap-0.5">
            {[...Array(5)].map((_, i) => (
                <StarIcon
                    key={i}
                    className={`h-4 w-4 ${
                        i < fullStars
                            ? 'text-yellow-400'
                            : i === fullStars && hasHalf
                            ? 'text-yellow-400 opacity-50'
                            : 'text-gray-300 dark:text-gray-600'
                    }`}
                />
            ))}
            <span className="ml-1 text-sm font-medium text-gray-700 dark:text-gray-300">
                {rating.toFixed(1)}
            </span>
        </div>
    );
}

function PhaseView({ phase, defaultExpanded = false }: { phase: Phase; defaultExpanded?: boolean }) {
    const [expanded, setExpanded] = useState(defaultExpanded);

    const statusIcon = {
        success: <CheckCircleIcon className="h-5 w-5 text-green-500" />,
        failed: <XCircleIcon className="h-5 w-5 text-red-500" />,
        partial: <ExclamationTriangleIcon className="h-5 w-5 text-yellow-500" />,
        skipped: <ExclamationCircleIcon className="h-5 w-5 text-gray-400" />
    };

    const phaseName = phase.name === 'entity_resolution' ? 'Entity Resolution' : 'Artifact Collection';

    return (
        <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
            <button
                onClick={() => setExpanded(!expanded)}
                className="w-full px-4 py-3 flex items-center justify-between bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-750 transition-colors"
            >
                <div className="flex items-center gap-3">
                    {statusIcon[phase.status]}
                    <span className="font-medium text-gray-900 dark:text-white">{phaseName}</span>
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                        {phase.steps.length} steps • {(phase.duration_ms / 1000).toFixed(1)}s
                    </span>
                </div>
                {expanded ? (
                    <ChevronDownIcon className="h-5 w-5 text-gray-400" />
                ) : (
                    <ChevronRightIcon className="h-5 w-5 text-gray-400" />
                )}
            </button>

            {expanded && (
                <div className="border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
                    {/* Steps */}
                    <div className="p-4 space-y-2">
                        {phase.steps.map((step, idx) => (
                            <StepView key={idx} step={step} index={idx + 1} />
                        ))}
                    </div>

                    {/* Conclusion */}
                    {phase.conclusion && (
                        <div className="px-4 pb-4">
                            <div className="text-sm text-gray-600 dark:text-gray-400 bg-white dark:bg-gray-800 rounded-lg px-3 py-2 border border-gray-200 dark:border-gray-700">
                                <span className="font-medium">Conclusion:</span> {phase.conclusion}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

function StepView({ step, index }: { step: Step; index: number }) {
    const [showFindings, setShowFindings] = useState(false);

    const actionIcon = step.action === 'search' ? (
        <MagnifyingGlassIcon className="h-4 w-4 text-blue-500" />
    ) : (
        <GlobeAltIcon className="h-4 w-4 text-purple-500" />
    );

    const statusColor = {
        success: 'text-green-600 dark:text-green-400',
        failed: 'text-red-600 dark:text-red-400',
        blocked: 'text-orange-600 dark:text-orange-400',
        timeout: 'text-yellow-600 dark:text-yellow-400'
    };

    const inputDisplay = step.input.length > 60 ? step.input.slice(0, 60) + '...' : step.input;

    return (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
            <div
                className="px-3 py-2 flex items-center gap-2 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-750"
                onClick={() => step.findings.length > 0 && setShowFindings(!showFindings)}
            >
                <span className="text-xs font-mono text-gray-400 w-5">{index}</span>
                {actionIcon}
                <span className="flex-1 text-sm text-gray-700 dark:text-gray-300 font-mono truncate">
                    {inputDisplay}
                </span>
                <span className={`text-xs font-medium ${statusColor[step.status]}`}>
                    {step.status}
                </span>
                <span className="text-xs text-gray-400">
                    {step.duration_ms}ms
                </span>
                {step.content_size && (
                    <span className="text-xs text-gray-400">
                        {(step.content_size / 1000).toFixed(1)}KB
                    </span>
                )}
                {step.was_js_rendered && (
                    <span className="text-xs text-purple-500">JS</span>
                )}
                {step.findings.length > 0 && (
                    showFindings ? (
                        <ChevronDownIcon className="h-4 w-4 text-gray-400" />
                    ) : (
                        <ChevronRightIcon className="h-4 w-4 text-gray-400" />
                    )
                )}
            </div>

            {showFindings && step.findings.length > 0 && (
                <div className="px-3 pb-2 pl-10">
                    <ul className="text-xs text-gray-600 dark:text-gray-400 space-y-1">
                        {step.findings.map((finding, idx) => (
                            <li key={idx} className="flex gap-1">
                                <span className="text-gray-400">-</span>
                                <span>{finding}</span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
}

function ReviewArtifactView({ artifact, index }: { artifact: ReviewArtifact; index: number }) {
    const [expanded, setExpanded] = useState(false);
    const textPreview = artifact.text.length > 200 ? artifact.text.slice(0, 200) + '...' : artifact.text;

    return (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                    {artifact.rating && <StarRating rating={artifact.rating} />}
                    {artifact.author && (
                        <span className="text-sm text-gray-600 dark:text-gray-400">
                            by {artifact.author}
                        </span>
                    )}
                </div>
                {artifact.date && (
                    <span className="text-xs text-gray-400">{artifact.date}</span>
                )}
            </div>
            <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                {expanded ? artifact.text : textPreview}
            </p>
            {artifact.text.length > 200 && (
                <button
                    onClick={() => setExpanded(!expanded)}
                    className="mt-2 text-xs text-blue-600 dark:text-blue-400 hover:underline"
                >
                    {expanded ? 'Show less' : 'Show more'}
                </button>
            )}
        </div>
    );
}

function ObstacleView({ obstacle }: { obstacle: Obstacle }) {
    return (
        <div className="flex items-start gap-2 p-3 bg-orange-50 dark:bg-orange-900/20 rounded-lg border border-orange-200 dark:border-orange-800">
            <ExclamationTriangleIcon className="h-5 w-5 text-orange-500 flex-shrink-0 mt-0.5" />
            <div>
                <div className="text-sm font-medium text-orange-700 dark:text-orange-300">
                    {obstacle.type.replace(/_/g, ' ')}
                </div>
                <div className="text-sm text-orange-600 dark:text-orange-400">
                    {obstacle.description}
                </div>
                <div className="text-xs text-orange-500 dark:text-orange-500 mt-1">
                    Impact: {obstacle.impact}
                </div>
            </div>
        </div>
    );
}

// =============================================================================
// Main Component
// =============================================================================

export default function ReviewCollectionView({
    payload,
    onSaveAsAsset,
    isSaving = false,
}: ReviewCollectionViewProps) {
    const [showJourney, setShowJourney] = useState(true);
    const [showArtifacts, setShowArtifacts] = useState(true);
    const [showAnalysis, setShowAnalysis] = useState(true);

    // Parse the data from the payload
    const data: ReviewCollectionData | null = payload.data?.data || payload.data;

    if (!data || !data.outcome) {
        return (
            <div className="p-4 text-gray-500 dark:text-gray-400">
                Invalid review collection data
            </div>
        );
    }

    const { outcome, request, entity, artifacts, journey, analysis } = data;

    return (
        <div className="space-y-6">
            {/* Header Card */}
            <div className={`rounded-lg border p-4 ${
                outcome.success
                    ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'
                    : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
            }`}>
                <div className="flex items-start justify-between mb-3">
                    <div>
                        <div className="flex items-center gap-2 mb-1">
                            <span className="text-lg font-semibold text-gray-900 dark:text-white uppercase">
                                {request.source}
                            </span>
                            <span className="text-gray-500 dark:text-gray-400">Review Collection</span>
                        </div>
                        <div className="text-sm text-gray-600 dark:text-gray-400">
                            {request.business_name} • {request.location}
                        </div>
                    </div>
                    <StatusBadge status={outcome.status} confidence={outcome.confidence} />
                </div>
                <p className="text-sm text-gray-700 dark:text-gray-300">{outcome.summary}</p>
            </div>

            {/* Entity Card (if found) */}
            {entity && (
                <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                        <CheckCircleIcon className="h-4 w-4 text-green-500" />
                        Entity Verified
                    </h3>
                    <div className="space-y-2">
                        <div className="flex items-center justify-between">
                            <span className="font-medium text-gray-900 dark:text-white">{entity.name}</span>
                            {entity.rating && <StarRating rating={entity.rating} />}
                        </div>
                        <a
                            href={entity.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1"
                        >
                            <LinkIcon className="h-3 w-3" />
                            {entity.url}
                        </a>
                        <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
                            {entity.review_count && <span>{entity.review_count} reviews</span>}
                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                                entity.match_confidence === 'exact'
                                    ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                                    : entity.match_confidence === 'probable'
                                    ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300'
                                    : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
                            }`}>
                                {entity.match_confidence} match
                            </span>
                        </div>
                        {entity.match_reason && (
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                                {entity.match_reason}
                            </p>
                        )}
                    </div>
                </div>
            )}

            {/* Journey Section */}
            <div>
                <button
                    onClick={() => setShowJourney(!showJourney)}
                    className="flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 hover:text-gray-900 dark:hover:text-white"
                >
                    <ClockIcon className="h-4 w-4" />
                    Journey ({(journey.duration_ms / 1000).toFixed(1)}s •{' '}
                    {journey.tool_calls.searches.attempted} searches •{' '}
                    {journey.tool_calls.fetches.attempted} fetches)
                    {showJourney ? (
                        <ChevronDownIcon className="h-4 w-4" />
                    ) : (
                        <ChevronRightIcon className="h-4 w-4" />
                    )}
                </button>

                {showJourney && (
                    <div className="space-y-3">
                        {/* Obstacles */}
                        {journey.obstacles.length > 0 && (
                            <div className="space-y-2">
                                {journey.obstacles.map((obs, idx) => (
                                    <ObstacleView key={idx} obstacle={obs} />
                                ))}
                            </div>
                        )}

                        {/* Phases */}
                        {journey.phases.map((phase, idx) => (
                            <PhaseView
                                key={idx}
                                phase={phase}
                                defaultExpanded={idx === 0}
                            />
                        ))}

                        {/* Stats */}
                        <div className="grid grid-cols-2 gap-4 text-sm">
                            <div className="bg-gray-100 dark:bg-gray-800 rounded-lg p-3">
                                <div className="text-gray-500 dark:text-gray-400 mb-1">Searches</div>
                                <div className="text-xl font-semibold text-gray-900 dark:text-white">
                                    {journey.tool_calls.searches.successful}/{journey.tool_calls.searches.attempted}
                                </div>
                            </div>
                            <div className="bg-gray-100 dark:bg-gray-800 rounded-lg p-3">
                                <div className="text-gray-500 dark:text-gray-400 mb-1">Fetches</div>
                                <div className="text-xl font-semibold text-gray-900 dark:text-white">
                                    {journey.tool_calls.fetches.successful}/{journey.tool_calls.fetches.attempted}
                                    {journey.tool_calls.fetches.blocked > 0 && (
                                        <span className="text-sm text-orange-500 ml-2">
                                            ({journey.tool_calls.fetches.blocked} blocked)
                                        </span>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Artifacts Section */}
            {artifacts && artifacts.length > 0 && (
                <div>
                    <button
                        onClick={() => setShowArtifacts(!showArtifacts)}
                        className="flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 hover:text-gray-900 dark:hover:text-white"
                    >
                        <StarIcon className="h-4 w-4" />
                        Reviews ({artifacts.length} collected)
                        {showArtifacts ? (
                            <ChevronDownIcon className="h-4 w-4" />
                        ) : (
                            <ChevronRightIcon className="h-4 w-4" />
                        )}
                    </button>

                    {showArtifacts && (
                        <div className="space-y-3">
                            {artifacts.map((artifact, idx) => (
                                <ReviewArtifactView
                                    key={idx}
                                    artifact={artifact as ReviewArtifact}
                                    index={idx + 1}
                                />
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Analysis Section */}
            {analysis && (analysis.sentiment || analysis.themes.length > 0) && (
                <div>
                    <button
                        onClick={() => setShowAnalysis(!showAnalysis)}
                        className="flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 hover:text-gray-900 dark:hover:text-white"
                    >
                        Analysis
                        {showAnalysis ? (
                            <ChevronDownIcon className="h-4 w-4" />
                        ) : (
                            <ChevronRightIcon className="h-4 w-4" />
                        )}
                    </button>

                    {showAnalysis && (
                        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-3">
                            {analysis.sentiment && (
                                <div>
                                    <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase mb-1">
                                        Sentiment
                                    </div>
                                    <p className="text-sm text-gray-700 dark:text-gray-300">
                                        {analysis.sentiment}
                                    </p>
                                </div>
                            )}
                            {analysis.themes.length > 0 && (
                                <div>
                                    <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase mb-1">
                                        Key Themes
                                    </div>
                                    <div className="flex flex-wrap gap-2">
                                        {analysis.themes.map((theme, idx) => (
                                            <span
                                                key={idx}
                                                className="px-2 py-1 text-xs bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded"
                                            >
                                                {theme}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                            {analysis.notable_quotes.length > 0 && (
                                <div>
                                    <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase mb-1">
                                        Notable Quotes
                                    </div>
                                    <ul className="space-y-1">
                                        {analysis.notable_quotes.map((quote, idx) => (
                                            <li
                                                key={idx}
                                                className="text-sm text-gray-600 dark:text-gray-400 italic"
                                            >
                                                "{quote}"
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
