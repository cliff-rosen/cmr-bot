/**
 * Conversation API client
 *
 * Handles CRUD operations for conversations and message retrieval.
 */

import settings from '../../config/settings';

function getAuthHeader(): Record<string, string> {
    const token = localStorage.getItem('authToken');
    return token ? { Authorization: `Bearer ${token}` } : {};
}

export interface Message {
    message_id: number;
    conversation_id: number;
    role: 'user' | 'assistant';
    content: string;
    tool_calls?: any[];
    suggested_values?: any[];
    suggested_actions?: any[];
    custom_payload?: any;
    created_at: string;
}

export interface Conversation {
    conversation_id: number;
    user_id: number;
    title: string | null;
    is_archived: boolean;
    created_at: string;
    updated_at: string;
    message_count?: number;
}

export interface ConversationWithMessages extends Conversation {
    messages: Message[];
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

export const conversationApi = {
    /**
     * List user's conversations
     */
    async list(limit = 20, offset = 0, includeArchived = false): Promise<Conversation[]> {
        const params = new URLSearchParams({
            limit: limit.toString(),
            offset: offset.toString(),
            include_archived: includeArchived.toString(),
        });

        const response = await fetchWithAuth(`${API_BASE}/api/conversations?${params}`);
        return response.json();
    },

    /**
     * Create a new conversation
     */
    async create(title?: string): Promise<Conversation> {
        const response = await fetchWithAuth(`${API_BASE}/api/conversations`, {
            method: 'POST',
            body: JSON.stringify({ title }),
        });
        return response.json();
    },

    /**
     * Get a specific conversation with messages
     */
    async get(conversationId: number): Promise<ConversationWithMessages> {
        const response = await fetchWithAuth(`${API_BASE}/api/conversations/${conversationId}`);
        return response.json();
    },

    /**
     * Update a conversation (title, archive status)
     */
    async update(
        conversationId: number,
        updates: { title?: string; is_archived?: boolean }
    ): Promise<Conversation> {
        const response = await fetchWithAuth(`${API_BASE}/api/conversations/${conversationId}`, {
            method: 'PUT',
            body: JSON.stringify(updates),
        });
        return response.json();
    },

    /**
     * Delete a conversation
     */
    async delete(conversationId: number): Promise<void> {
        await fetchWithAuth(`${API_BASE}/api/conversations/${conversationId}`, {
            method: 'DELETE',
        });
    },

    /**
     * Get messages for a conversation
     */
    async getMessages(conversationId: number, limit = 100, offset = 0): Promise<Message[]> {
        const params = new URLSearchParams({
            limit: limit.toString(),
            offset: offset.toString(),
        });

        const response = await fetchWithAuth(
            `${API_BASE}/api/conversations/${conversationId}/messages?${params}`
        );
        return response.json();
    },
};
