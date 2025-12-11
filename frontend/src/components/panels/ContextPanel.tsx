import { useState } from 'react';
import {
    WrenchScrewdriverIcon, XMarkIcon, PlusIcon, DocumentIcon,
    LightBulbIcon, BookmarkIcon, Cog6ToothIcon,
    ArrowsPointingOutIcon, UserIcon, HeartIcon, BuildingOfficeIcon,
    FolderIcon, ClockIcon, XCircleIcon, CheckIcon, UserCircleIcon
} from '@heroicons/react/24/solid';
import { CheckCircleIcon as CheckCircleOutlineIcon } from '@heroicons/react/24/outline';
import { Memory, MemoryType, Asset } from '../../lib/api';

// Available tools that can be enabled/disabled
const AVAILABLE_TOOLS = [
    { id: 'web_search', name: 'Web Search', description: 'Search the web for information' },
    { id: 'fetch_webpage', name: 'Fetch Webpage', description: 'Retrieve content from URLs' },
    { id: 'save_memory', name: 'Save Memory', description: 'Save information to memory' },
    { id: 'search_memory', name: 'Search Memory', description: 'Search saved memories' },
];

interface ContextPanelProps {
    memories: Memory[];
    assets: Asset[];
    enabledTools: Set<string>;
    includeProfile: boolean;
    onAddWorkingMemory: (content: string) => void;
    onToggleMemoryPinned: (memId: number) => void;
    onToggleAssetContext: (assetId: number) => void;
    onClearAllAssetsFromContext: () => void;
    onToggleTool: (toolId: string) => void;
    onToggleProfile: () => void;
    onExpandMemories: () => void;
    onExpandAssets: () => void;
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

export default function ContextPanel({
    memories,
    assets,
    enabledTools,
    includeProfile,
    onAddWorkingMemory,
    onToggleMemoryPinned,
    onToggleAssetContext,
    onClearAllAssetsFromContext,
    onToggleTool,
    onToggleProfile,
    onExpandMemories,
    onExpandAssets
}: ContextPanelProps) {
    const [newMemoryInput, setNewMemoryInput] = useState('');

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

    const enabledToolCount = enabledTools.size;

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
                {/* Profile Section */}
                <div className="border-b border-gray-200 dark:border-gray-700">
                    <button
                        onClick={onToggleProfile}
                        className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
                    >
                        <div className="flex items-center gap-2">
                            <UserCircleIcon className={`h-4 w-4 ${includeProfile ? 'text-green-500' : 'text-gray-400'}`} />
                            <span className="text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase">
                                Profile Info
                            </span>
                        </div>
                        {includeProfile ? (
                            <CheckIcon className="h-4 w-4 text-green-500" />
                        ) : (
                            <CheckCircleOutlineIcon className="h-4 w-4 text-gray-400" />
                        )}
                    </button>
                </div>

                {/* Tools Section */}
                <div className="border-b border-gray-200 dark:border-gray-700">
                    <div className="px-4 py-3 bg-gray-100 dark:bg-gray-800">
                        <div className="flex items-center gap-2">
                            <WrenchScrewdriverIcon className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                            <span className="text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase">
                                Tools
                            </span>
                            <span className="text-xs text-gray-500">({enabledToolCount}/{AVAILABLE_TOOLS.length})</span>
                        </div>
                    </div>
                    <div className="p-2 space-y-1">
                        {AVAILABLE_TOOLS.map(tool => {
                            const isEnabled = enabledTools.has(tool.id);
                            return (
                                <button
                                    key={tool.id}
                                    onClick={() => onToggleTool(tool.id)}
                                    className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-xs transition-colors ${
                                        isEnabled
                                            ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300'
                                            : 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
                                    }`}
                                >
                                    {isEnabled ? (
                                        <CheckIcon className="h-3.5 w-3.5 text-green-500 flex-shrink-0" />
                                    ) : (
                                        <CheckCircleOutlineIcon className="h-3.5 w-3.5 flex-shrink-0" />
                                    )}
                                    <span className="flex-1 text-left">{tool.name}</span>
                                </button>
                            );
                        })}
                    </div>
                </div>

                {/* Memories Section */}
                <div className="border-b border-gray-200 dark:border-gray-700">
                    <div className="px-4 py-3 bg-gray-100 dark:bg-gray-800">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <LightBulbIcon className="h-4 w-4 text-yellow-600 dark:text-yellow-400" />
                                <span className="text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase">
                                    Memories
                                </span>
                                <span className="text-xs text-gray-500">({totalMemoryCount})</span>
                            </div>
                            <button
                                onClick={onExpandMemories}
                                className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 rounded"
                                title="Expand memories"
                            >
                                <ArrowsPointingOutIcon className="h-4 w-4" />
                            </button>
                        </div>
                    </div>

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
                </div>

                {/* Assets Section */}
                <div className="border-b border-gray-200 dark:border-gray-700">
                    <div className="px-4 py-3 bg-gray-100 dark:bg-gray-800">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <DocumentIcon className="h-4 w-4 text-orange-600 dark:text-orange-400" />
                                <span className="text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase">
                                    Assets
                                </span>
                                <span className="text-xs text-gray-500">({assets.length})</span>
                            </div>
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
                </div>
            </div>
        </div>
    );
}
