/**
 * Asset API client
 *
 * Handles CRUD operations for user assets.
 */

import settings from '../../config/settings';

function getAuthHeader(): Record<string, string> {
    const token = localStorage.getItem('authToken');
    return token ? { Authorization: `Bearer ${token}` } : {};
}

export type AssetType = 'file' | 'document' | 'data' | 'code' | 'link';

export interface Asset {
    asset_id: number;
    user_id: number;
    name: string;
    asset_type: AssetType;
    mime_type: string | null;
    content: string | null;
    external_url: string | null;
    description: string | null;
    tags: string[];
    is_in_context: boolean;
    context_summary: string | null;
    source_conversation_id: number | null;
    created_at: string;
    updated_at: string;
}

export interface AssetCreate {
    name: string;
    asset_type: AssetType;
    content?: string;
    external_url?: string;
    mime_type?: string;
    description?: string;
    tags?: string[];
    context_summary?: string;
    source_conversation_id?: number;
}

export interface AssetUpdate {
    name?: string;
    content?: string;
    description?: string;
    tags?: string[];
    context_summary?: string;
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

export const assetApi = {
    /**
     * List user's assets
     */
    async list(
        assetType?: AssetType,
        inContextOnly = false,
        limit = 100,
        offset = 0
    ): Promise<Asset[]> {
        const params = new URLSearchParams({
            in_context_only: inContextOnly.toString(),
            limit: limit.toString(),
            offset: offset.toString(),
        });

        if (assetType) params.set('asset_type', assetType);

        const response = await fetchWithAuth(`${API_BASE}/api/assets?${params}`);
        return response.json();
    },

    /**
     * Create a new asset
     */
    async create(asset: AssetCreate): Promise<Asset> {
        const response = await fetchWithAuth(`${API_BASE}/api/assets`, {
            method: 'POST',
            body: JSON.stringify(asset),
        });
        return response.json();
    },

    /**
     * Get a specific asset
     */
    async get(assetId: number): Promise<Asset> {
        const response = await fetchWithAuth(`${API_BASE}/api/assets/${assetId}`);
        return response.json();
    },

    /**
     * Update an asset
     */
    async update(assetId: number, updates: AssetUpdate): Promise<Asset> {
        const response = await fetchWithAuth(`${API_BASE}/api/assets/${assetId}`, {
            method: 'PUT',
            body: JSON.stringify(updates),
        });
        return response.json();
    },

    /**
     * Delete an asset
     */
    async delete(assetId: number): Promise<void> {
        await fetchWithAuth(`${API_BASE}/api/assets/${assetId}`, {
            method: 'DELETE',
        });
    },

    /**
     * Toggle asset in-context status
     */
    async toggleContext(assetId: number): Promise<{ asset_id: number; is_in_context: boolean }> {
        const response = await fetchWithAuth(`${API_BASE}/api/assets/${assetId}/context`, {
            method: 'POST',
        });
        return response.json();
    },

    /**
     * Clear all assets from context
     */
    async clearContext(): Promise<{ status: string; count: number }> {
        const response = await fetchWithAuth(`${API_BASE}/api/assets/context/clear`, {
            method: 'DELETE',
        });
        return response.json();
    },
};
