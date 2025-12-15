/**
 * VendorFinderWorkflowView
 *
 * Custom view for the vendor_finder workflow.
 * Shows vendor cards with reviews, ratings, and selection controls.
 */

import { useState, useMemo, useEffect } from 'react';
import {
    CheckCircleIcon,
    XCircleIcon,
    StarIcon,
    ArrowPathIcon,
    ChevronDownIcon,
    ChevronRightIcon,
    GlobeAltIcon,
    MapPinIcon,
    PhoneIcon,
    EnvelopeIcon,
    BuildingStorefrontIcon,
    MagnifyingGlassIcon,
    ClipboardDocumentListIcon,
    SparklesIcon,
    DocumentArrowDownIcon,
    LightBulbIcon,
} from '@heroicons/react/24/solid';
import { WorkflowViewProps } from '../../../lib/workspace';
import { WorkspacePayload, TableColumn } from '../../../types/chat';

// =============================================================================
// Types
// =============================================================================

interface ReviewSummary {
    source: string;
    rating?: number;
    sentiment: string;
    highlights: string[];
    concerns: string[];
}

interface Vendor {
    id: string;
    name: string;
    website?: string;
    description?: string;
    services?: string[];
    location?: string;
    contact?: Record<string, string>;
    price_tier?: string;
    reviews?: ReviewSummary[];
    overall_rating?: number;
    overall_sentiment?: string;
    status: string;
    user_notes?: string;
}

interface Criteria {
    vendor_type: string;
    location: string;
    radius: string;
    must_have: string[];
    nice_to_have: string[];
    budget_hint: string;
    search_queries: string[];
}

// =============================================================================
// Stage Configuration
// =============================================================================

const STAGES = [
    { id: 'define_criteria', name: 'Criteria', icon: ClipboardDocumentListIcon },
    { id: 'broad_search', name: 'Search', icon: MagnifyingGlassIcon },
    { id: 'build_vendor_list', name: 'Build List', icon: BuildingStorefrontIcon },
    { id: 'enrich_company_info', name: 'Enrich', icon: SparklesIcon },
    { id: 'find_reviews', name: 'Reviews', icon: StarIcon },
    { id: 'analyze_and_recommend', name: 'Analyze', icon: LightBulbIcon },
    { id: 'final_checkpoint', name: 'Complete', icon: CheckCircleIcon },
];

// Checkpoint to relevant data node mapping
const CHECKPOINT_DATA_MAP: Record<string, string> = {
    'criteria_checkpoint': 'define_criteria',
    'vendor_list_checkpoint': 'build_vendor_list',
    'final_checkpoint': 'analyze_and_recommend',
};

// =============================================================================
// Helper Components
// =============================================================================

function StatusBadge({ status }: { status: string }) {
    const config: Record<string, { color: string; bg: string; label: string }> = {
        pending: { color: 'text-gray-600 dark:text-gray-400', bg: 'bg-gray-100 dark:bg-gray-800', label: 'Pending' },
        running: { color: 'text-blue-600 dark:text-blue-400', bg: 'bg-blue-100 dark:bg-blue-900/30', label: 'Running' },
        waiting: { color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-100 dark:bg-amber-900/30', label: 'Waiting' },
        completed: { color: 'text-green-600 dark:text-green-400', bg: 'bg-green-100 dark:bg-green-900/30', label: 'Completed' },
        failed: { color: 'text-red-600 dark:text-red-400', bg: 'bg-red-100 dark:bg-red-900/30', label: 'Failed' },
    };
    const cfg = config[status] || config.pending;
    return (
        <span className={`px-2 py-1 text-xs font-medium rounded-full ${cfg.bg} ${cfg.color}`}>
            {cfg.label}
        </span>
    );
}

function StageProgress({ currentNodeId, nodeStates }: { currentNodeId?: string; nodeStates: Record<string, any> }) {
    const getCurrentStageIndex = () => {
        if (!currentNodeId) return -1;
        // Find the stage that contains this node (including checkpoints)
        const stageIndex = STAGES.findIndex(s => currentNodeId.includes(s.id) || currentNodeId === s.id);
        if (stageIndex >= 0) return stageIndex;
        // Check if it's a checkpoint
        for (const [checkpoint, dataNode] of Object.entries(CHECKPOINT_DATA_MAP)) {
            if (currentNodeId === checkpoint) {
                const idx = STAGES.findIndex(s => s.id === dataNode);
                return idx >= 0 ? idx : -1;
            }
        }
        return -1;
    };

    const currentIndex = getCurrentStageIndex();

    return (
        <div className="flex items-center justify-between mb-6 px-2">
            {STAGES.map((stage, idx) => {
                const Icon = stage.icon;
                const isCompleted = nodeStates[stage.id]?.status === 'completed';
                const isCurrent = idx === currentIndex;
                const isPast = idx < currentIndex;

                return (
                    <div key={stage.id} className="flex items-center">
                        <div className="flex flex-col items-center">
                            <div
                                className={`w-10 h-10 rounded-full flex items-center justify-center transition-colors ${
                                    isCompleted || isPast
                                        ? 'bg-green-100 dark:bg-green-900/30'
                                        : isCurrent
                                            ? 'bg-blue-100 dark:bg-blue-900/30'
                                            : 'bg-gray-100 dark:bg-gray-800'
                                }`}
                            >
                                <Icon
                                    className={`w-5 h-5 ${
                                        isCompleted || isPast
                                            ? 'text-green-600 dark:text-green-400'
                                            : isCurrent
                                                ? 'text-blue-600 dark:text-blue-400'
                                                : 'text-gray-400'
                                    }`}
                                />
                            </div>
                            <span className={`text-xs mt-1 ${isCurrent ? 'font-medium text-gray-900 dark:text-white' : 'text-gray-500 dark:text-gray-400'}`}>
                                {stage.name}
                            </span>
                        </div>
                        {idx < STAGES.length - 1 && (
                            <div className={`w-8 h-0.5 mx-1 ${isPast ? 'bg-green-400' : 'bg-gray-200 dark:bg-gray-700'}`} />
                        )}
                    </div>
                );
            })}
        </div>
    );
}

function SentimentBadge({ sentiment }: { sentiment?: string }) {
    const config: Record<string, { emoji: string; color: string }> = {
        positive: { emoji: '👍', color: 'text-green-600' },
        mixed: { emoji: '😐', color: 'text-amber-600' },
        negative: { emoji: '👎', color: 'text-red-600' },
    };
    const cfg = config[sentiment || ''] || { emoji: '', color: '' };
    return cfg.emoji ? <span className={cfg.color}>{cfg.emoji}</span> : null;
}

function RatingStars({ rating }: { rating?: number }) {
    if (!rating) return null;
    return (
        <div className="flex items-center gap-1">
            <StarIcon className="w-4 h-4 text-amber-500" />
            <span className="text-sm font-medium text-gray-900 dark:text-white">{rating.toFixed(1)}</span>
        </div>
    );
}

/**
 * Calculate a composite score (0-100) for a vendor based on available data
 */
function calculateVendorScore(vendor: Vendor): { score: number; confidence: 'high' | 'medium' | 'low' } | null {
    const rating = vendor.overall_rating;
    const sentiment = vendor.overall_sentiment;
    const reviewCount = vendor.reviews?.length || 0;

    // Need at least rating OR sentiment to calculate score
    if (!rating && !sentiment) return null;

    let score = 50; // Start at neutral

    // Rating contributes up to 40 points (rating/5 * 40)
    if (rating) {
        score = (rating / 5) * 80; // 0-80 base from rating
    }

    // Sentiment adjustment (+/- 10 points)
    if (sentiment === 'positive') score += 10;
    else if (sentiment === 'negative') score -= 10;

    // Clamp to 0-100
    score = Math.max(0, Math.min(100, Math.round(score)));

    // Confidence based on data availability
    const confidence: 'high' | 'medium' | 'low' =
        rating && reviewCount >= 2 ? 'high' :
        rating || reviewCount >= 1 ? 'medium' : 'low';

    return { score, confidence };
}

function VendorScore({ vendor }: { vendor: Vendor }) {
    const result = calculateVendorScore(vendor);
    if (!result) return null;

    const { score, confidence } = result;

    // Color based on score
    const getScoreColor = (s: number) => {
        if (s >= 80) return 'text-green-600 dark:text-green-400 bg-green-100 dark:bg-green-900/30';
        if (s >= 60) return 'text-blue-600 dark:text-blue-400 bg-blue-100 dark:bg-blue-900/30';
        if (s >= 40) return 'text-amber-600 dark:text-amber-400 bg-amber-100 dark:bg-amber-900/30';
        return 'text-red-600 dark:text-red-400 bg-red-100 dark:bg-red-900/30';
    };

    const confidenceIndicator = confidence === 'high' ? '●●●' : confidence === 'medium' ? '●●○' : '●○○';

    return (
        <div className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-sm font-bold ${getScoreColor(score)}`}>
            <span>{score}</span>
            <span className="text-[10px] opacity-60" title={`Confidence: ${confidence}`}>{confidenceIndicator}</span>
        </div>
    );
}

// =============================================================================
// Vendor Card Component
// =============================================================================

function VendorCard({
    vendor,
    expanded,
    onToggle,
    showReviews = false,
}: {
    vendor: Vendor;
    expanded: boolean;
    onToggle: () => void;
    showReviews?: boolean;
}) {
    return (
        <div className="border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 overflow-hidden">
            {/* Header */}
            <button
                onClick={onToggle}
                className="w-full flex items-center gap-3 p-4 text-left hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
            >
                {/* Score badge - prominent position */}
                <VendorScore vendor={vendor} />

                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                        <h3 className="font-semibold text-gray-900 dark:text-white truncate">
                            {vendor.name}
                        </h3>
                        {vendor.overall_rating && <RatingStars rating={vendor.overall_rating} />}
                        <SentimentBadge sentiment={vendor.overall_sentiment} />
                        {vendor.price_tier && (
                            <span className="text-green-600 dark:text-green-400 text-sm font-medium">
                                {vendor.price_tier}
                            </span>
                        )}
                    </div>
                    {vendor.description && (
                        <p className="text-sm text-gray-600 dark:text-gray-400 mt-1 line-clamp-2">
                            {vendor.description}
                        </p>
                    )}
                    <div className="flex items-center gap-4 mt-2 text-xs text-gray-500 dark:text-gray-400">
                        {vendor.location && (
                            <span className="flex items-center gap-1">
                                <MapPinIcon className="w-3 h-3" />
                                {vendor.location}
                            </span>
                        )}
                        {vendor.website && (
                            <span className="flex items-center gap-1">
                                <GlobeAltIcon className="w-3 h-3" />
                                Website
                            </span>
                        )}
                    </div>
                </div>
                {expanded ? (
                    <ChevronDownIcon className="w-5 h-5 text-gray-400 flex-shrink-0" />
                ) : (
                    <ChevronRightIcon className="w-5 h-5 text-gray-400 flex-shrink-0" />
                )}
            </button>

            {/* Expanded Content */}
            {expanded && (
                <div className="px-4 pb-4 border-t border-gray-100 dark:border-gray-800 pt-3 space-y-4">
                    {/* Services */}
                    {vendor.services && vendor.services.length > 0 && (
                        <div>
                            <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase mb-1">Services</h4>
                            <div className="flex flex-wrap gap-1">
                                {vendor.services.map((service, i) => (
                                    <span key={i} className="px-2 py-0.5 text-xs bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded">
                                        {service}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Contact */}
                    {vendor.contact && Object.keys(vendor.contact).length > 0 && (
                        <div>
                            <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase mb-1">Contact</h4>
                            <div className="space-y-1 text-sm">
                                {vendor.contact.phone && (
                                    <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400">
                                        <PhoneIcon className="w-3 h-3" />
                                        {vendor.contact.phone}
                                    </div>
                                )}
                                {vendor.contact.email && (
                                    <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400">
                                        <EnvelopeIcon className="w-3 h-3" />
                                        {vendor.contact.email}
                                    </div>
                                )}
                                {vendor.contact.address && (
                                    <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400">
                                        <MapPinIcon className="w-3 h-3" />
                                        {vendor.contact.address}
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {/* Website Link */}
                    {vendor.website && (
                        <a
                            href={vendor.website}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-sm text-blue-600 hover:underline"
                        >
                            <GlobeAltIcon className="w-4 h-4" />
                            Visit Website
                        </a>
                    )}

                    {/* Reviews */}
                    {showReviews && vendor.reviews && vendor.reviews.length > 0 && (
                        <div>
                            <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase mb-2">Reviews</h4>
                            <div className="space-y-2">
                                {vendor.reviews.map((review, i) => (
                                    <div key={i} className="p-2 bg-gray-50 dark:bg-gray-800 rounded text-sm">
                                        <div className="flex items-center gap-2 mb-1">
                                            <span className="font-medium capitalize text-gray-900 dark:text-white">{review.source}</span>
                                            {review.rating && <RatingStars rating={review.rating} />}
                                            <SentimentBadge sentiment={review.sentiment} />
                                        </div>
                                        {review.highlights && review.highlights.length > 0 && (
                                            <div className="text-green-600 dark:text-green-400 text-xs">
                                                + {review.highlights.join(', ')}
                                            </div>
                                        )}
                                        {review.concerns && review.concerns.length > 0 && (
                                            <div className="text-red-600 dark:text-red-400 text-xs">
                                                - {review.concerns.join(', ')}
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// =============================================================================
// Criteria View Component
// =============================================================================

function CriteriaView({ criteria }: { criteria: Criteria }) {
    return (
        <div className="space-y-4 p-4 bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700">
            <div>
                <h3 className="font-medium text-gray-900 dark:text-white">Looking for: {criteria.vendor_type}</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">{criteria.location} ({criteria.radius})</p>
            </div>

            {criteria.must_have && criteria.must_have.length > 0 && (
                <div>
                    <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">Must Have</h4>
                    <ul className="list-disc list-inside text-sm text-gray-600 dark:text-gray-400">
                        {criteria.must_have.map((item, i) => <li key={i}>{item}</li>)}
                    </ul>
                </div>
            )}

            {criteria.nice_to_have && criteria.nice_to_have.length > 0 && (
                <div>
                    <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">Nice to Have</h4>
                    <ul className="list-disc list-inside text-sm text-gray-600 dark:text-gray-400">
                        {criteria.nice_to_have.map((item, i) => <li key={i}>{item}</li>)}
                    </ul>
                </div>
            )}

            {criteria.budget_hint && criteria.budget_hint !== 'not specified' && (
                <p className="text-sm text-gray-700 dark:text-gray-300"><strong>Budget:</strong> {criteria.budget_hint}</p>
            )}
        </div>
    );
}

// =============================================================================
// Main Component
// =============================================================================

export default function VendorFinderWorkflowView({
    instance,
    handlers,
    isProcessing = false,
    currentEvent,
    onSaveAsAsset,
    isSavingAsset = false,
    onClose,
}: WorkflowViewProps) {
    const [expandedVendors, setExpandedVendors] = useState<Set<string>>(new Set());
    const [isTransitioning, setIsTransitioning] = useState(false);
    const [lastCheckpointId, setLastCheckpointId] = useState<string | null>(null);
    const [assetSaved, setAssetSaved] = useState(false);

    const toggleVendor = (id: string) => {
        setExpandedVendors(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    // Get current state
    const currentNodeId = instance.current_node?.id;
    const isAtCheckpoint = instance.status === 'waiting';
    const isRunning = instance.status === 'running';
    const stepData = instance.step_data;

    // Reset local transitioning state when processing starts (parent takes over) or when we reach a new checkpoint
    useEffect(() => {
        if (isProcessing || isRunning) {
            // Parent is now handling the processing state, we can reset local state
            setIsTransitioning(false);
        }
        // Track current checkpoint to detect when we arrive at a new one
        if (isAtCheckpoint && currentNodeId !== lastCheckpointId) {
            setLastCheckpointId(currentNodeId || null);
        }
    }, [isProcessing, isRunning, isAtCheckpoint, currentNodeId, lastCheckpointId]);

    // Handler for approve with transition state
    const handleApprove = () => {
        setIsTransitioning(true);
        handlers.onApprove();
    };

    const handleReject = () => {
        handlers.onReject();
    };

    // Get vendors from the latest step that has them
    const vendors = useMemo(() => {
        const sources = ['find_reviews', 'enrich_company_info', 'build_vendor_list'];
        for (const source of sources) {
            if (stepData[source]?.vendors) {
                return stepData[source].vendors as Vendor[];
            }
        }
        return [];
    }, [stepData]);

    // Get criteria
    const criteria = stepData.define_criteria?.criteria as Criteria | undefined;

    // Convert vendors to table format for saving as asset
    const convertVendorsToTablePayload = (): WorkspacePayload => {
        const columns: TableColumn[] = [
            { key: 'name', label: 'Name', type: 'text', sortable: true, filterable: true },
            { key: 'description', label: 'Description', type: 'text', sortable: false, filterable: true },
            { key: 'location', label: 'Location', type: 'text', sortable: true, filterable: true },
            { key: 'website', label: 'Website', type: 'link', sortable: false, filterable: false },
            { key: 'overall_rating', label: 'Rating', type: 'number', sortable: true, filterable: false },
            { key: 'overall_sentiment', label: 'Sentiment', type: 'text', sortable: true, filterable: true },
            { key: 'price_tier', label: 'Price', type: 'text', sortable: true, filterable: true },
            { key: 'services', label: 'Services', type: 'text', sortable: false, filterable: true },
        ];

        const rows = vendors.map(vendor => ({
            name: vendor.name,
            description: vendor.description || '',
            location: vendor.location || '',
            website: vendor.website || '',
            overall_rating: vendor.overall_rating || null,
            overall_sentiment: vendor.overall_sentiment || '',
            price_tier: vendor.price_tier || '',
            services: vendor.services?.join(', ') || '',
        }));

        return {
            type: 'table',
            title: `Vendor Search: ${criteria?.vendor_type || 'Vendors'}`,
            content: `${vendors.length} vendors found for ${criteria?.vendor_type || 'search'} in ${criteria?.location || 'location'}`,
            table_data: {
                columns,
                rows,
                source: 'vendor_finder',
            },
        };
    };

    const handleSaveAsAsset = () => {
        if (!onSaveAsAsset) return;
        const tablePayload = convertVendorsToTablePayload();
        onSaveAsAsset(tablePayload);
        setAssetSaved(true);
    };

    return (
        <div className="h-full flex flex-col">
            {/* Header */}
            <div className="flex-shrink-0 px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                            Vendor Finder
                        </h2>
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                            {instance.status === 'completed'
                                ? `Complete - ${vendors.length} vendors`
                                : vendors.length > 0
                                    ? `${vendors.length} vendors found`
                                    : isRunning
                                        ? 'Searching...'
                                        : 'Ready'}
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        <StatusBadge status={instance.status} />
                        {instance.status !== 'completed' && instance.status !== 'cancelled' && (
                            <button
                                onClick={() => handlers.onCancel()}
                                className="px-3 py-1.5 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
                            >
                                Cancel
                            </button>
                        )}
                    </div>
                </div>

                {/* Stage Progress */}
                <StageProgress
                    currentNodeId={currentNodeId || undefined}
                    nodeStates={instance.node_states || {}}
                />
            </div>

            {/* Content Area - ONE focus at a time */}
            <div className="flex-1 overflow-y-auto p-6">
                {(() => {
                    // Determine the single view to show
                    const isWorking = isProcessing || isTransitioning || isRunning;
                    const isComplete = instance.status === 'completed';
                    const isCheckpoint = isAtCheckpoint && !isProcessing && !isTransitioning;

                    // ===========================================
                    // STATE: WORKING (processing/running)
                    // ===========================================
                    if (isWorking && !isComplete) {
                        return (
                            <div className="flex flex-col items-center justify-center py-16">
                                <div className="w-16 h-16 mb-6 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                                    <ArrowPathIcon className="w-8 h-8 text-blue-600 dark:text-blue-400 animate-spin" />
                                </div>
                                <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                                    {isTransitioning
                                        ? 'Resuming...'
                                        : currentEvent?.node_name || instance.current_node?.name || 'Processing'}
                                </h3>
                                <p className="text-gray-600 dark:text-gray-400 mb-6 text-center max-w-md">
                                    {currentEvent?.data?.message || (
                                        currentNodeId === 'define_criteria' ? 'Analyzing your requirements...' :
                                        currentNodeId === 'broad_search' ? 'Searching for vendors...' :
                                        currentNodeId === 'build_vendor_list' ? 'Building vendor list...' :
                                        currentNodeId === 'enrich_company_info' ? 'Researching company details...' :
                                        currentNodeId === 'find_reviews' ? 'Finding reviews...' :
                                        currentNodeId === 'analyze_and_recommend' ? 'Analyzing findings and building recommendations...' :
                                        'Working...'
                                    )}
                                </p>
                                {currentEvent?.data?.progress != null && (
                                    <div className="w-64 h-2 bg-blue-200 dark:bg-blue-800 rounded-full overflow-hidden">
                                        <div
                                            className="h-full bg-blue-500 transition-all duration-300"
                                            style={{ width: `${Math.round(currentEvent.data.progress * 100)}%` }}
                                        />
                                    </div>
                                )}
                            </div>
                        );
                    }

                    // ===========================================
                    // STATE: CHECKPOINT (waiting for user)
                    // ===========================================
                    if (isCheckpoint) {
                        return (
                            <div>
                                {/* Checkpoint prompt */}
                                <div className="mb-6 p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
                                    <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                                        {currentNodeId === 'criteria_checkpoint' ? 'Review Search Criteria' :
                                         currentNodeId === 'vendor_list_checkpoint' ? 'Review Vendor List' :
                                         currentNodeId === 'final_checkpoint' ? 'Review Final Results' :
                                         'Review'}
                                    </h3>
                                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                                        {currentNodeId === 'criteria_checkpoint' && 'Confirm these criteria before searching for vendors.'}
                                        {currentNodeId === 'vendor_list_checkpoint' && 'Review the vendors found. Continue to research their reviews and details.'}
                                        {currentNodeId === 'final_checkpoint' && 'Review the complete vendor profiles with reviews and ratings.'}
                                    </p>
                                    <div className="flex gap-2">
                                        <button
                                            onClick={handleApprove}
                                            className="flex items-center gap-2 px-4 py-2 bg-gray-900 dark:bg-white text-white dark:text-gray-900 rounded-lg hover:bg-gray-800 dark:hover:bg-gray-100 transition-colors"
                                        >
                                            <CheckCircleIcon className="w-4 h-4" />
                                            Continue
                                        </button>
                                        <button
                                            onClick={handleReject}
                                            className="flex items-center gap-2 px-4 py-2 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors"
                                        >
                                            <XCircleIcon className="w-4 h-4" />
                                            Cancel
                                        </button>
                                    </div>
                                </div>

                                {/* Data to review - specific to checkpoint */}
                                {currentNodeId === 'criteria_checkpoint' && criteria && (
                                    <CriteriaView criteria={criteria} />
                                )}

                                {currentNodeId === 'vendor_list_checkpoint' && vendors.length > 0 && (
                                    <div className="space-y-3">
                                        {vendors.map(vendor => (
                                            <VendorCard
                                                key={vendor.id}
                                                vendor={vendor}
                                                expanded={expandedVendors.has(vendor.id)}
                                                onToggle={() => toggleVendor(vendor.id)}
                                                showReviews={false}
                                            />
                                        ))}
                                    </div>
                                )}

                                {currentNodeId === 'final_checkpoint' && vendors.length > 0 && (
                                    <div className="space-y-3">
                                        {vendors.map(vendor => (
                                            <VendorCard
                                                key={vendor.id}
                                                vendor={vendor}
                                                expanded={expandedVendors.has(vendor.id)}
                                                onToggle={() => toggleVendor(vendor.id)}
                                                showReviews={true}
                                            />
                                        ))}
                                    </div>
                                )}
                            </div>
                        );
                    }

                    // ===========================================
                    // STATE: COMPLETED
                    // ===========================================
                    if (isComplete) {
                        return (
                            <div>
                                {/* Success banner with save/close buttons */}
                                <div className="mb-6 p-4 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                            <CheckCircleIcon className="w-5 h-5 text-green-600" />
                                            <span className="font-medium text-gray-900 dark:text-white">
                                                {assetSaved ? 'Results saved!' : 'Vendor research complete'}
                                            </span>
                                            <span className="text-sm text-gray-500 dark:text-gray-400">
                                                ({vendors.length} vendors)
                                            </span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            {/* Save button - only show if not saved yet */}
                                            {onSaveAsAsset && vendors.length > 0 && !assetSaved && (
                                                <button
                                                    onClick={handleSaveAsAsset}
                                                    disabled={isSavingAsset}
                                                    className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-green-400 text-white rounded-lg transition-colors"
                                                >
                                                    {isSavingAsset ? (
                                                        <ArrowPathIcon className="w-4 h-4 animate-spin" />
                                                    ) : (
                                                        <DocumentArrowDownIcon className="w-4 h-4" />
                                                    )}
                                                    {isSavingAsset ? 'Saving...' : 'Save as Asset'}
                                                </button>
                                            )}
                                            {/* Close button */}
                                            {onClose && (
                                                <button
                                                    onClick={onClose}
                                                    className="flex items-center gap-2 px-4 py-2 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 rounded-lg transition-colors"
                                                >
                                                    <XCircleIcon className="w-4 h-4" />
                                                    Close
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                </div>

                                {/* Final results */}
                                {vendors.length > 0 && (
                                    <div className="space-y-3">
                                        {vendors.map(vendor => (
                                            <VendorCard
                                                key={vendor.id}
                                                vendor={vendor}
                                                expanded={expandedVendors.has(vendor.id)}
                                                onToggle={() => toggleVendor(vendor.id)}
                                                showReviews={true}
                                            />
                                        ))}
                                    </div>
                                )}
                            </div>
                        );
                    }

                    // ===========================================
                    // STATE: IDLE/INITIAL (shouldn't normally see)
                    // ===========================================
                    return (
                        <div className="flex flex-col items-center justify-center py-16 text-gray-400">
                            <BuildingStorefrontIcon className="w-12 h-12 mb-3 opacity-50" />
                            <p>Ready to start</p>
                        </div>
                    );
                })()}
            </div>
        </div>
    );
}
