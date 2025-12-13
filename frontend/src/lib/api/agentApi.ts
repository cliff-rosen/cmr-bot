/**
 * Autonomous Agents API client
 *
 * Handles CRUD operations and run management for autonomous agents.
 */

import { api } from './index';

export type AgentLifecycle = 'one_shot' | 'scheduled' | 'monitor';
export type AgentStatus = 'active' | 'paused' | 'completed' | 'failed';
export type AgentRunStatus = 'pending' | 'running' | 'sleeping' | 'completed' | 'failed';
export type AgentRunEventType = 'status' | 'thinking' | 'tool_start' | 'tool_progress' | 'tool_complete' | 'tool_error' | 'message' | 'error' | 'warning';

export interface Agent {
    agent_id: number;
    name: string;
    description: string | null;
    lifecycle: AgentLifecycle;
    instructions: string;
    tools: string[];
    schedule: string | null;
    monitor_interval_minutes: number | null;
    status: AgentStatus;
    total_runs: number;
    total_assets_created: number;
    last_run_at: string | null;
    next_run_at: string | null;
    created_at: string;
}

export interface AgentRun {
    run_id: number;
    agent_id: number;
    status: AgentRunStatus;
    started_at: string | null;
    completed_at: string | null;
    result_summary: string | null;
    error: string | null;
    assets_created: number;
    created_at: string;
}

export interface AgentDetail extends Agent {
    recent_runs: AgentRun[];
}

export interface AgentRunEvent {
    event_id: number;
    run_id: number;
    event_type: AgentRunEventType;
    message: string;
    data: Record<string, any> | null;
    created_at: string;
}

export interface CreateAgentRequest {
    name: string;
    instructions: string;
    lifecycle: AgentLifecycle;
    description?: string;
    tools?: string[];
    schedule?: string;
    monitor_interval_minutes?: number;
}

export interface AgentAsset {
    asset_id: number;
    name: string;
    asset_type: string;
    description: string | null;
    created_at: string;
    run_id: number | null;
}

export interface UpdateAgentRequest {
    name?: string;
    description?: string;
    instructions?: string;
    tools?: string[];
    schedule?: string;
    monitor_interval_minutes?: number;
}

export const agentApi = {
    /**
     * List all agents
     */
    async list(includeCompleted = true): Promise<Agent[]> {
        const params = new URLSearchParams({
            include_completed: includeCompleted.toString()
        });
        const response = await api.get(`/api/agents?${params}`);
        return response.data;
    },

    /**
     * Create a new agent
     */
    async create(agent: CreateAgentRequest): Promise<Agent> {
        const response = await api.post('/api/agents/', agent);
        return response.data;
    },

    /**
     * Get agent details with recent runs
     */
    async get(agentId: number): Promise<AgentDetail> {
        const response = await api.get(`/api/agents/${agentId}`);
        return response.data;
    },

    /**
     * Update an agent
     */
    async update(agentId: number, updates: UpdateAgentRequest): Promise<Agent> {
        const response = await api.patch(`/api/agents/${agentId}`, updates);
        return response.data;
    },

    /**
     * Delete an agent
     */
    async delete(agentId: number): Promise<void> {
        await api.delete(`/api/agents/${agentId}`);
    },

    /**
     * Pause an agent
     */
    async pause(agentId: number): Promise<Agent> {
        const response = await api.post(`/api/agents/${agentId}/pause`);
        return response.data;
    },

    /**
     * Resume a paused agent
     */
    async resume(agentId: number): Promise<Agent> {
        const response = await api.post(`/api/agents/${agentId}/resume`);
        return response.data;
    },

    /**
     * Trigger a manual run
     */
    async triggerRun(agentId: number): Promise<AgentRun> {
        const response = await api.post(`/api/agents/${agentId}/run`);
        return response.data;
    },

    /**
     * Get runs for an agent
     */
    async getRuns(agentId: number, limit = 20): Promise<AgentRun[]> {
        const params = new URLSearchParams({ limit: limit.toString() });
        const response = await api.get(`/api/agents/${agentId}/runs?${params}`);
        return response.data;
    },

    /**
     * Get telemetry events for a run
     */
    async getRunEvents(runId: number, limit = 100): Promise<AgentRunEvent[]> {
        const params = new URLSearchParams({ limit: limit.toString() });
        const response = await api.get(`/api/agents/runs/${runId}/events?${params}`);
        return response.data;
    },

    /**
     * Get assets created by an agent
     */
    async getAgentAssets(agentId: number, limit = 20): Promise<AgentAsset[]> {
        const params = new URLSearchParams({ limit: limit.toString() });
        const response = await api.get(`/api/agents/${agentId}/assets?${params}`);
        return response.data;
    }
};
