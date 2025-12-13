import { useState } from 'react';
import {
    WrenchScrewdriverIcon, XMarkIcon, PlusIcon, DocumentIcon,
    LightBulbIcon, BookmarkIcon, Cog6ToothIcon,
    ArrowsPointingOutIcon, UserIcon, HeartIcon, BuildingOfficeIcon,
    FolderIcon, ClockIcon, XCircleIcon, CheckIcon, UserCircleIcon,
    ChevronDownIcon, ChevronRightIcon, PencilIcon, PlayIcon,
    DocumentTextIcon
} from '@heroicons/react/24/solid';
import { CheckCircleIcon as CheckCircleOutlineIcon } from '@heroicons/react/24/outline';
import { Memory, MemoryType, Asset, Profile, ToolInfo } from '../../lib/api';
import { WorkflowPlan } from '../../types/chat';

interface ContextPanelProps {
    availableTools: ToolInfo[];
    memories: Memory[];
    assets: Asset[];
    profile: Profile | null;
    enabledTools: Set<string>;
    includeProfile: boolean;
    workflow: WorkflowPlan | null;
    onAddWorkingMemory: (content: string) => void;
    onToggleMemoryPinned: (memId: number) => void;
    onToggleAssetContext: (assetId: number) => void;
    onClearAllAssetsFromContext: () => void;
    onToggleTool: (toolId: string) => void;
    onToggleProfile: () => void;
    onExpandMemories: () => void;
    onExpandAssets: () => void;
    onEditProfile: () => void;
    onAbandonWorkflow: () => void;
    onViewStepOutput: (stepNumber: number) => void;
}

// Helper to get memory type icon and color
const getMemoryTypeInfo = (type: MemoryType) => {
    switch (type) {
        case 'fact':
            return { icon: UserIcon, color: 'text-blue-500', bg: 'bg-blue-100 dark:bg-blue-900/30', label: 'Fact' };
        case 'preference':
            return { icon: HeartIcon, color: 'text-pink-500', bg: 'bg-pink-100 dark:bg-pink-900/30', label: 'Preference' };
        case 'entity':
            return { icon: BuildingOfficeIcon, color: 'text-purple-500', bg: 'bg-purple-100 dark:bg-purple-900/30', label: 'Entity' };
        case 'project':
            return { icon: FolderIcon, color: 'text-green-500', bg: 'bg-green-100 dark:bg-green-900/30', label: 'Project' };
        case 'working':
            return { icon: ClockIcon, color: 'text-yellow-500', bg: 'bg-yellow-100 dark:bg-yellow-900/30', label: 'Session' };
        default:
            return { icon: LightBulbIcon, color: 'text-gray-500', bg: 'bg-gray-100 dark:bg-gray-900/30', label: type };
    }
};

// Tool category tabs configuration
type ToolTab = 'system' | 'search' | 'processing' | 'workflow';

const TOOL_TABS: { key: ToolTab; label: string; categories: string[] }[] = [
    { key: 'system', label: 'System', categories: ['memory', 'assets'] },
    { key: 'search', label: 'Search', categories: ['search', 'research'] },
    { key: 'processing', label: 'Processing', categories: ['processing'] },
    { key: 'workflow', label: 'Workflow', categories: ['workflow'] },
];

interface ToolsSectionProps {
    availableTools: ToolInfo[];
    enabledTools: Set<string>;
    isExpanded: boolean;
    onToggleExpanded: () => void;
    onToggleTool: (toolId: string) => void;
}

function ToolsSection({ availableTools, enabledTools, isExpanded, onToggleExpanded, onToggleTool }: ToolsSectionProps) {
    const [activeTab, setActiveTab] = useState<ToolTab>('system');

    // Group tools by tab
    const getToolsForTab = (tab: ToolTab) => {
        const tabConfig = TOOL_TABS.find(t => t.key === tab);
        if (!tabConfig) return [];
        return availableTools.filter(tool => tabConfig.categories.includes(tool.category));
    };

    // Count enabled tools per tab
    const getTabCounts = (tab: ToolTab) => {
        const tools = getToolsForTab(tab);
        const enabled = tools.filter(t => enabledTools.has(t.name)).length;
        return { enabled, total: tools.length };
    };

    // Enable/disable all tools in current tab
    const handleEnableAll = () => {
        const tools = getToolsForTab(activeTab);
        tools.forEach(tool => {
            if (!enabledTools.has(tool.name)) {
                onToggleTool(tool.name);
            }
        });
    };

    const handleDisableAll = () => {
        const tools = getToolsForTab(activeTab);
        tools.forEach(tool => {
            if (enabledTools.has(tool.name)) {
                onToggleTool(tool.name);
            }
        });
    };

    const currentTools = getToolsForTab(activeTab);
    const enabledCount = enabledTools.size;

    return (
        <div className="border-b border-gray-200 dark:border-gray-700">
            {/* Header */}
            <div className="px-4 py-3 bg-gray-100 dark:bg-gray-800">
                <button
                    onClick={onToggleExpanded}
                    className="flex items-center gap-2"
                >
                    {isExpanded ? (
                        <ChevronDownIcon className="h-3 w-3 text-gray-500" />
                    ) : (
                        <ChevronRightIcon className="h-3 w-3 text-gray-500" />
                    )}
                    <WrenchScrewdriverIcon className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                    <span className="text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase">
                        Tools
                    </span>
                    <span className="text-xs text-gray-500">({enabledCount}/{availableTools.length})</span>
                </button>
            </div>

            {isExpanded && (
                <div>
                    {/* Tabs */}
                    <div className="flex border-b border-gray-200 dark:border-gray-700">
                        {TOOL_TABS.map(tab => {
                            const counts = getTabCounts(tab.key);
                            if (counts.total === 0) return null;
                            const isActive = activeTab === tab.key;
                            return (
                                <button
                                    key={tab.key}
                                    onClick={() => setActiveTab(tab.key)}
                                    className={`flex-1 px-2 py-2 text-xs font-medium transition-colors ${
                                        isActive
                                            ? 'text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400 bg-blue-50 dark:bg-blue-900/20'
                                            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800'
                                    }`}
                                >
                                    <div>{tab.label}</div>
                                    <div className="text-[10px] opacity-70">
                                        {counts.enabled}/{counts.total}
                                    </div>
                                </button>
                            );
                        })}
                    </div>

                    {/* Enable/Disable All buttons */}
                    <div className="flex gap-1 px-2 py-1.5 border-b border-gray-100 dark:border-gray-800">
                        <button
                            onClick={handleEnableAll}
                            className="flex-1 px-2 py-1 text-[10px] text-green-600 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/20 rounded transition-colors"
                        >
                            Enable All
                        </button>
                        <button
                            onClick={handleDisableAll}
                            className="flex-1 px-2 py-1 text-[10px] text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                        >
                            Disable All
                        </button>
                    </div>

                    {/* Tools list for current tab */}
                    <div className="p-2 space-y-1">
                        {currentTools.length === 0 ? (
                            <div className="text-xs text-gray-400 dark:text-gray-500 text-center py-2">
                                No tools in this category
                            </div>
                        ) : (
                            currentTools.map(tool => {
                                const isEnabled = enabledTools.has(tool.name);
                                return (
                                    <button
                                        key={tool.name}
                                        onClick={() => onToggleTool(tool.name)}
                                        className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-xs transition-colors ${
                                            isEnabled
                                                ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300'
                                                : 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
                                        }`}
                                        title={tool.description}
                                    >
                                        {isEnabled ? (
                                            <CheckIcon className="h-3.5 w-3.5 text-green-500 flex-shrink-0" />
                                        ) : (
                                            <CheckCircleOutlineIcon className="h-3.5 w-3.5 flex-shrink-0" />
                                        )}
                                        <span className="flex-1 text-left">{tool.name}</span>
                                    </button>
                                );
                            })
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

export default function ContextPanel({
    availableTools,
    memories,
    assets,
    profile,
    enabledTools,
    includeProfile,
    workflow,
    onAddWorkingMemory,
    onToggleMemoryPinned,
    onToggleAssetContext,
    onClearAllAssetsFromContext,
    onToggleTool,
    onToggleProfile,
    onExpandMemories,
    onExpandAssets,
    onEditProfile,
    onAbandonWorkflow,
    onViewStepOutput
}: ContextPanelProps) {
    const [newMemoryInput, setNewMemoryInput] = useState('');

    // Section collapse state
    const [isAssetsExpanded, setIsAssetsExpanded] = useState(true);
    const [isToolsExpanded, setIsToolsExpanded] = useState(true);
    const [isMemoriesExpanded, setIsMemoriesExpanded] = useState(true);
    const [isProfileExpanded, setIsProfileExpanded] = useState(false);

    // Memories: pinned + last 3 unpinned
    const pinnedMemories = memories.filter(m => m.is_pinned && m.is_active);
    const recentUnpinnedMemories = memories
        .filter(m => !m.is_pinned && m.is_active)
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        .slice(0, 3);
    const totalMemoryCount = memories.filter(m => m.is_active).length;
    const hiddenMemoryCount = totalMemoryCount - pinnedMemories.length - recentUnpinnedMemories.length;

    // Assets: in context + top 5 recent not in context
    const contextAssets = assets.filter(a => a.is_in_context);
    const recentAvailableAssets = assets
        .filter(a => !a.is_in_context)
        .sort((a, b) => new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime())
        .slice(0, 5);
    const hiddenAssetCount = assets.filter(a => !a.is_in_context).length - recentAvailableAssets.length;

    const handleAddMemory = () => {
        if (newMemoryInput.trim()) {
            onAddWorkingMemory(newMemoryInput.trim());
            setNewMemoryInput('');
        }
    };

    return (
        <div className="flex flex-col h-full">
            {/* Panel Header */}
            <div className="flex items-center justify-between px-4 py-4 border-b border-gray-200 dark:border-gray-700 min-w-[280px]">
                <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
                    Agent Controls
                </h2>
                <Cog6ToothIcon className="h-5 w-5 text-gray-400" />
            </div>

            {/* Panel Content */}
            <div className="flex-1 overflow-y-auto min-w-[280px]">
                {/* Active Workflow Section */}
                {workflow && workflow.status === 'active' && (
                    <div className="border-b border-gray-200 dark:border-gray-700">
                        <div className="px-4 py-3 bg-indigo-100 dark:bg-indigo-900/30">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <PlayIcon className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                                    <span className="text-xs font-semibold text-indigo-700 dark:text-indigo-300 uppercase">
                                        Workflow
                                    </span>
                                </div>
                                <button
                                    onClick={onAbandonWorkflow}
                                    className="p-1 text-gray-400 hover:text-red-500 hover:bg-gray-200 dark:hover:bg-gray-700 rounded"
                                    title="Abandon workflow"
                                >
                                    <XMarkIcon className="h-4 w-4" />
                                </button>
                            </div>
                        </div>
                        <div className="p-3 space-y-2">
                            {/* Workflow title */}
                            <div className="text-sm font-medium text-gray-900 dark:text-white">
                                {workflow.title}
                            </div>

                            {/* Steps list */}
                            <div className="space-y-1.5">
                                {workflow.steps.map((step) => {
                                    const isCompleted = step.status === 'completed';
                                    const isInProgress = step.status === 'in_progress';

                                    return (
                                        <div
                                            key={step.step_number}
                                            className={`flex items-start gap-2 px-2 py-1.5 rounded text-xs ${
                                                isInProgress
                                                    ? 'bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-200 dark:border-indigo-700'
                                                    : isCompleted
                                                        ? 'bg-green-50 dark:bg-green-900/20'
                                                        : 'bg-gray-50 dark:bg-gray-800/50'
                                            }`}
                                        >
                                            {/* Step number / status icon */}
                                            <div className="flex-shrink-0 mt-0.5">
                                                {isCompleted ? (
                                                    <CheckIcon className="h-3.5 w-3.5 text-green-500" />
                                                ) : isInProgress ? (
                                                    <div className="h-3.5 w-3.5 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin" />
                                                ) : (
                                                    <span className="inline-flex items-center justify-center h-3.5 w-3.5 text-[10px] font-medium text-gray-400 rounded-full border border-gray-300 dark:border-gray-600">
                                                        {step.step_number}
                                                    </span>
                                                )}
                                            </div>

                                            {/* Step description */}
                                            <div className="flex-1 min-w-0">
                                                <span className={`${
                                                    isCompleted
                                                        ? 'text-green-700 dark:text-green-300'
                                                        : isInProgress
                                                            ? 'text-indigo-700 dark:text-indigo-300 font-medium'
                                                            : 'text-gray-500 dark:text-gray-400'
                                                }`}>
                                                    {step.description}
                                                </span>
                                            </div>

                                            {/* View output button for completed steps */}
                                            {isCompleted && step.wip_output && (
                                                <button
                                                    onClick={() => onViewStepOutput(step.step_number)}
                                                    className="flex-shrink-0 text-indigo-500 hover:text-indigo-600 dark:text-indigo-400"
                                                    title="View output"
                                                >
                                                    <DocumentTextIcon className="h-3.5 w-3.5" />
                                                </button>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>

                            {/* Progress indicator */}
                            <div className="pt-2">
                                <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 mb-1">
                                    <span>Progress</span>
                                    <span>
                                        {workflow.steps.filter(s => s.status === 'completed').length}/{workflow.steps.length}
                                    </span>
                                </div>
                                <div className="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                                    <div
                                        className="h-full bg-indigo-500 rounded-full transition-all"
                                        style={{
                                            width: `${(workflow.steps.filter(s => s.status === 'completed').length / workflow.steps.length) * 100}%`
                                        }}
                                    />
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* Assets Section */}
                <div className="border-b border-gray-200 dark:border-gray-700">
                    <div className="px-4 py-3 bg-gray-100 dark:bg-gray-800">
                        <div className="flex items-center justify-between">
                            <button
                                onClick={() => setIsAssetsExpanded(!isAssetsExpanded)}
                                className="flex items-center gap-2"
                            >
                                {isAssetsExpanded ? (
                                    <ChevronDownIcon className="h-3 w-3 text-gray-500" />
                                ) : (
                                    <ChevronRightIcon className="h-3 w-3 text-gray-500" />
                                )}
                                <DocumentIcon className="h-4 w-4 text-orange-600 dark:text-orange-400" />
                                <span className="text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase">
                                    Assets
                                </span>
                                <span className="text-xs text-gray-500">({assets.length})</span>
                            </button>
                            <div className="flex items-center gap-1">
                                {contextAssets.length > 0 && (
                                    <button
                                        onClick={onClearAllAssetsFromContext}
                                        className="p-1 text-gray-400 hover:text-orange-500 hover:bg-gray-200 dark:hover:bg-gray-700 rounded"
                                        title="Clear all from context"
                                    >
                                        <XCircleIcon className="h-4 w-4" />
                                    </button>
                                )}
                                <button
                                    onClick={onExpandAssets}
                                    className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 rounded"
                                    title="Expand assets"
                                >
                                    <ArrowsPointingOutIcon className="h-4 w-4" />
                                </button>
                            </div>
                        </div>
                    </div>
                    {isAssetsExpanded && (
                        <div className="p-2 space-y-1">
                            {/* Assets in context */}
                            {contextAssets.length === 0 ? (
                                <div className="text-center text-gray-400 dark:text-gray-500 text-xs py-2">
                                    No assets in context
                                </div>
                            ) : (
                                <>
                                    <div className="text-xs text-gray-500 dark:text-gray-400 px-2 py-1 font-medium">
                                        In Context ({contextAssets.length})
                                    </div>
                                    {contextAssets.map((asset) => (
                                        <div key={asset.asset_id} className="flex items-center gap-2 px-2 py-1.5 rounded bg-orange-50 dark:bg-orange-900/20">
                                            <span className="flex-1 text-gray-700 dark:text-gray-300 text-xs truncate">{asset.name}</span>
                                            <button
                                                onClick={() => onToggleAssetContext(asset.asset_id)}
                                                className="text-gray-400 hover:text-red-500 flex-shrink-0"
                                                title="Remove from context"
                                            >
                                                <XMarkIcon className="h-3 w-3" />
                                            </button>
                                        </div>
                                    ))}
                                </>
                            )}

                            {/* Recent available assets (top 5) */}
                            {recentAvailableAssets.length > 0 && (
                                <>
                                    <div className="text-xs text-gray-400 dark:text-gray-500 px-2 py-1 mt-2">
                                        Recent
                                    </div>
                                    {recentAvailableAssets.map((asset) => (
                                        <button
                                            key={asset.asset_id}
                                            onClick={() => onToggleAssetContext(asset.asset_id)}
                                            className="w-full text-left flex items-center gap-2 px-2 py-1.5 rounded text-xs text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"
                                        >
                                            <PlusIcon className="h-3 w-3" />
                                            <span className="truncate">{asset.name}</span>
                                        </button>
                                    ))}
                                    {hiddenAssetCount > 0 && (
                                        <button
                                            onClick={onExpandAssets}
                                            className="w-full text-xs text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 py-1"
                                        >
                                            +{hiddenAssetCount} more...
                                        </button>
                                    )}
                                </>
                            )}
                        </div>
                    )}
                </div>

                {/* Tools Section */}
                <ToolsSection
                    availableTools={availableTools}
                    enabledTools={enabledTools}
                    isExpanded={isToolsExpanded}
                    onToggleExpanded={() => setIsToolsExpanded(!isToolsExpanded)}
                    onToggleTool={onToggleTool}
                />

                {/* Memories Section */}
                <div className="border-b border-gray-200 dark:border-gray-700">
                    <div className="px-4 py-3 bg-gray-100 dark:bg-gray-800">
                        <div className="flex items-center justify-between">
                            <button
                                onClick={() => setIsMemoriesExpanded(!isMemoriesExpanded)}
                                className="flex items-center gap-2"
                            >
                                {isMemoriesExpanded ? (
                                    <ChevronDownIcon className="h-3 w-3 text-gray-500" />
                                ) : (
                                    <ChevronRightIcon className="h-3 w-3 text-gray-500" />
                                )}
                                <LightBulbIcon className="h-4 w-4 text-yellow-600 dark:text-yellow-400" />
                                <span className="text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase">
                                    Memories
                                </span>
                                <span className="text-xs text-gray-500">({totalMemoryCount})</span>
                            </button>
                            <button
                                onClick={onExpandMemories}
                                className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 rounded"
                                title="Expand memories"
                            >
                                <ArrowsPointingOutIcon className="h-4 w-4" />
                            </button>
                        </div>
                    </div>

                    {isMemoriesExpanded && (
                        <>
                            {/* Quick add note */}
                            <div className="px-3 py-2 border-b border-gray-200 dark:border-gray-700">
                                <div className="flex gap-1">
                                    <input
                                        type="text"
                                        value={newMemoryInput}
                                        onChange={(e) => setNewMemoryInput(e.target.value)}
                                        onKeyDown={(e) => e.key === 'Enter' && handleAddMemory()}
                                        placeholder="Quick note..."
                                        className="flex-1 px-2 py-1 text-xs rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                                    />
                                    <button
                                        onClick={handleAddMemory}
                                        className="px-2 py-1 text-xs bg-yellow-500 text-white rounded hover:bg-yellow-600"
                                    >
                                        +
                                    </button>
                                </div>
                            </div>

                            {/* Pinned + Recent memories */}
                            <div className="p-2 space-y-1">
                                {pinnedMemories.length === 0 && recentUnpinnedMemories.length === 0 ? (
                                    <div className="text-center text-gray-400 dark:text-gray-500 text-xs py-3">
                                        No memories yet
                                    </div>
                                ) : (
                                    <>
                                        {/* Pinned memories */}
                                        {pinnedMemories.map((mem) => {
                                            const typeInfo = getMemoryTypeInfo(mem.memory_type);
                                            return (
                                                <div
                                                    key={mem.memory_id}
                                                    className={`flex items-start gap-2 px-2 py-1.5 rounded ${typeInfo.bg}`}
                                                >
                                                    <BookmarkIcon className="h-3 w-3 mt-0.5 flex-shrink-0 text-blue-500" />
                                                    <span className="flex-1 text-gray-700 dark:text-gray-300 text-xs leading-relaxed line-clamp-2">
                                                        {mem.content}
                                                    </span>
                                                    <button
                                                        onClick={() => onToggleMemoryPinned(mem.memory_id)}
                                                        className="text-blue-500 hover:text-blue-600 flex-shrink-0"
                                                        title="Unpin"
                                                    >
                                                        <XMarkIcon className="h-3 w-3" />
                                                    </button>
                                                </div>
                                            );
                                        })}

                                        {/* Divider if both pinned and recent exist */}
                                        {pinnedMemories.length > 0 && recentUnpinnedMemories.length > 0 && (
                                            <div className="text-xs text-gray-400 dark:text-gray-500 px-2 py-1">
                                                Recent
                                            </div>
                                        )}

                                        {/* Recent unpinned memories */}
                                        {recentUnpinnedMemories.map((mem) => {
                                            const typeInfo = getMemoryTypeInfo(mem.memory_type);
                                            const TypeIcon = typeInfo.icon;
                                            return (
                                                <div
                                                    key={mem.memory_id}
                                                    className="flex items-start gap-2 px-2 py-1.5 rounded bg-gray-50 dark:bg-gray-800/50"
                                                >
                                                    <TypeIcon className={`h-3 w-3 mt-0.5 flex-shrink-0 ${typeInfo.color}`} />
                                                    <span className="flex-1 text-gray-700 dark:text-gray-300 text-xs leading-relaxed line-clamp-2">
                                                        {mem.content}
                                                    </span>
                                                    <button
                                                        onClick={() => onToggleMemoryPinned(mem.memory_id)}
                                                        className="text-gray-400 hover:text-blue-500 flex-shrink-0"
                                                        title="Pin"
                                                    >
                                                        <BookmarkIcon className="h-3 w-3" />
                                                    </button>
                                                </div>
                                            );
                                        })}

                                        {/* Show more indicator */}
                                        {hiddenMemoryCount > 0 && (
                                            <button
                                                onClick={onExpandMemories}
                                                className="w-full text-xs text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 py-1"
                                            >
                                                +{hiddenMemoryCount} more...
                                            </button>
                                        )}
                                    </>
                                )}
                            </div>
                        </>
                    )}
                </div>

                {/* Profile Section */}
                <div className="border-b border-gray-200 dark:border-gray-700">
                    <div className="px-4 py-3 bg-gray-100 dark:bg-gray-800">
                        <div className="flex items-center justify-between">
                            <button
                                onClick={() => setIsProfileExpanded(!isProfileExpanded)}
                                className="flex items-center gap-2"
                            >
                                {isProfileExpanded ? (
                                    <ChevronDownIcon className="h-3 w-3 text-gray-500" />
                                ) : (
                                    <ChevronRightIcon className="h-3 w-3 text-gray-500" />
                                )}
                                <UserCircleIcon className={`h-4 w-4 ${includeProfile ? 'text-green-500' : 'text-gray-400'}`} />
                                <span className="text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase">
                                    Profile
                                </span>
                            </button>
                            <div className="flex items-center gap-1">
                                <button
                                    onClick={onEditProfile}
                                    className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 rounded"
                                    title="Edit profile"
                                >
                                    <PencilIcon className="h-3.5 w-3.5" />
                                </button>
                                <button
                                    onClick={onToggleProfile}
                                    className="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded"
                                    title={includeProfile ? 'Exclude from context' : 'Include in context'}
                                >
                                    {includeProfile ? (
                                        <CheckIcon className="h-4 w-4 text-green-500" />
                                    ) : (
                                        <CheckCircleOutlineIcon className="h-4 w-4 text-gray-400" />
                                    )}
                                </button>
                            </div>
                        </div>
                    </div>
                    {isProfileExpanded && (
                        <div className="p-3 space-y-2">
                            {profile ? (
                                <>
                                    {profile.full_name && (
                                        <div className="text-xs">
                                            <span className="text-gray-500 dark:text-gray-400">Name: </span>
                                            <span className="text-gray-700 dark:text-gray-300">{profile.full_name}</span>
                                        </div>
                                    )}
                                    {profile.display_name && (
                                        <div className="text-xs">
                                            <span className="text-gray-500 dark:text-gray-400">Display: </span>
                                            <span className="text-gray-700 dark:text-gray-300">{profile.display_name}</span>
                                        </div>
                                    )}
                                    {profile.bio && (
                                        <div className="text-xs">
                                            <span className="text-gray-500 dark:text-gray-400">Bio: </span>
                                            <span className="text-gray-700 dark:text-gray-300">{profile.bio}</span>
                                        </div>
                                    )}
                                    {profile.preferences && Object.keys(profile.preferences).length > 0 && (
                                        <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-700">
                                            <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Preferences:</div>
                                            {Object.entries(profile.preferences).map(([key, value]) => (
                                                <div key={key} className="text-xs">
                                                    <span className="text-gray-500 dark:text-gray-400">{key}: </span>
                                                    <span className="text-gray-700 dark:text-gray-300">{String(value)}</span>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                    {!profile.full_name && !profile.display_name && !profile.bio && Object.keys(profile.preferences || {}).length === 0 && (
                                        <div className="text-xs text-gray-400 dark:text-gray-500 italic">
                                            No profile info set. Click edit to add.
                                        </div>
                                    )}
                                </>
                            ) : (
                                <div className="text-xs text-gray-400 dark:text-gray-500">
                                    Loading profile...
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
