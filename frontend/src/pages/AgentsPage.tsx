import React, { useState, useEffect, useCallback, useRef } from 'react';
import { PlusIcon, PlayIcon, PauseIcon, TrashIcon, ArrowPathIcon, ChevronDownIcon, ChevronUpIcon, DocumentTextIcon, PencilIcon } from '@heroicons/react/24/outline';
import { agentApi, Agent, AgentDetail, AgentRun, AgentRunEvent, AgentAsset, AgentLifecycle, AgentStatus, AgentRunEventType, CreateAgentRequest, UpdateAgentRequest, workflowApi, ToolInfo } from '../lib/api';

/**
 * Agents Dashboard
 *
 * Displays autonomous background agents with their status, lifecycle type, and recent runs.
 */
export default function AgentsPage() {
    const [agents, setAgents] = useState<Agent[]>([]);
    const [selectedAgent, setSelectedAgent] = useState<AgentDetail | null>(null);
    const [agentAssets, setAgentAssets] = useState<AgentAsset[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
    const [isEditModalOpen, setIsEditModalOpen] = useState(false);
    const [availableTools, setAvailableTools] = useState<ToolInfo[]>([]);

    // Load agents and tools on mount
    useEffect(() => {
        const loadData = async () => {
            try {
                const [agentList, tools] = await Promise.all([
                    agentApi.list(),
                    workflowApi.getTools()
                ]);
                setAgents(agentList);
                setAvailableTools(tools);
            } catch (err) {
                setError('Failed to load agents');
                console.error(err);
            } finally {
                setIsLoading(false);
            }
        };
        loadData();
    }, []);

    // Refresh agents list
    const refreshAgents = useCallback(async () => {
        try {
            const agentList = await agentApi.list();
            setAgents(agentList);
        } catch (err) {
            console.error('Failed to refresh agents:', err);
        }
    }, []);

    // Select agent and load details
    const handleSelectAgent = useCallback(async (agentId: number) => {
        try {
            const [detail, assets] = await Promise.all([
                agentApi.get(agentId),
                agentApi.getAgentAssets(agentId).catch(() => []) // Gracefully handle if columns don't exist yet
            ]);
            setSelectedAgent({ ...detail, recent_runs: [...detail.recent_runs] });
            setAgentAssets(assets);
        } catch (err) {
            console.error('Failed to load agent details:', err);
        }
    }, []);

    // Refresh current agent (with loading indicator)
    const handleRefresh = useCallback(async () => {
        if (!selectedAgent) return;
        setIsRefreshing(true);
        try {
            const [agentList, detail, assets] = await Promise.all([
                agentApi.list(),
                agentApi.get(selectedAgent.agent_id),
                agentApi.getAgentAssets(selectedAgent.agent_id).catch(() => [])
            ]);
            setAgents(agentList);
            setSelectedAgent({ ...detail, recent_runs: [...detail.recent_runs] });
            setAgentAssets(assets);
        } catch (err) {
            console.error('Failed to refresh:', err);
        } finally {
            setIsRefreshing(false);
        }
    }, [selectedAgent]);

    // Pause agent
    const handlePauseAgent = useCallback(async (agentId: number, e: React.MouseEvent) => {
        e.stopPropagation();
        try {
            await agentApi.pause(agentId);
            await refreshAgents();
            if (selectedAgent?.agent_id === agentId) {
                handleSelectAgent(agentId);
            }
        } catch (err) {
            console.error('Failed to pause agent:', err);
        }
    }, [refreshAgents, selectedAgent, handleSelectAgent]);

    // Resume agent
    const handleResumeAgent = useCallback(async (agentId: number, e: React.MouseEvent) => {
        e.stopPropagation();
        try {
            await agentApi.resume(agentId);
            await refreshAgents();
            if (selectedAgent?.agent_id === agentId) {
                handleSelectAgent(agentId);
            }
        } catch (err) {
            console.error('Failed to resume agent:', err);
        }
    }, [refreshAgents, selectedAgent, handleSelectAgent]);

    // Trigger manual run
    const handleTriggerRun = useCallback(async (agentId: number, e: React.MouseEvent) => {
        e.stopPropagation();
        try {
            await agentApi.triggerRun(agentId);
            await refreshAgents();
            if (selectedAgent?.agent_id === agentId) {
                handleSelectAgent(agentId);
            }
        } catch (err) {
            console.error('Failed to trigger run:', err);
        }
    }, [refreshAgents, selectedAgent, handleSelectAgent]);

    // Delete agent
    const handleDeleteAgent = useCallback(async (agentId: number, e: React.MouseEvent) => {
        e.stopPropagation();
        if (!confirm('Are you sure you want to delete this agent?')) return;
        try {
            await agentApi.delete(agentId);
            await refreshAgents();
            if (selectedAgent?.agent_id === agentId) {
                setSelectedAgent(null);
            }
        } catch (err) {
            console.error('Failed to delete agent:', err);
        }
    }, [refreshAgents, selectedAgent]);

    // Create agent
    const handleCreateAgent = useCallback(async (data: CreateAgentRequest) => {
        try {
            await agentApi.create(data);
            await refreshAgents();
            setIsCreateModalOpen(false);
        } catch (err) {
            console.error('Failed to create agent:', err);
        }
    }, [refreshAgents]);

    // Update agent
    const handleUpdateAgent = useCallback(async (agentId: number, data: UpdateAgentRequest) => {
        try {
            await agentApi.update(agentId, data);
            await refreshAgents();
            await handleSelectAgent(agentId);
            setIsEditModalOpen(false);
        } catch (err) {
            console.error('Failed to update agent:', err);
        }
    }, [refreshAgents, handleSelectAgent]);

    // Format relative time
    const formatRelativeTime = (dateStr: string | null) => {
        if (!dateStr) return 'Never';
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffMins = Math.floor(diffMs / 60000);
        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        const diffHours = Math.floor(diffMins / 60);
        if (diffHours < 24) return `${diffHours}h ago`;
        const diffDays = Math.floor(diffHours / 24);
        return `${diffDays}d ago`;
    };

    // Get lifecycle badge color
    const getLifecycleBadge = (lifecycle: AgentLifecycle) => {
        const badges: Record<AgentLifecycle, { color: string; label: string }> = {
            one_shot: { color: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200', label: 'One-Shot' },
            scheduled: { color: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200', label: 'Scheduled' },
            monitor: { color: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200', label: 'Monitor' }
        };
        return badges[lifecycle];
    };

    // Get status badge color
    const getStatusBadge = (status: AgentStatus) => {
        const badges: Record<AgentStatus, { color: string; label: string }> = {
            active: { color: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200', label: 'Active' },
            paused: { color: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200', label: 'Paused' },
            completed: { color: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200', label: 'Completed' },
            failed: { color: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200', label: 'Failed' }
        };
        return badges[status];
    };

    if (isLoading) {
        return (
            <div className="h-full flex items-center justify-center">
                <div className="text-gray-500 dark:text-gray-400">Loading agents...</div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="h-full flex items-center justify-center">
                <div className="text-red-500">{error}</div>
            </div>
        );
    }

    return (
        <div className="h-full flex">
            {/* Agent List */}
            <div className="w-80 border-r border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 flex flex-col">
                <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Agents</h2>
                    <button
                        onClick={() => setIsCreateModalOpen(true)}
                        className="p-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors"
                        title="Create new agent"
                    >
                        <PlusIcon className="h-5 w-5" />
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto p-2 space-y-2">
                    {agents.length === 0 ? (
                        <div className="text-center text-gray-500 dark:text-gray-400 py-8">
                            No agents yet. Create one to get started.
                        </div>
                    ) : (
                        agents.map(agent => {
                            const lifecycleBadge = getLifecycleBadge(agent.lifecycle);
                            const statusBadge = getStatusBadge(agent.status);
                            const isSelected = selectedAgent?.agent_id === agent.agent_id;

                            return (
                                <div
                                    key={agent.agent_id}
                                    onClick={() => handleSelectAgent(agent.agent_id)}
                                    className={`p-3 rounded-lg cursor-pointer transition-colors ${
                                        isSelected
                                            ? 'bg-blue-100 dark:bg-blue-900 border border-blue-300 dark:border-blue-700'
                                            : 'bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700'
                                    }`}
                                >
                                    <div className="flex items-start justify-between">
                                        <div className="flex-1 min-w-0">
                                            <h3 className="font-medium text-gray-900 dark:text-white truncate">
                                                {agent.name}
                                            </h3>
                                            <div className="flex items-center gap-2 mt-1">
                                                <span className={`px-2 py-0.5 text-xs font-medium rounded ${lifecycleBadge.color}`}>
                                                    {lifecycleBadge.label}
                                                </span>
                                                <span className={`px-2 py-0.5 text-xs font-medium rounded ${statusBadge.color}`}>
                                                    {statusBadge.label}
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                                        {agent.total_runs} runs | {agent.total_assets_created} assets
                                    </div>
                                    <div className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                                        Last run: {formatRelativeTime(agent.last_run_at)}
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>
            </div>

            {/* Agent Details */}
            <div className="flex-1 bg-white dark:bg-gray-800 overflow-y-auto">
                {selectedAgent ? (
                    <div className="p-6">
                        <div className="flex items-start justify-between mb-6">
                            <div>
                                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                                    {selectedAgent.name}
                                </h1>
                                {selectedAgent.description && (
                                    <p className="mt-1 text-gray-600 dark:text-gray-300">
                                        {selectedAgent.description}
                                    </p>
                                )}
                                <div className="flex items-center gap-3 mt-3">
                                    <span className={`px-3 py-1 text-sm font-medium rounded ${getLifecycleBadge(selectedAgent.lifecycle).color}`}>
                                        {getLifecycleBadge(selectedAgent.lifecycle).label}
                                    </span>
                                    <span className={`px-3 py-1 text-sm font-medium rounded ${getStatusBadge(selectedAgent.status).color}`}>
                                        {getStatusBadge(selectedAgent.status).label}
                                    </span>
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={handleRefresh}
                                    disabled={isRefreshing}
                                    className="p-2 bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 rounded-md transition-colors disabled:opacity-50"
                                    title="Refresh"
                                >
                                    <ArrowPathIcon className={`h-5 w-5 ${isRefreshing ? 'animate-spin' : ''}`} />
                                </button>
                                <button
                                    onClick={() => setIsEditModalOpen(true)}
                                    className="p-2 bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 rounded-md transition-colors"
                                    title="Edit agent"
                                >
                                    <PencilIcon className="h-5 w-5" />
                                </button>
                                {selectedAgent.status === 'active' && (
                                    <>
                                        <button
                                            onClick={(e) => handleTriggerRun(selectedAgent.agent_id, e)}
                                            className="p-2 bg-green-600 hover:bg-green-700 text-white rounded-md transition-colors"
                                            title="Run now"
                                        >
                                            <PlayIcon className="h-5 w-5" />
                                        </button>
                                        <button
                                            onClick={(e) => handlePauseAgent(selectedAgent.agent_id, e)}
                                            className="p-2 bg-yellow-600 hover:bg-yellow-700 text-white rounded-md transition-colors"
                                            title="Pause agent"
                                        >
                                            <PauseIcon className="h-5 w-5" />
                                        </button>
                                    </>
                                )}
                                {selectedAgent.status === 'paused' && (
                                    <button
                                        onClick={(e) => handleResumeAgent(selectedAgent.agent_id, e)}
                                        className="p-2 bg-green-600 hover:bg-green-700 text-white rounded-md transition-colors"
                                        title="Resume agent"
                                    >
                                        <PlayIcon className="h-5 w-5" />
                                    </button>
                                )}
                                <button
                                    onClick={(e) => handleDeleteAgent(selectedAgent.agent_id, e)}
                                    className="p-2 bg-red-600 hover:bg-red-700 text-white rounded-md transition-colors"
                                    title="Delete agent"
                                >
                                    <TrashIcon className="h-5 w-5" />
                                </button>
                            </div>
                        </div>

                        {/* Instructions */}
                        <div className="mb-6">
                            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">Instructions</h2>
                            <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
                                <pre className="whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-300 font-mono">
                                    {selectedAgent.instructions}
                                </pre>
                            </div>
                        </div>

                        {/* Stats & Info */}
                        <div className="grid grid-cols-2 gap-4 mb-6">
                            <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
                                <div className="flex items-baseline gap-4 mb-2">
                                    <div>
                                        <span className="text-2xl font-bold text-gray-900 dark:text-white">{selectedAgent.total_runs}</span>
                                        <span className="text-sm text-gray-500 dark:text-gray-400 ml-1">runs</span>
                                    </div>
                                    <div>
                                        <span className="text-2xl font-bold text-gray-900 dark:text-white">{selectedAgent.total_assets_created}</span>
                                        <span className="text-sm text-gray-500 dark:text-gray-400 ml-1">assets</span>
                                    </div>
                                </div>
                                <div className="text-sm text-gray-600 dark:text-gray-300">
                                    <span className="font-medium">Lifecycle:</span> {getLifecycleBadge(selectedAgent.lifecycle).label}
                                    {selectedAgent.lifecycle === 'monitor' && selectedAgent.monitor_interval_minutes && (
                                        <span className="text-gray-500 dark:text-gray-400"> (every {selectedAgent.monitor_interval_minutes}m)</span>
                                    )}
                                </div>
                                {selectedAgent.next_run_at && (
                                    <div className="text-sm text-gray-600 dark:text-gray-300 mt-1">
                                        <span className="font-medium">Next run:</span> {new Date(selectedAgent.next_run_at).toLocaleString()}
                                    </div>
                                )}
                            </div>
                            <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
                                <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                    Tools ({selectedAgent.tools.length})
                                </div>
                                {selectedAgent.tools.length === 0 ? (
                                    <div className="text-sm text-gray-500 dark:text-gray-400">No tools configured</div>
                                ) : (
                                    <div className="flex flex-wrap gap-1">
                                        {selectedAgent.tools.map(tool => (
                                            <span
                                                key={tool}
                                                className="px-2 py-0.5 text-xs bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 rounded"
                                            >
                                                {tool}
                                            </span>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Recent Runs */}
                        <div className="mb-6">
                            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">Recent Runs</h2>
                            {selectedAgent.recent_runs.length === 0 ? (
                                <div className="text-gray-500 dark:text-gray-400 py-4">No runs yet</div>
                            ) : (
                                <div className="space-y-2 max-h-96 overflow-y-auto">
                                    {selectedAgent.recent_runs.map(run => (
                                        <RunCard
                                            key={run.run_id}
                                            run={run}
                                            formatRelativeTime={formatRelativeTime}
                                        />
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Assets Created */}
                        <div>
                            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">Assets Created</h2>
                            {agentAssets.length === 0 ? (
                                <div className="text-gray-500 dark:text-gray-400 py-4">No assets created yet</div>
                            ) : (
                                <div className="space-y-2">
                                    {agentAssets.map(asset => (
                                        <div
                                            key={asset.asset_id}
                                            className="p-3 bg-gray-50 dark:bg-gray-700 rounded-lg flex items-start gap-3"
                                        >
                                            <DocumentTextIcon className="h-5 w-5 text-blue-500 flex-shrink-0 mt-0.5" />
                                            <div className="flex-1 min-w-0">
                                                <div className="font-medium text-gray-900 dark:text-white truncate">
                                                    {asset.name}
                                                </div>
                                                <div className="text-sm text-gray-500 dark:text-gray-400">
                                                    {asset.asset_type} • {formatRelativeTime(asset.created_at)}
                                                    {asset.run_id && ` • Run #${asset.run_id}`}
                                                </div>
                                                {asset.description && (
                                                    <div className="text-sm text-gray-600 dark:text-gray-300 mt-1 truncate">
                                                        {asset.description}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                ) : (
                    <div className="h-full flex items-center justify-center text-gray-500 dark:text-gray-400">
                        Select an agent to view details
                    </div>
                )}
            </div>

            {/* Create Agent Modal */}
            {isCreateModalOpen && (
                <CreateAgentModal
                    availableTools={availableTools}
                    onClose={() => setIsCreateModalOpen(false)}
                    onCreate={handleCreateAgent}
                />
            )}

            {/* Edit Agent Modal */}
            {isEditModalOpen && selectedAgent && (
                <EditAgentModal
                    agent={selectedAgent}
                    availableTools={availableTools}
                    onClose={() => setIsEditModalOpen(false)}
                    onUpdate={(data) => handleUpdateAgent(selectedAgent.agent_id, data)}
                />
            )}
        </div>
    );
}

// Tool tabs configuration (matching ContextPanel)
type ToolTab = 'system' | 'search' | 'process' | 'workflow' | 'agents' | 'mail';

const TOOL_TABS: { key: ToolTab; label: string; categories: string[] }[] = [
    { key: 'system', label: 'Sys', categories: ['memory', 'assets'] },
    { key: 'search', label: 'Search', categories: ['search', 'research'] },
    { key: 'process', label: 'Process', categories: ['processing'] },
    { key: 'workflow', label: 'Flow', categories: ['workflow'] },
    { key: 'agents', label: 'Agents', categories: ['agents'] },
    { key: 'mail', label: 'Mail', categories: ['integrations', 'email'] },
];

// Tool Selector Component
function ToolSelector({
    availableTools,
    selectedTools,
    setSelectedTools
}: {
    availableTools: ToolInfo[];
    selectedTools: Set<string>;
    setSelectedTools: React.Dispatch<React.SetStateAction<Set<string>>>;
}) {
    const [activeTab, setActiveTab] = useState<ToolTab>('search');

    // Get tools for current tab
    const getToolsForTab = (tab: ToolTab) => {
        const tabConfig = TOOL_TABS.find(t => t.key === tab);
        if (!tabConfig) return [];
        return availableTools.filter(tool => tabConfig.categories.includes(tool.category));
    };

    // Count selected tools per tab
    const getTabCounts = (tab: ToolTab) => {
        const tools = getToolsForTab(tab);
        const selected = tools.filter(t => selectedTools.has(t.name)).length;
        return { selected, total: tools.length };
    };

    const toggleTool = (toolName: string) => {
        setSelectedTools(prev => {
            const next = new Set(prev);
            if (next.has(toolName)) {
                next.delete(toolName);
            } else {
                next.add(toolName);
            }
            return next;
        });
    };

    const selectAllInTab = () => {
        const tools = getToolsForTab(activeTab);
        setSelectedTools(prev => new Set([...prev, ...tools.map(t => t.name)]));
    };

    const clearAllInTab = () => {
        const toolNames = new Set(getToolsForTab(activeTab).map(t => t.name));
        setSelectedTools(prev => new Set([...prev].filter(t => !toolNames.has(t))));
    };

    const currentTools = getToolsForTab(activeTab);

    return (
        <div>
            <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                    Tools ({selectedTools.size} selected)
                </label>
            </div>

            {/* Tabs */}
            <div className="flex border border-gray-300 dark:border-gray-600 rounded-t-md overflow-hidden">
                {TOOL_TABS.map(tab => {
                    const counts = getTabCounts(tab.key);
                    if (counts.total === 0) return null;
                    const isActive = activeTab === tab.key;
                    return (
                        <button
                            key={tab.key}
                            type="button"
                            onClick={() => setActiveTab(tab.key)}
                            className={`flex-1 px-1 py-2 text-xs font-medium transition-colors border-r last:border-r-0 border-gray-300 dark:border-gray-600 ${
                                isActive
                                    ? 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30'
                                    : 'text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700'
                            }`}
                        >
                            <div className="truncate">{tab.label}</div>
                            <div className="text-[10px] opacity-70">
                                {counts.selected}/{counts.total}
                            </div>
                        </button>
                    );
                })}
            </div>

            {/* Enable/Disable buttons */}
            <div className="flex gap-1 px-2 py-1.5 border-x border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-800">
                <button
                    type="button"
                    onClick={selectAllInTab}
                    className="flex-1 px-2 py-1 text-[10px] text-green-600 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/20 rounded transition-colors"
                >
                    Select All
                </button>
                <button
                    type="button"
                    onClick={clearAllInTab}
                    className="flex-1 px-2 py-1 text-[10px] text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                >
                    Clear All
                </button>
            </div>

            {/* Tools list */}
            <div className="max-h-48 overflow-y-auto border border-t-0 border-gray-300 dark:border-gray-600 rounded-b-md">
                {currentTools.length === 0 ? (
                    <div className="p-3 text-sm text-gray-500 dark:text-gray-400 text-center">
                        No tools in this category
                    </div>
                ) : (
                    <div className="p-1">
                        {currentTools.map(tool => (
                            <label
                                key={tool.name}
                                className="flex items-start gap-2 p-2 hover:bg-gray-50 dark:hover:bg-gray-700 rounded cursor-pointer"
                            >
                                <input
                                    type="checkbox"
                                    checked={selectedTools.has(tool.name)}
                                    onChange={() => toggleTool(tool.name)}
                                    className="mt-0.5 rounded border-gray-300 dark:border-gray-600"
                                />
                                <div className="flex-1 min-w-0">
                                    <div className="text-sm font-medium text-gray-900 dark:text-white">
                                        {tool.name}
                                    </div>
                                    <div className="text-xs text-gray-500 dark:text-gray-400 line-clamp-2">
                                        {tool.description}
                                    </div>
                                </div>
                            </label>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

// Create Agent Modal Component
function CreateAgentModal({
    availableTools,
    onClose,
    onCreate
}: {
    availableTools: ToolInfo[];
    onClose: () => void;
    onCreate: (data: CreateAgentRequest) => void;
}) {
    const [name, setName] = useState('');
    const [description, setDescription] = useState('');
    const [instructions, setInstructions] = useState('');
    const [lifecycle, setLifecycle] = useState<AgentLifecycle>('one_shot');
    const [selectedTools, setSelectedTools] = useState<Set<string>>(new Set());
    const [monitorInterval, setMonitorInterval] = useState(60);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        onCreate({
            name,
            description: description || undefined,
            instructions,
            lifecycle,
            tools: Array.from(selectedTools),
            monitor_interval_minutes: lifecycle === 'monitor' ? monitorInterval : undefined
        });
    };

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-4xl h-[85vh] overflow-hidden flex flex-col">
                <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
                    <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Create New Agent</h2>
                </div>

                <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6">
                    <div className="grid grid-cols-2 gap-6">
                        {/* Left column - Basic info */}
                        <div className="space-y-4">
                            {/* Name */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Name *
                                </label>
                                <input
                                    type="text"
                                    value={name}
                                    onChange={(e) => setName(e.target.value)}
                                    required
                                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                                    placeholder="e.g., Daily News Summarizer"
                                />
                            </div>

                            {/* Description */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Description
                                </label>
                                <input
                                    type="text"
                                    value={description}
                                    onChange={(e) => setDescription(e.target.value)}
                                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                                    placeholder="Brief description of what this agent does"
                                />
                            </div>

                            {/* Lifecycle */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Lifecycle Type *
                                </label>
                                <select
                                    value={lifecycle}
                                    onChange={(e) => setLifecycle(e.target.value as AgentLifecycle)}
                                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                                >
                                    <option value="one_shot">One-Shot (run once)</option>
                                    <option value="scheduled">Scheduled (run on schedule)</option>
                                    <option value="monitor">Monitor (watch for conditions)</option>
                                </select>
                            </div>

                            {/* Monitor Interval */}
                            {lifecycle === 'monitor' && (
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                        Check Interval (minutes)
                                    </label>
                                    <input
                                        type="number"
                                        min={1}
                                        value={monitorInterval}
                                        onChange={(e) => setMonitorInterval(parseInt(e.target.value) || 60)}
                                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                                    />
                                </div>
                            )}

                            {/* Tools */}
                            <ToolSelector
                                availableTools={availableTools}
                                selectedTools={selectedTools}
                                setSelectedTools={setSelectedTools}
                            />
                        </div>

                        {/* Right column - Instructions */}
                        <div className="flex flex-col">
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                Instructions *
                            </label>
                            <textarea
                                value={instructions}
                                onChange={(e) => setInstructions(e.target.value)}
                                required
                                className="flex-1 min-h-[300px] w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white resize-none font-mono text-sm"
                                placeholder="Describe what this agent should do. Be specific about:&#10;&#10;- The task to accomplish&#10;- Data sources to use&#10;- Output format expected&#10;- Any constraints or requirements"
                            />
                        </div>
                    </div>
                </form>

                <div className="p-4 border-t border-gray-200 dark:border-gray-700 flex justify-end gap-3 flex-shrink-0">
                    <button
                        type="button"
                        onClick={onClose}
                        className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition-colors"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleSubmit}
                        disabled={!name || !instructions}
                        className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white rounded-md transition-colors"
                    >
                        Create Agent
                    </button>
                </div>
            </div>
        </div>
    );
}

// Edit Agent Modal Component
function EditAgentModal({
    agent,
    availableTools,
    onClose,
    onUpdate
}: {
    agent: AgentDetail;
    availableTools: ToolInfo[];
    onClose: () => void;
    onUpdate: (data: UpdateAgentRequest) => void;
}) {
    const [name, setName] = useState(agent.name);
    const [description, setDescription] = useState(agent.description || '');
    const [instructions, setInstructions] = useState(agent.instructions);
    const [selectedTools, setSelectedTools] = useState<Set<string>>(new Set(agent.tools));
    const [monitorInterval, setMonitorInterval] = useState(agent.monitor_interval_minutes || 60);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        onUpdate({
            name,
            description: description || undefined,
            instructions,
            tools: Array.from(selectedTools),
            monitor_interval_minutes: agent.lifecycle === 'monitor' ? monitorInterval : undefined
        });
    };

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-4xl h-[85vh] overflow-hidden flex flex-col">
                <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
                    <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Edit Agent</h2>
                </div>

                <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6">
                    <div className="grid grid-cols-2 gap-6">
                        {/* Left column - Basic info */}
                        <div className="space-y-4">
                            {/* Name */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Name *
                                </label>
                                <input
                                    type="text"
                                    value={name}
                                    onChange={(e) => setName(e.target.value)}
                                    required
                                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                                />
                            </div>

                            {/* Description */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Description
                                </label>
                                <input
                                    type="text"
                                    value={description}
                                    onChange={(e) => setDescription(e.target.value)}
                                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                                />
                            </div>

                            {/* Lifecycle (read-only) */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Lifecycle Type
                                </label>
                                <input
                                    type="text"
                                    value={agent.lifecycle === 'one_shot' ? 'One-Shot' : agent.lifecycle === 'scheduled' ? 'Scheduled' : 'Monitor'}
                                    disabled
                                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-gray-100 dark:bg-gray-600 text-gray-500 dark:text-gray-400"
                                />
                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Lifecycle type cannot be changed</p>
                            </div>

                            {/* Monitor Interval */}
                            {agent.lifecycle === 'monitor' && (
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                        Check Interval (minutes)
                                    </label>
                                    <input
                                        type="number"
                                        min={1}
                                        value={monitorInterval}
                                        onChange={(e) => setMonitorInterval(parseInt(e.target.value) || 60)}
                                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                                    />
                                </div>
                            )}

                            {/* Tools */}
                            <ToolSelector
                                availableTools={availableTools}
                                selectedTools={selectedTools}
                                setSelectedTools={setSelectedTools}
                            />
                        </div>

                        {/* Right column - Instructions */}
                        <div className="flex flex-col">
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                Instructions *
                            </label>
                            <textarea
                                value={instructions}
                                onChange={(e) => setInstructions(e.target.value)}
                                required
                                className="flex-1 min-h-[300px] w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white resize-none font-mono text-sm"
                            />
                        </div>
                    </div>
                </form>

                <div className="p-4 border-t border-gray-200 dark:border-gray-700 flex justify-end gap-3 flex-shrink-0">
                    <button
                        type="button"
                        onClick={onClose}
                        className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition-colors"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleSubmit}
                        disabled={!name || !instructions}
                        className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white rounded-md transition-colors"
                    >
                        Save Changes
                    </button>
                </div>
            </div>
        </div>
    );
}

// Run Card Component with expandable events
function RunCard({
    run,
    formatRelativeTime
}: {
    run: AgentRun;
    formatRelativeTime: (dateStr: string | null) => string;
}) {
    const [isExpanded, setIsExpanded] = useState(false);
    const [events, setEvents] = useState<AgentRunEvent[]>([]);
    const [isLoadingEvents, setIsLoadingEvents] = useState(false);
    const eventsContainerRef = useRef<HTMLDivElement>(null);

    const loadEvents = async (scrollToBottom = false) => {
        setIsLoadingEvents(true);
        try {
            const runEvents = await agentApi.getRunEvents(run.run_id);
            setEvents(runEvents);
            // Scroll to bottom after state updates
            if (scrollToBottom) {
                setTimeout(() => {
                    if (eventsContainerRef.current) {
                        eventsContainerRef.current.scrollTop = eventsContainerRef.current.scrollHeight;
                    }
                }, 50);
            }
        } catch (err) {
            console.error('Failed to load events:', err);
        } finally {
            setIsLoadingEvents(false);
        }
    };

    const handleToggle = () => {
        if (!isExpanded) {
            loadEvents(true); // Scroll to bottom on initial open
        }
        setIsExpanded(!isExpanded);
    };

    const getEventIcon = (eventType: AgentRunEventType) => {
        switch (eventType) {
            case 'status': return '📋';
            case 'thinking': return '🤔';
            case 'tool_start': return '🔧';
            case 'tool_progress': return '⏳';
            case 'tool_complete': return '✅';
            case 'tool_error': return '❌';
            case 'message': return '💬';
            case 'error': return '🚨';
            case 'warning': return '⚠️';
            default: return '•';
        }
    };

    const getEventColor = (eventType: AgentRunEventType) => {
        switch (eventType) {
            case 'error':
            case 'tool_error':
                return 'text-red-600 dark:text-red-400';
            case 'warning':
                return 'text-yellow-600 dark:text-yellow-400';
            case 'tool_complete':
                return 'text-green-600 dark:text-green-400';
            case 'tool_start':
            case 'tool_progress':
                return 'text-blue-600 dark:text-blue-400';
            default:
                return 'text-gray-600 dark:text-gray-300';
        }
    };

    return (
        <div className="bg-gray-50 dark:bg-gray-700 rounded-lg overflow-hidden">
            {/* Run Header */}
            <div
                className="p-4 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors"
                onClick={handleToggle}
            >
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <span className={`w-2 h-2 rounded-full ${
                            run.status === 'completed' ? 'bg-green-500' :
                            run.status === 'running' ? 'bg-blue-500 animate-pulse' :
                            run.status === 'failed' ? 'bg-red-500' :
                            'bg-gray-500'
                        }`} />
                        <span className="font-medium text-gray-900 dark:text-white capitalize">
                            {run.status}
                        </span>
                        <span className="text-sm text-gray-500 dark:text-gray-400">
                            Run #{run.run_id}
                        </span>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-500 dark:text-gray-400">
                            {formatRelativeTime(run.started_at || run.created_at)}
                        </span>
                        {isExpanded ? (
                            <ChevronUpIcon className="h-5 w-5 text-gray-400" />
                        ) : (
                            <ChevronDownIcon className="h-5 w-5 text-gray-400" />
                        )}
                    </div>
                </div>
                {run.result_summary && (
                    <p className="mt-2 text-sm text-gray-600 dark:text-gray-300 line-clamp-2">
                        {run.result_summary}
                    </p>
                )}
                {run.error && (
                    <p className="mt-2 text-sm text-red-600 dark:text-red-400">
                        Error: {run.error}
                    </p>
                )}
                {run.assets_created > 0 && (
                    <div className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                        Created {run.assets_created} asset{run.assets_created !== 1 ? 's' : ''}
                    </div>
                )}
            </div>

            {/* Events Panel */}
            {isExpanded && (
                <div className="border-t border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 p-4">
                    <div className="flex items-center justify-between mb-3">
                        <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                            Execution Log
                            {isLoadingEvents && events.length > 0 && (
                                <ArrowPathIcon className="inline-block ml-2 h-3 w-3 animate-spin text-gray-400" />
                            )}
                        </h4>
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                loadEvents(true); // Scroll to bottom on manual reload
                            }}
                            disabled={isLoadingEvents}
                            className="text-xs text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 disabled:opacity-50"
                        >
                            Reload
                        </button>
                    </div>
                    {isLoadingEvents && events.length === 0 ? (
                        <div className="text-sm text-gray-500 dark:text-gray-400">Loading events...</div>
                    ) : events.length === 0 ? (
                        <div className="text-sm text-gray-500 dark:text-gray-400">No events recorded</div>
                    ) : (
                        <div ref={eventsContainerRef} className="space-y-2 max-h-64 overflow-y-auto">
                            {events.map(event => (
                                <div
                                    key={event.event_id}
                                    className="flex items-start gap-2 text-sm"
                                >
                                    <span className="flex-shrink-0 mt-0.5">
                                        {getEventIcon(event.event_type)}
                                    </span>
                                    <div className="flex-1 min-w-0">
                                        <span className={getEventColor(event.event_type)}>
                                            {event.message}
                                        </span>
                                        {event.data && (
                                            <details className="mt-1">
                                                <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-600 dark:hover:text-gray-300">
                                                    Details
                                                </summary>
                                                <pre className="mt-1 text-xs bg-gray-100 dark:bg-gray-700 p-2 rounded overflow-x-auto">
                                                    {JSON.stringify(event.data, null, 2)}
                                                </pre>
                                            </details>
                                        )}
                                    </div>
                                    <span className="flex-shrink-0 text-xs text-gray-400">
                                        {new Date(event.created_at).toLocaleTimeString()}
                                    </span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
