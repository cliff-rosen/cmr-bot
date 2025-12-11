/**
 * Memory API client
 *
 * Handles CRUD operations for user memories.
 */

import settings from '../../config/settings';

function getAuthHeader(): Record<string, string> {
    const token = localStorage.getItem('authToken');
    return token ? { Authorization: `Bearer ${token}` } : {};
}

export type MemoryType = 'working' | 'fact' | 'preference' | 'entity' | 'project';

export interface Memory {
    memory_id: number;
    user_id: number;
    memory_type: MemoryType;
    category: string | null;
    content: string;
    source_conversation_id: number | null;
    created_at: string;
    expires_at: string | null;
    is_active: boolean;
    is_pinned: boolean;
    confidence: number;
}

export interface MemoryCreate {
    content: string;
    memory_type: MemoryType;
    category?: string;
    is_pinned?: boolean;
    source_conversation_id?: number;
}

export interface MemoryUpdate {
    content?: string;
    category?: string;
    is_active?: boolean;
    is_pinned?: boolean;
}

const API_BASE = settings.apiUrl;

async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
    const authHeader = getAuthHeader();
    const headers = {
        'Content-Type': 'application/json',
        ...authHeader,
        ...options.headers,
    };

    const response = await fetch(url, { ...options, headers });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Request failed' }));
        throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response;
}

export const memoryApi = {
    /**
     * List user's memories
     */
    async list(
        memoryType?: MemoryType,
        category?: string,
        activeOnly = true,
        limit = 100,
        offset = 0
    ): Promise<Memory[]> {
        const params = new URLSearchParams({
            active_only: activeOnly.toString(),
            limit: limit.toString(),
            offset: offset.toString(),
        });

        if (memoryType) params.set('memory_type', memoryType);
        if (category) params.set('category', category);

        const response = await fetchWithAuth(`${API_BASE}/api/memories?${params}`);
        return response.json();
    },

    /**
     * Create a new memory
     */
    async create(memory: MemoryCreate): Promise<Memory> {
        const response = await fetchWithAuth(`${API_BASE}/api/memories`, {
            method: 'POST',
            body: JSON.stringify(memory),
        });
        return response.json();
    },

    /**
     * Get a specific memory
     */
    async get(memoryId: number): Promise<Memory> {
        const response = await fetchWithAuth(`${API_BASE}/api/memories/${memoryId}`);
        return response.json();
    },

    /**
     * Update a memory
     */
    async update(memoryId: number, updates: MemoryUpdate): Promise<Memory> {
        const response = await fetchWithAuth(`${API_BASE}/api/memories/${memoryId}`, {
            method: 'PUT',
            body: JSON.stringify(updates),
        });
        return response.json();
    },

    /**
     * Delete a memory
     */
    async delete(memoryId: number): Promise<void> {
        await fetchWithAuth(`${API_BASE}/api/memories/${memoryId}`, {
            method: 'DELETE',
        });
    },

    /**
     * Toggle memory active status
     */
    async toggleActive(memoryId: number): Promise<{ memory_id: number; is_active: boolean }> {
        const response = await fetchWithAuth(`${API_BASE}/api/memories/${memoryId}/toggle`, {
            method: 'POST',
        });
        return response.json();
    },

    /**
     * Toggle memory pinned status
     */
    async togglePinned(memoryId: number): Promise<{ memory_id: number; is_pinned: boolean }> {
        const response = await fetchWithAuth(`${API_BASE}/api/memories/${memoryId}/pin`, {
            method: 'POST',
        });
        return response.json();
    },

    /**
     * Clear all working memories
     */
    async clearWorkingMemory(): Promise<{ status: string; count: number }> {
        const response = await fetchWithAuth(`${API_BASE}/api/memories/working/clear`, {
            method: 'DELETE',
        });
        return response.json();
    },
};
