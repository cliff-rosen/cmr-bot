/**
 * ResearchWorkflowView - Interactive research workflow with stage-specific UX
 *
 * Stages:
 * 1. Question Formulation - Refine and approve the research question
 * 2. Answer Checklist - Define what a complete answer needs
 * 3. Retrieval Loop - Iterative search and findings collection
 * 4. Final Compilation - Review compiled answer
 */

import { useState } from 'react';
import {
    QuestionMarkCircleIcon,
    ClipboardDocumentListIcon,
    MagnifyingGlassIcon,
    CheckIcon,
    PencilIcon,
    PlusIcon,
    TrashIcon,
    ArrowPathIcon,
    ChevronRightIcon,
    ChevronDownIcon,
    ExclamationTriangleIcon,
    CheckCircleIcon,
    PlayIcon,
    PauseIcon,
    LinkIcon,
    LightBulbIcon,
    SparklesIcon
} from '@heroicons/react/24/solid';
import {
    ResearchWorkflow,
    ResearchWorkflowStage,
    ChecklistItem,
    WorkspacePayload
} from '../../../types/chat';
import { MarkdownRenderer } from '../../common/MarkdownRenderer';

interface ResearchWorkflowViewProps {
    payload: WorkspacePayload;
    // Unified PayloadViewProps interface
    onSaveAsAsset?: (payload: WorkspacePayload, andClose?: boolean) => void;
    isSaving?: boolean;
    onPayloadEdit?: (payload: WorkspacePayload) => void;
    onAccept?: (payload: WorkspacePayload) => void;
    onReject?: () => void;
    // Research workflow specific callbacks
    onUpdateWorkflow?: (workflow: any) => void;
    onProceed?: () => void;
    onRunRetrieval?: () => void;
    onPauseRetrieval?: () => void;
    onCompile?: () => void;
    onComplete?: () => void;
}

// Stage configuration
const STAGES: { key: ResearchWorkflowStage; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
    { key: 'question', label: 'Question', icon: QuestionMarkCircleIcon },
    { key: 'checklist', label: 'Checklist', icon: ClipboardDocumentListIcon },
    { key: 'retrieval', label: 'Retrieval', icon: MagnifyingGlassIcon },
    { key: 'compiling', label: 'Compiling', icon: SparklesIcon },
    { key: 'complete', label: 'Complete', icon: CheckCircleIcon },
];

// Priority colors
const PRIORITY_COLORS = {
    high: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 border-red-200 dark:border-red-800',
    medium: 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300 border-yellow-200 dark:border-yellow-800',
    low: 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-700'
};

const STATUS_COLORS = {
    pending: 'text-gray-400',
    partial: 'text-yellow-500',
    complete: 'text-green-500'
};

const CONFIDENCE_COLORS = {
    high: 'text-green-600 dark:text-green-400',
    medium: 'text-yellow-600 dark:text-yellow-400',
    low: 'text-red-600 dark:text-red-400'
};

export default function ResearchWorkflowView({
    payload,
    onUpdateWorkflow,
    onProceed,
    onRunRetrieval,
    onPauseRetrieval,
    onCompile,
    onComplete
}: ResearchWorkflowViewProps) {
    const workflow = payload.research_data;

    if (!workflow) {
        return (
            <div className="flex items-center justify-center h-full text-gray-400">
                No research workflow data
            </div>
        );
    }

    const currentStageIndex = STAGES.findIndex(s => s.key === workflow.stage);

    return (
        <div className="flex flex-col h-full bg-white dark:bg-gray-900">
            {/* Header with stage progress */}
            <div className="flex-shrink-0 px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                <div className="flex items-center gap-3 mb-4">
                    <LightBulbIcon className="h-6 w-6 text-purple-500" />
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                        Research Workflow
                    </h2>
                </div>

                {/* Stage progress bar */}
                <div className="flex items-center gap-2">
                    {STAGES.map((stage, index) => {
                        const Icon = stage.icon;
                        const isActive = stage.key === workflow.stage;
                        const isComplete = index < currentStageIndex;
                        const isPending = index > currentStageIndex;

                        return (
                            <div key={stage.key} className="flex items-center">
                                <div className={`
                                    flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all
                                    ${isActive ? 'bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300 ring-2 ring-purple-500' : ''}
                                    ${isComplete ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300' : ''}
                                    ${isPending ? 'bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-500' : ''}
                                `}>
                                    {isComplete ? (
                                        <CheckIcon className="h-3.5 w-3.5" />
                                    ) : (
                                        <Icon className="h-3.5 w-3.5" />
                                    )}
                                    <span className="hidden sm:inline">{stage.label}</span>
                                </div>
                                {index < STAGES.length - 1 && (
                                    <ChevronRightIcon className={`h-4 w-4 mx-1 ${isComplete ? 'text-green-400' : 'text-gray-300 dark:text-gray-600'}`} />
                                )}
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Stage content */}
            <div className="flex-1 overflow-y-auto">
                {workflow.stage === 'question' && (
                    <QuestionStageView
                        workflow={workflow}
                        onUpdate={onUpdateWorkflow || (() => {})}
                        onProceed={onProceed || (() => {})}
                    />
                )}
                {workflow.stage === 'checklist' && (
                    <ChecklistStageView
                        workflow={workflow}
                        onUpdate={onUpdateWorkflow || (() => {})}
                        onProceed={onProceed || (() => {})}
                    />
                )}
                {workflow.stage === 'retrieval' && (
                    <RetrievalStageView
                        workflow={workflow}
                        onUpdate={onUpdateWorkflow || (() => {})}
                        onRun={onRunRetrieval || (() => {})}
                        onPause={onPauseRetrieval || (() => {})}
                        onCompile={onCompile || (() => {})}
                    />
                )}
                {workflow.stage === 'compiling' && (
                    <CompilingStageView workflow={workflow} />
                )}
                {workflow.stage === 'complete' && (
                    <FinalStageView
                        workflow={workflow}
                        onUpdate={onUpdateWorkflow || (() => {})}
                        onComplete={onComplete || (() => {})}
                    />
                )}
            </div>
        </div>
    );
}

// =============================================================================
// Stage 1: Question Formulation
// =============================================================================

interface QuestionStageViewProps {
    workflow: ResearchWorkflow;
    onUpdate: (workflow: ResearchWorkflow) => void;
    onProceed: () => void;
}

function QuestionStageView({ workflow, onUpdate, onProceed }: QuestionStageViewProps) {
    const question = workflow.question;
    const [isEditing, setIsEditing] = useState(false);
    const [editedQuestion, setEditedQuestion] = useState(question?.refined || '');
    const [editedScope, _setEditedScope] = useState(question?.scope || '');
    void _setEditedScope; // Reserved for future scope editing UI

    const handleSaveEdit = () => {
        if (question) {
            onUpdate({
                ...workflow,
                question: {
                    ...question,
                    refined: editedQuestion,
                    scope: editedScope
                }
            });
        }
        setIsEditing(false);
    };

    const handleApprove = () => {
        if (question) {
            onUpdate({
                ...workflow,
                question: { ...question, approved: true }
            });
            onProceed();
        }
    };

    return (
        <div className="p-6 space-y-6">
            {/* Original query */}
            <div>
                <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                    Your Original Question
                </label>
                <div className="mt-2 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg text-gray-700 dark:text-gray-300">
                    "{workflow.original_query}"
                </div>
            </div>

            {/* Refined question */}
            {question && (
                <>
                    <div>
                        <div className="flex items-center justify-between mb-2">
                            <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                                Refined Research Question
                            </label>
                            {!isEditing && (
                                <button
                                    onClick={() => setIsEditing(true)}
                                    className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                                >
                                    <PencilIcon className="h-3 w-3" />
                                    Edit
                                </button>
                            )}
                        </div>
                        {isEditing ? (
                            <div className="space-y-3">
                                <textarea
                                    value={editedQuestion}
                                    onChange={(e) => setEditedQuestion(e.target.value)}
                                    className="w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white resize-none"
                                    rows={3}
                                />
                                <div className="flex gap-2">
                                    <button
                                        onClick={handleSaveEdit}
                                        className="px-3 py-1.5 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-700"
                                    >
                                        Save
                                    </button>
                                    <button
                                        onClick={() => setIsEditing(false)}
                                        className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
                                    >
                                        Cancel
                                    </button>
                                </div>
                            </div>
                        ) : (
                            <div className="p-4 bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800 rounded-lg">
                                <p className="text-gray-900 dark:text-white font-medium">
                                    {question.refined}
                                </p>
                            </div>
                        )}
                    </div>

                    {/* Scope */}
                    <div>
                        <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                            Scope & Boundaries
                        </label>
                        <div className="mt-2 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg text-gray-600 dark:text-gray-400 text-sm">
                            {question.scope}
                        </div>
                    </div>

                    {/* Key terms */}
                    {question.key_terms && question.key_terms.length > 0 && (
                        <div>
                            <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                                Key Terms
                            </label>
                            <div className="mt-2 flex flex-wrap gap-2">
                                {question.key_terms.map((term, i) => (
                                    <span
                                        key={i}
                                        className="px-2 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded text-sm"
                                    >
                                        {term}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Constraints */}
                    {question.constraints && question.constraints.length > 0 && (
                        <div>
                            <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                                Constraints
                            </label>
                            <ul className="mt-2 space-y-1">
                                {question.constraints.map((constraint, i) => (
                                    <li key={i} className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-400">
                                        <ExclamationTriangleIcon className="h-4 w-4 text-yellow-500 flex-shrink-0 mt-0.5" />
                                        {constraint}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {/* Approve button */}
                    {!question.approved && (
                        <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
                            <button
                                onClick={handleApprove}
                                className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 font-medium"
                            >
                                <CheckIcon className="h-5 w-5" />
                                Approve Question & Build Checklist
                            </button>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}

// =============================================================================
// Stage 2: Answer Checklist
// =============================================================================

interface ChecklistStageViewProps {
    workflow: ResearchWorkflow;
    onUpdate: (workflow: ResearchWorkflow) => void;
    onProceed: () => void;
}

function ChecklistStageView({ workflow, onUpdate, onProceed }: ChecklistStageViewProps) {
    const checklist = workflow.checklist;
    const [newItemText, setNewItemText] = useState('');
    const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());

    const toggleExpanded = (id: string) => {
        setExpandedItems(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    const handleAddItem = () => {
        if (!newItemText.trim() || !checklist) return;

        const newItem: ChecklistItem = {
            id: `item_${Date.now()}`,
            description: newItemText.trim(),
            rationale: 'User-added requirement',
            status: 'pending',
            findings: [],
            priority: 'medium'
        };

        onUpdate({
            ...workflow,
            checklist: {
                ...checklist,
                items: [...checklist.items, newItem]
            }
        });
        setNewItemText('');
    };

    const handleRemoveItem = (itemId: string) => {
        if (!checklist) return;
        onUpdate({
            ...workflow,
            checklist: {
                ...checklist,
                items: checklist.items.filter(item => item.id !== itemId)
            }
        });
    };

    const handleUpdatePriority = (itemId: string, priority: 'high' | 'medium' | 'low') => {
        if (!checklist) return;
        onUpdate({
            ...workflow,
            checklist: {
                ...checklist,
                items: checklist.items.map(item =>
                    item.id === itemId ? { ...item, priority } : item
                )
            }
        });
    };

    const handleApprove = () => {
        if (checklist) {
            onUpdate({
                ...workflow,
                checklist: { ...checklist, approved: true }
            });
            onProceed();
        }
    };

    const completedCount = checklist?.items.filter(i => i.status === 'complete').length || 0;
    const totalCount = checklist?.items.length || 0;

    return (
        <div className="p-6 space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                        Answer Checklist
                    </h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                        Define what a complete answer should include
                    </p>
                </div>
                <div className="text-sm text-gray-500">
                    {completedCount}/{totalCount} items
                </div>
            </div>

            {/* Research question reminder */}
            {workflow.question && (
                <div className="p-3 bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800 rounded-lg">
                    <div className="text-xs text-purple-600 dark:text-purple-400 font-medium mb-1">Research Question</div>
                    <p className="text-sm text-gray-900 dark:text-white">{workflow.question.refined}</p>
                </div>
            )}

            {/* Checklist items */}
            {checklist && (
                <div className="space-y-3">
                    {checklist.items.map((item) => (
                        <div
                            key={item.id}
                            className={`border rounded-lg overflow-hidden ${PRIORITY_COLORS[item.priority]}`}
                        >
                            <div
                                className="flex items-center gap-3 p-3 cursor-pointer"
                                onClick={() => toggleExpanded(item.id)}
                            >
                                {/* Status icon */}
                                <div className={STATUS_COLORS[item.status]}>
                                    {item.status === 'complete' ? (
                                        <CheckCircleIcon className="h-5 w-5" />
                                    ) : item.status === 'partial' ? (
                                        <ArrowPathIcon className="h-5 w-5" />
                                    ) : (
                                        <div className="h-5 w-5 rounded-full border-2 border-current" />
                                    )}
                                </div>

                                {/* Content */}
                                <div className="flex-1 min-w-0">
                                    <p className="font-medium text-gray-900 dark:text-white">
                                        {item.description}
                                    </p>
                                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                                        {item.findings.length} findings
                                    </p>
                                </div>

                                {/* Priority selector */}
                                <select
                                    value={item.priority}
                                    onChange={(e) => handleUpdatePriority(item.id, e.target.value as any)}
                                    onClick={(e) => e.stopPropagation()}
                                    className="text-xs px-2 py-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                                >
                                    <option value="high">High</option>
                                    <option value="medium">Medium</option>
                                    <option value="low">Low</option>
                                </select>

                                {/* Delete button */}
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleRemoveItem(item.id);
                                    }}
                                    className="p-1 text-gray-400 hover:text-red-500"
                                >
                                    <TrashIcon className="h-4 w-4" />
                                </button>

                                {/* Expand icon */}
                                {expandedItems.has(item.id) ? (
                                    <ChevronDownIcon className="h-4 w-4 text-gray-400" />
                                ) : (
                                    <ChevronRightIcon className="h-4 w-4 text-gray-400" />
                                )}
                            </div>

                            {/* Expanded content */}
                            {expandedItems.has(item.id) && (
                                <div className="px-3 pb-3 border-t border-gray-200 dark:border-gray-700 bg-white/50 dark:bg-black/20">
                                    <p className="text-sm text-gray-600 dark:text-gray-400 py-2">
                                        <span className="font-medium">Rationale:</span> {item.rationale}
                                    </p>
                                    {item.findings.length > 0 && (
                                        <div className="space-y-2 mt-2">
                                            <div className="text-xs font-medium text-gray-500 uppercase">Findings</div>
                                            {item.findings.map((finding) => (
                                                <div key={finding.id} className="p-2 bg-white dark:bg-gray-800 rounded text-sm">
                                                    <div className="font-medium text-gray-900 dark:text-white">{finding.title}</div>
                                                    <div className="text-gray-600 dark:text-gray-400 text-xs mt-1">{finding.content}</div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}

            {/* Add item */}
            <div className="flex gap-2">
                <input
                    type="text"
                    value={newItemText}
                    onChange={(e) => setNewItemText(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleAddItem()}
                    placeholder="Add a checklist item..."
                    className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-sm"
                />
                <button
                    onClick={handleAddItem}
                    disabled={!newItemText.trim()}
                    className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    <PlusIcon className="h-5 w-5" />
                </button>
            </div>

            {/* Approve button */}
            {checklist && !checklist.approved && checklist.items.length > 0 && (
                <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
                    <button
                        onClick={handleApprove}
                        className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 font-medium"
                    >
                        <MagnifyingGlassIcon className="h-5 w-5" />
                        Approve Checklist & Start Research
                    </button>
                </div>
            )}
        </div>
    );
}

// =============================================================================
// Stage 3: Retrieval Loop
// =============================================================================

interface RetrievalStageViewProps {
    workflow: ResearchWorkflow;
    onUpdate: (workflow: ResearchWorkflow) => void;
    onRun: () => void;
    onPause: () => void;
    onCompile: () => void;
}

function RetrievalStageView({ workflow, onUpdate: _onUpdate, onRun, onPause, onCompile }: RetrievalStageViewProps) {
    void _onUpdate; // Reserved for future inline editing
    const retrieval = workflow.retrieval;
    const checklist = workflow.checklist;
    const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());

    const toggleExpanded = (id: string) => {
        setExpandedItems(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    const completedCount = checklist?.items.filter(i => i.status === 'complete').length || 0;
    const totalCount = checklist?.items.length || 0;
    const progress = totalCount > 0 ? (completedCount / totalCount) * 100 : 0;
    const isRunning = retrieval?.status === 'searching' || retrieval?.status === 'reviewing' || retrieval?.status === 'updating';

    return (
        <div className="p-6 space-y-6">
            {/* Header with controls */}
            <div className="flex items-center justify-between">
                <div>
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                        Research Retrieval
                    </h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                        Iteration {retrieval?.iteration || 0} of {retrieval?.max_iterations || 10}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    {isRunning ? (
                        <button
                            onClick={onPause}
                            className="flex items-center gap-2 px-4 py-2 bg-yellow-500 text-white rounded-lg hover:bg-yellow-600"
                        >
                            <PauseIcon className="h-4 w-4" />
                            Pause
                        </button>
                    ) : (
                        <button
                            onClick={onRun}
                            className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
                        >
                            <PlayIcon className="h-4 w-4" />
                            {retrieval?.iteration ? 'Continue' : 'Start'} Research
                        </button>
                    )}
                </div>
            </div>

            {/* Progress bar */}
            <div>
                <div className="flex items-center justify-between text-sm mb-1">
                    <span className="text-gray-600 dark:text-gray-400">Checklist Progress</span>
                    <span className="font-medium text-gray-900 dark:text-white">{completedCount}/{totalCount}</span>
                </div>
                <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                    <div
                        className="h-full bg-gradient-to-r from-purple-500 to-purple-600 rounded-full transition-all duration-500"
                        style={{ width: `${progress}%` }}
                    />
                </div>
            </div>

            {/* Status indicator */}
            {retrieval && (
                <div className={`p-3 rounded-lg ${
                    isRunning
                        ? 'bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800'
                        : 'bg-gray-50 dark:bg-gray-800'
                }`}>
                    <div className="flex items-center gap-2">
                        {isRunning && <ArrowPathIcon className="h-4 w-4 text-blue-500 animate-spin" />}
                        <span className={`text-sm font-medium ${isRunning ? 'text-blue-700 dark:text-blue-300' : 'text-gray-600 dark:text-gray-400'}`}>
                            {retrieval.status === 'searching' && 'Searching for information...'}
                            {retrieval.status === 'reviewing' && 'Reviewing search results...'}
                            {retrieval.status === 'updating' && 'Updating checklist with findings...'}
                            {retrieval.status === 'paused' && 'Paused - Click Continue to resume'}
                            {retrieval.status === 'complete' && 'Research complete! Ready to compile final answer.'}
                        </span>
                    </div>
                </div>
            )}

            {/* Checklist with findings */}
            <div className="space-y-3">
                <h4 className="font-medium text-gray-900 dark:text-white">Checklist Items</h4>
                {checklist?.items.map((item) => {
                    const isExpanded = expandedItems.has(item.id);
                    return (
                        <div
                            key={item.id}
                            className={`border rounded-lg overflow-hidden ${
                                item.status === 'complete'
                                    ? 'border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20'
                                    : item.status === 'partial'
                                        ? 'border-yellow-200 dark:border-yellow-800 bg-yellow-50 dark:bg-yellow-900/20'
                                        : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800'
                            }`}
                        >
                            <div
                                className="flex items-center gap-3 p-3 cursor-pointer"
                                onClick={() => toggleExpanded(item.id)}
                            >
                                <div className={STATUS_COLORS[item.status]}>
                                    {item.status === 'complete' ? (
                                        <CheckCircleIcon className="h-5 w-5" />
                                    ) : item.status === 'partial' ? (
                                        <ArrowPathIcon className="h-5 w-5" />
                                    ) : (
                                        <div className="h-5 w-5 rounded-full border-2 border-current" />
                                    )}
                                </div>
                                <div className="flex-1">
                                    <p className="font-medium text-gray-900 dark:text-white">{item.description}</p>
                                    <p className="text-xs text-gray-500 mt-0.5">{item.findings.length} findings</p>
                                </div>
                                {isExpanded ? (
                                    <ChevronDownIcon className="h-4 w-4 text-gray-400" />
                                ) : (
                                    <ChevronRightIcon className="h-4 w-4 text-gray-400" />
                                )}
                            </div>

                            {/* Findings list */}
                            {isExpanded && item.findings.length > 0 && (
                                <div className="px-3 pb-3 space-y-2 border-t border-gray-200 dark:border-gray-700">
                                    {item.findings.map((finding) => (
                                        <div key={finding.id} className="p-3 bg-white dark:bg-gray-900 rounded-lg mt-2">
                                            <div className="flex items-start justify-between">
                                                <div className="flex-1">
                                                    <p className="font-medium text-gray-900 dark:text-white text-sm">{finding.title}</p>
                                                    <p className="text-xs text-gray-500 mt-1">{finding.source}</p>
                                                </div>
                                                <span className={`text-xs px-2 py-0.5 rounded ${CONFIDENCE_COLORS[finding.confidence]}`}>
                                                    {finding.confidence}
                                                </span>
                                            </div>
                                            <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">{finding.content}</p>
                                            {finding.source_url && (
                                                <a
                                                    href={finding.source_url}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="inline-flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 mt-2 hover:underline"
                                                >
                                                    <LinkIcon className="h-3 w-3" />
                                                    View source
                                                </a>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Recent iterations */}
            {retrieval && retrieval.iterations.length > 0 && (
                <div className="space-y-3">
                    <h4 className="font-medium text-gray-900 dark:text-white">Recent Iterations</h4>
                    {retrieval.iterations.slice(-3).reverse().map((iteration) => (
                        <div key={iteration.iteration_number} className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                            <div className="flex items-center justify-between">
                                <span className="font-medium text-gray-900 dark:text-white">
                                    Iteration {iteration.iteration_number}
                                </span>
                                <span className="text-xs text-gray-500">
                                    {iteration.findings_added} findings added
                                </span>
                            </div>
                            <div className="flex flex-wrap gap-1 mt-2">
                                {iteration.queries.map((q) => (
                                    <span key={q.id} className="text-xs px-2 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded">
                                        {q.source}: {q.query.slice(0, 30)}...
                                    </span>
                                ))}
                            </div>
                            {iteration.notes && (
                                <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">{iteration.notes}</p>
                            )}
                        </div>
                    ))}
                </div>
            )}

            {/* Compile button */}
            {progress >= 70 && !isRunning && (
                <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
                    <button
                        onClick={onCompile}
                        className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 font-medium"
                    >
                        <SparklesIcon className="h-5 w-5" />
                        Compile Final Answer
                    </button>
                    <p className="text-xs text-center text-gray-500 mt-2">
                        {progress < 100 && `${(100 - progress).toFixed(0)}% of checklist items still pending`}
                    </p>
                </div>
            )}
        </div>
    );
}

// =============================================================================
// Stage 4a: Compiling (transitional)
// =============================================================================

function CompilingStageView({ workflow }: { workflow: ResearchWorkflow }) {
    return (
        <div className="flex flex-col items-center justify-center h-full p-6">
            <SparklesIcon className="h-16 w-16 text-purple-500 animate-pulse mb-4" />
            <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                Compiling Your Answer
            </h3>
            <p className="text-gray-500 dark:text-gray-400 text-center max-w-md">
                Synthesizing findings from {workflow.checklist?.items.reduce((sum, item) => sum + item.findings.length, 0) || 0} sources
                into a comprehensive answer...
            </p>
        </div>
    );
}

// =============================================================================
// Stage 4b: Final Answer
// =============================================================================

interface FinalStageViewProps {
    workflow: ResearchWorkflow;
    onUpdate: (workflow: ResearchWorkflow) => void;
    onComplete: () => void;
}

function FinalStageView({ workflow, onUpdate: _onUpdate, onComplete }: FinalStageViewProps) {
    void _onUpdate; // Reserved for future inline editing
    const final = workflow.final;
    const [showSources, setShowSources] = useState(false);

    if (!final) {
        return (
            <div className="flex items-center justify-center h-full text-gray-400">
                No final answer available
            </div>
        );
    }

    return (
        <div className="p-6 space-y-6">
            {/* Summary */}
            <div className="p-4 bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800 rounded-lg">
                <h3 className="font-medium text-purple-800 dark:text-purple-200 mb-2">Summary</h3>
                <p className="text-gray-900 dark:text-white">{final.summary}</p>
            </div>

            {/* Confidence */}
            <div className="flex items-center gap-4">
                <span className="text-sm text-gray-500">Confidence:</span>
                <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                    final.confidence === 'high' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' :
                    final.confidence === 'medium' ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300' :
                    'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
                }`}>
                    {final.confidence.charAt(0).toUpperCase() + final.confidence.slice(1)}
                </span>
                <span className="text-sm text-gray-500 flex-1">{final.confidence_explanation}</span>
            </div>

            {/* Full answer */}
            <div>
                <h3 className="font-medium text-gray-900 dark:text-white mb-3">Full Answer</h3>
                <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg prose dark:prose-invert max-w-none">
                    <MarkdownRenderer content={final.answer} />
                </div>
            </div>

            {/* Limitations */}
            {final.limitations.length > 0 && (
                <div>
                    <h3 className="font-medium text-gray-900 dark:text-white mb-2">Limitations</h3>
                    <ul className="space-y-1">
                        {final.limitations.map((limitation, i) => (
                            <li key={i} className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-400">
                                <ExclamationTriangleIcon className="h-4 w-4 text-yellow-500 flex-shrink-0 mt-0.5" />
                                {limitation}
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {/* Sources toggle */}
            <div>
                <button
                    onClick={() => setShowSources(!showSources)}
                    className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
                >
                    {showSources ? <ChevronDownIcon className="h-4 w-4" /> : <ChevronRightIcon className="h-4 w-4" />}
                    {final.sources.length} Sources
                </button>
                {showSources && (
                    <div className="mt-2 space-y-2">
                        {final.sources.map((source) => (
                            <div key={source.id} className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                                <div className="flex items-start justify-between">
                                    <div>
                                        <p className="font-medium text-gray-900 dark:text-white text-sm">{source.title}</p>
                                        {source.citation && (
                                            <p className="text-xs text-gray-500 mt-0.5">{source.citation}</p>
                                        )}
                                    </div>
                                    {source.url && (
                                        <a
                                            href={source.url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="text-blue-600 dark:text-blue-400 hover:underline"
                                        >
                                            <LinkIcon className="h-4 w-4" />
                                        </a>
                                    )}
                                </div>
                                <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">{source.contribution}</p>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Complete button */}
            <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
                <button
                    onClick={onComplete}
                    className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium"
                >
                    <CheckIcon className="h-5 w-5" />
                    Accept Answer & Save
                </button>
            </div>
        </div>
    );
}
