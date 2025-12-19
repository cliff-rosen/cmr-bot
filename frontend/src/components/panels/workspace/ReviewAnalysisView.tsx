/**
 * Review Analysis View
 *
 * Custom workspace view for the analyze_reviews tool results.
 * Shows human-intuition-based analysis with verdict, themes, and anomalies.
 */

import { useState } from 'react';
import {
    CheckCircleIcon,
    XCircleIcon,
    ExclamationTriangleIcon,
    ChevronDownIcon,
    ChevronRightIcon,
    StarIcon,
    ShieldCheckIcon,
    ShieldExclamationIcon,
    ExclamationCircleIcon,
    ArrowTrendingUpIcon,
    ArrowTrendingDownIcon,
    MinusIcon,
    QuestionMarkCircleIcon,
    LinkIcon,
    ClockIcon
} from '@heroicons/react/24/solid';
import { WorkspacePayload, ReviewAnalysisData, ComplaintTheme, AnomalyFlag, HumanIntuitionVerdict, RatingDistribution, ReviewArtifact } from '../../../types/chat';

interface ReviewAnalysisViewProps {
    payload: WorkspacePayload;
    onSaveAsAsset: (payload: WorkspacePayload, andClose?: boolean) => void;
    isSaving?: boolean;
    onPayloadEdit: (payload: WorkspacePayload) => void;
}

// =============================================================================
// Helper Components
// =============================================================================

function VerdictBanner({ verdict }: { verdict: HumanIntuitionVerdict }) {
    const config: Record<string, { bg: string; border: string; icon: React.ReactNode; label: string }> = {
        trustworthy: {
            bg: 'bg-green-50 dark:bg-green-900/20',
            border: 'border-green-200 dark:border-green-800',
            icon: <ShieldCheckIcon className="h-8 w-8 text-green-500" />,
            label: 'TRUSTWORTHY'
        },
        proceed_with_caution: {
            bg: 'bg-yellow-50 dark:bg-yellow-900/20',
            border: 'border-yellow-200 dark:border-yellow-800',
            icon: <ExclamationTriangleIcon className="h-8 w-8 text-yellow-500" />,
            label: 'PROCEED WITH CAUTION'
        },
        significant_concerns: {
            bg: 'bg-orange-50 dark:bg-orange-900/20',
            border: 'border-orange-200 dark:border-orange-800',
            icon: <ShieldExclamationIcon className="h-8 w-8 text-orange-500" />,
            label: 'SIGNIFICANT CONCERNS'
        },
        avoid: {
            bg: 'bg-red-50 dark:bg-red-900/20',
            border: 'border-red-200 dark:border-red-800',
            icon: <XCircleIcon className="h-8 w-8 text-red-500" />,
            label: 'AVOID'
        }
    };

    const c = config[verdict.recommendation] || config.proceed_with_caution;

    // Health score color
    const scoreColor = verdict.overall_health_score >= 80
        ? 'text-green-600 dark:text-green-400'
        : verdict.overall_health_score >= 60
        ? 'text-yellow-600 dark:text-yellow-400'
        : verdict.overall_health_score >= 40
        ? 'text-orange-600 dark:text-orange-400'
        : 'text-red-600 dark:text-red-400';

    return (
        <div className={`rounded-lg border-2 p-6 ${c.bg} ${c.border}`}>
            <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-4">
                    {c.icon}
                    <div>
                        <div className="text-xl font-bold text-gray-900 dark:text-white">
                            {c.label}
                        </div>
                        <div className="text-sm text-gray-500 dark:text-gray-400">
                            {Math.round(verdict.confidence * 100)}% confidence
                        </div>
                    </div>
                </div>
                <div className="text-right">
                    <div className={`text-4xl font-bold ${scoreColor}`}>
                        {verdict.overall_health_score}
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                        Health Score
                    </div>
                </div>
            </div>
            <p className="text-gray-700 dark:text-gray-300">{verdict.summary}</p>

            {/* Red Flags */}
            {verdict.red_flags && verdict.red_flags.length > 0 && (
                <div className="mt-4 p-3 bg-red-100 dark:bg-red-900/30 rounded-lg border border-red-200 dark:border-red-800">
                    <div className="text-sm font-semibold text-red-700 dark:text-red-300 mb-2 flex items-center gap-2">
                        <XCircleIcon className="h-4 w-4" />
                        RED FLAGS
                    </div>
                    <ul className="text-sm text-red-600 dark:text-red-400 space-y-1">
                        {verdict.red_flags.map((flag, idx) => (
                            <li key={idx}>- {flag}</li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
}

function RatingDistributionBar({ distribution }: { distribution: RatingDistribution }) {
    const bars = [
        { stars: 5, count: distribution.stars_5, color: 'bg-green-500' },
        { stars: 4, count: distribution.stars_4, color: 'bg-green-400' },
        { stars: 3, count: distribution.stars_3, color: 'bg-yellow-400' },
        { stars: 2, count: distribution.stars_2, color: 'bg-orange-400' },
        { stars: 1, count: distribution.stars_1, color: 'bg-red-400' }
    ];

    const maxCount = Math.max(...bars.map(b => b.count), 1);

    return (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-4">
                Rating Distribution
            </h3>
            <div className="space-y-2">
                {bars.map(({ stars, count, color }) => {
                    const percent = distribution.total > 0 ? (count / distribution.total * 100) : 0;
                    const width = maxCount > 0 ? (count / maxCount * 100) : 0;

                    return (
                        <div key={stars} className="flex items-center gap-2">
                            <div className="w-12 flex items-center gap-1 text-sm text-gray-600 dark:text-gray-400">
                                {stars}
                                <StarIcon className="h-3 w-3 text-yellow-400" />
                            </div>
                            <div className="flex-1 h-5 bg-gray-100 dark:bg-gray-700 rounded overflow-hidden">
                                <div
                                    className={`h-full ${color} transition-all duration-500`}
                                    style={{ width: `${width}%` }}
                                />
                            </div>
                            <div className="w-20 text-right text-sm text-gray-600 dark:text-gray-400">
                                {count} ({percent.toFixed(1)}%)
                            </div>
                        </div>
                    );
                })}
            </div>
            <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700 grid grid-cols-2 gap-4 text-sm">
                <div>
                    <span className="text-gray-500 dark:text-gray-400">Negative (1-2 star): </span>
                    <span className="font-medium text-red-600 dark:text-red-400">
                        {distribution.percent_negative.toFixed(1)}%
                    </span>
                </div>
                <div>
                    <span className="text-gray-500 dark:text-gray-400">Positive (4-5 star): </span>
                    <span className="font-medium text-green-600 dark:text-green-400">
                        {distribution.percent_positive.toFixed(1)}%
                    </span>
                </div>
            </div>
        </div>
    );
}

function ComplaintThemeCard({ theme, index }: { theme: ComplaintTheme; index: number }) {
    const [expanded, setExpanded] = useState(false);

    const severityConfig: Record<string, { bg: string; text: string; label: string }> = {
        critical: {
            bg: 'bg-red-100 dark:bg-red-900/30',
            text: 'text-red-700 dark:text-red-300',
            label: 'CRITICAL'
        },
        moderate: {
            bg: 'bg-yellow-100 dark:bg-yellow-900/30',
            text: 'text-yellow-700 dark:text-yellow-300',
            label: 'MODERATE'
        },
        minor: {
            bg: 'bg-gray-100 dark:bg-gray-700',
            text: 'text-gray-600 dark:text-gray-400',
            label: 'MINOR'
        }
    };

    const trendIcon: Record<string, React.ReactNode> = {
        increasing: <ArrowTrendingUpIcon className="h-4 w-4 text-red-500" />,
        decreasing: <ArrowTrendingDownIcon className="h-4 w-4 text-green-500" />,
        stable: <MinusIcon className="h-4 w-4 text-gray-400" />,
        unknown: <QuestionMarkCircleIcon className="h-4 w-4 text-gray-400" />
    };

    const severity = severityConfig[theme.severity] || severityConfig.moderate;

    return (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
            <button
                onClick={() => setExpanded(!expanded)}
                className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-750 transition-colors"
            >
                <div className="flex items-center gap-3">
                    <span className="text-lg font-bold text-gray-400">{index}.</span>
                    <span className="font-medium text-gray-900 dark:text-white">{theme.theme}</span>
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${severity.bg} ${severity.text}`}>
                        {severity.label}
                    </span>
                </div>
                <div className="flex items-center gap-3">
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                        {theme.frequency} mentions
                    </span>
                    {trendIcon[theme.recent_trend]}
                    {expanded ? (
                        <ChevronDownIcon className="h-5 w-5 text-gray-400" />
                    ) : (
                        <ChevronRightIcon className="h-5 w-5 text-gray-400" />
                    )}
                </div>
            </button>

            {expanded && theme.example_quotes.length > 0 && (
                <div className="px-4 pb-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
                    <div className="pt-3 space-y-2">
                        <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                            Example Quotes
                        </div>
                        {theme.example_quotes.map((quote, idx) => (
                            <p key={idx} className="text-sm text-gray-600 dark:text-gray-400 italic pl-3 border-l-2 border-gray-300 dark:border-gray-600">
                                "{quote}"
                            </p>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

function AnomalyCard({ anomaly }: { anomaly: AnomalyFlag }) {
    const [expanded, setExpanded] = useState(false);

    const confidenceColor: Record<string, string> = {
        high: 'text-red-600 dark:text-red-400',
        medium: 'text-orange-600 dark:text-orange-400',
        low: 'text-yellow-600 dark:text-yellow-400'
    };

    const typeLabels: Record<string, string> = {
        fake_positive: 'Possible Fake Reviews',
        review_burst: 'Review Burst Detected',
        generic_text: 'Generic/Templated Text',
        competitor_attack: 'Possible Competitor Attack',
        incentivized: 'Incentivized Reviews'
    };

    return (
        <div className="bg-orange-50 dark:bg-orange-900/20 rounded-lg border border-orange-200 dark:border-orange-800 overflow-hidden">
            <button
                onClick={() => setExpanded(!expanded)}
                className="w-full px-4 py-3 flex items-start justify-between hover:bg-orange-100 dark:hover:bg-orange-900/30 transition-colors"
            >
                <div className="flex items-start gap-3">
                    <ExclamationTriangleIcon className="h-5 w-5 text-orange-500 mt-0.5" />
                    <div className="text-left">
                        <div className="font-medium text-orange-700 dark:text-orange-300">
                            {typeLabels[anomaly.type] || anomaly.type}
                        </div>
                        <div className="text-sm text-orange-600 dark:text-orange-400">
                            {anomaly.description}
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <span className={`text-xs font-medium ${confidenceColor[anomaly.confidence]}`}>
                        {anomaly.confidence.toUpperCase()} confidence
                    </span>
                    {anomaly.evidence.length > 0 && (
                        expanded ? (
                            <ChevronDownIcon className="h-4 w-4 text-orange-400" />
                        ) : (
                            <ChevronRightIcon className="h-4 w-4 text-orange-400" />
                        )
                    )}
                </div>
            </button>

            {expanded && anomaly.evidence.length > 0 && (
                <div className="px-4 pb-3 border-t border-orange-200 dark:border-orange-800">
                    <div className="pt-3">
                        <div className="text-xs font-medium text-orange-500 mb-2">Evidence:</div>
                        <ul className="text-sm text-orange-600 dark:text-orange-400 space-y-1">
                            {anomaly.evidence.map((e, idx) => (
                                <li key={idx}>- {e}</li>
                            ))}
                        </ul>
                    </div>
                </div>
            )}
        </div>
    );
}

function KeyFindingsGrid({ verdict }: { verdict: HumanIntuitionVerdict }) {
    return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Key Concerns */}
            <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                <h4 className="text-sm font-semibold text-red-600 dark:text-red-400 mb-3 flex items-center gap-2">
                    <XCircleIcon className="h-4 w-4" />
                    Key Concerns
                </h4>
                {verdict.key_concerns.length > 0 ? (
                    <ul className="text-sm text-gray-700 dark:text-gray-300 space-y-2">
                        {verdict.key_concerns.map((concern, idx) => (
                            <li key={idx} className="flex gap-2">
                                <span className="text-red-400">-</span>
                                <span>{concern}</span>
                            </li>
                        ))}
                    </ul>
                ) : (
                    <p className="text-sm text-gray-500 dark:text-gray-400 italic">
                        No significant concerns identified
                    </p>
                )}
            </div>

            {/* Positive Signals */}
            <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                <h4 className="text-sm font-semibold text-green-600 dark:text-green-400 mb-3 flex items-center gap-2">
                    <CheckCircleIcon className="h-4 w-4" />
                    Positive Signals
                </h4>
                {verdict.positive_signals.length > 0 ? (
                    <ul className="text-sm text-gray-700 dark:text-gray-300 space-y-2">
                        {verdict.positive_signals.map((signal, idx) => (
                            <li key={idx} className="flex gap-2">
                                <span className="text-green-400">+</span>
                                <span>{signal}</span>
                            </li>
                        ))}
                    </ul>
                ) : (
                    <p className="text-sm text-gray-500 dark:text-gray-400 italic">
                        No notable positives identified
                    </p>
                )}
            </div>
        </div>
    );
}

function ReviewList({ reviews, title, defaultExpanded = false }: { reviews: ReviewArtifact[]; title: string; defaultExpanded?: boolean }) {
    const [expanded, setExpanded] = useState(defaultExpanded);
    const [showAll, setShowAll] = useState(false);

    const displayReviews = showAll ? reviews : reviews.slice(0, 5);

    return (
        <div>
            <button
                onClick={() => setExpanded(!expanded)}
                className="flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 hover:text-gray-900 dark:hover:text-white"
            >
                <StarIcon className="h-4 w-4" />
                {title} ({reviews.length})
                {expanded ? (
                    <ChevronDownIcon className="h-4 w-4" />
                ) : (
                    <ChevronRightIcon className="h-4 w-4" />
                )}
            </button>

            {expanded && (
                <div className="space-y-3">
                    {displayReviews.map((review, idx) => (
                        <ReviewCard key={idx} review={review} />
                    ))}
                    {reviews.length > 5 && !showAll && (
                        <button
                            onClick={() => setShowAll(true)}
                            className="w-full py-2 text-sm text-blue-600 dark:text-blue-400 hover:underline"
                        >
                            Show all {reviews.length} reviews
                        </button>
                    )}
                </div>
            )}
        </div>
    );
}

function ReviewCard({ review }: { review: ReviewArtifact }) {
    const [expanded, setExpanded] = useState(false);
    const textPreview = review.text.length > 200 ? review.text.slice(0, 200) + '...' : review.text;

    const starColor = review.rating && review.rating <= 2
        ? 'text-red-400'
        : review.rating && review.rating >= 4
        ? 'text-green-400'
        : 'text-yellow-400';

    return (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                    {review.rating && (
                        <div className={`flex items-center gap-0.5 ${starColor}`}>
                            {[...Array(5)].map((_, i) => (
                                <StarIcon
                                    key={i}
                                    className={`h-4 w-4 ${i < review.rating! ? '' : 'opacity-30'}`}
                                />
                            ))}
                        </div>
                    )}
                    {review.author && (
                        <span className="text-sm text-gray-600 dark:text-gray-400">
                            by {review.author}
                        </span>
                    )}
                </div>
                {review.date && (
                    <span className="text-xs text-gray-400">{review.date}</span>
                )}
            </div>
            <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                {expanded ? review.text : textPreview}
            </p>
            {review.text.length > 200 && (
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

// =============================================================================
// Main Component
// =============================================================================

export default function ReviewAnalysisView({
    payload,
}: ReviewAnalysisViewProps) {
    const [showThemes, setShowThemes] = useState(true);

    // Parse the data from the payload - handle various nesting patterns
    let data: ReviewAnalysisData | null = null;

    if (payload.data) {
        // Could be nested as payload.data.data or directly as payload.data
        if (payload.data.business_name) {
            data = payload.data as ReviewAnalysisData;
        } else if (payload.data.data?.business_name) {
            data = payload.data.data as ReviewAnalysisData;
        }
    }

    if (!data || !data.business_name) {
        console.error('ReviewAnalysisView: Invalid data structure', payload);
        return (
            <div className="p-4 text-gray-500 dark:text-gray-400">
                <p>Invalid review analysis data</p>
                <pre className="mt-2 text-xs overflow-auto max-h-40">
                    {JSON.stringify(payload, null, 2)}
                </pre>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-start justify-between">
                <div>
                    <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                        {data.business_name}
                    </h2>
                    <div className="flex items-center gap-3 mt-1 text-sm text-gray-500 dark:text-gray-400">
                        <span className="uppercase font-medium">{data.source}</span>
                        {data.business_rating && (
                            <span className="flex items-center gap-1">
                                <StarIcon className="h-4 w-4 text-yellow-400" />
                                {data.business_rating.toFixed(1)}
                            </span>
                        )}
                        {data.business_review_count && (
                            <span>{data.business_review_count.toLocaleString()} reviews</span>
                        )}
                    </div>
                    {data.business_url && (
                        <a
                            href={data.business_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1 mt-1"
                        >
                            <LinkIcon className="h-3 w-3" />
                            View on {data.source}
                        </a>
                    )}
                </div>
            </div>

            {/* Verdict Banner */}
            {data.verdict && <VerdictBanner verdict={data.verdict} />}

            {/* Rating Distribution */}
            <RatingDistributionBar distribution={data.rating_distribution} />

            {/* Key Findings Grid */}
            {data.verdict && <KeyFindingsGrid verdict={data.verdict} />}

            {/* Complaint Themes */}
            {data.complaint_themes && data.complaint_themes.length > 0 && (
                <div>
                    <button
                        onClick={() => setShowThemes(!showThemes)}
                        className="flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 hover:text-gray-900 dark:hover:text-white"
                    >
                        <ExclamationCircleIcon className="h-4 w-4" />
                        Complaint Themes ({data.complaint_themes.length})
                        {showThemes ? (
                            <ChevronDownIcon className="h-4 w-4" />
                        ) : (
                            <ChevronRightIcon className="h-4 w-4" />
                        )}
                    </button>

                    {showThemes && (
                        <div className="space-y-2">
                            {data.complaint_themes.map((theme, idx) => (
                                <ComplaintThemeCard key={idx} theme={theme} index={idx + 1} />
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Anomalies */}
            {data.anomalies && data.anomalies.length > 0 && (
                <div>
                    <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
                        <ExclamationTriangleIcon className="h-4 w-4 text-orange-500" />
                        Anomalies Detected ({data.anomalies.length})
                    </h3>
                    <div className="space-y-2">
                        {data.anomalies.map((anomaly, idx) => (
                            <AnomalyCard key={idx} anomaly={anomaly} />
                        ))}
                    </div>
                </div>
            )}

            {/* Negative Reviews */}
            {data.negative_reviews && data.negative_reviews.length > 0 && (
                <ReviewList
                    reviews={data.negative_reviews}
                    title={`Negative Reviews (${data.one_star_count} 1-star, ${data.two_star_count} 2-star)`}
                />
            )}

            {/* Positive Sample */}
            {data.positive_sample && data.positive_sample.length > 0 && (
                <ReviewList
                    reviews={data.positive_sample}
                    title="Positive Review Sample"
                />
            )}

            {/* Journey Stats */}
            {data.journey && (
                <div className="bg-gray-100 dark:bg-gray-800 rounded-lg p-4">
                    <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
                        <ClockIcon className="h-4 w-4" />
                        Analysis Stats
                    </h3>
                    <div className="grid grid-cols-3 gap-4 text-sm">
                        <div>
                            <div className="text-gray-500 dark:text-gray-400">Duration</div>
                            <div className="font-medium text-gray-900 dark:text-white">
                                {(data.journey.duration_ms / 1000).toFixed(1)}s
                            </div>
                        </div>
                        <div>
                            <div className="text-gray-500 dark:text-gray-400">API Calls</div>
                            <div className="font-medium text-gray-900 dark:text-white">
                                {data.journey.api_calls}
                            </div>
                        </div>
                        <div>
                            <div className="text-gray-500 dark:text-gray-400">Reviews Analyzed</div>
                            <div className="font-medium text-gray-900 dark:text-white">
                                {data.journey.reviews_analyzed}
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
