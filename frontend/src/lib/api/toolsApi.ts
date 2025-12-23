/**
 * Tools API client
 *
 * Endpoints for testing backend services directly.
 */

import { api } from './index';

// ============================================================================
// Tool Registry Types
// ============================================================================

export interface ToolInfo {
    name: string;
    description: string;
    category: string;
    input_schema: {
        type: string;
        properties?: Record<string, {
            type: string;
            description?: string;
            enum?: string[];
            items?: { type: string };
            default?: any;
        }>;
        required?: string[];
    };
    streaming: boolean;
}

export interface ToolListResponse {
    tools: ToolInfo[];
    categories: string[];
}

// ============================================================================
// PubMed Search
// ============================================================================

export interface PubMedSearchRequest {
    query: string;
    max_results?: number;
    sort_by?: 'relevance' | 'date';
    start_date?: string;
    end_date?: string;
}

export interface PubMedArticle {
    pmid: string | null;
    title: string;
    authors: string[];
    journal: string | null;
    publication_date: string | null;
    abstract: string | null;
    url: string | null;
}

export interface PubMedSearchResponse {
    success: boolean;
    query: string;
    total_results: number;
    returned: number;
    articles: PubMedArticle[];
    error?: string;
}

// ============================================================================
// Gmail Search
// ============================================================================

export interface GmailSearchRequest {
    query: string;
    max_results?: number;
}

export interface GmailMessage {
    id: string;
    thread_id: string;
    subject: string;
    sender: string;
    date: string;
    snippet: string;
    labels: string[];
}

export interface GmailSearchResponse {
    success: boolean;
    query: string;
    count: number;
    messages: GmailMessage[];
    error?: string;
}

// ============================================================================
// LLM Testing
// ============================================================================

export interface LLMModelInfo {
    id: string;
    display_name: string;
    provider: string;
    is_configured: boolean;
    is_reasoning: boolean;
    context_window: number;
    notes?: string;
}

export interface LLMModelsResponse {
    models: LLMModelInfo[];
    configured_providers: string[];
}

export interface LLMTestRequest {
    model: string;
    context: string;
    questions: string[];  // All questions sent together
}

export interface LLMTestResponse {
    success: boolean;
    model: string;
    raw_response: string;  // Full response text
    parsed_answers: string[];  // Individual answers extracted
    latency_ms: number;
    input_tokens?: number;
    output_tokens?: number;
    error?: string;
}

export const toolsApi = {
    /**
     * List all available tools with their documentation
     */
    async listTools(category?: string): Promise<ToolListResponse> {
        const params = category ? { category } : {};
        const response = await api.get('/api/tools/list', { params });
        return response.data;
    },

    /**
     * Search PubMed for articles
     */
    async searchPubMed(request: PubMedSearchRequest): Promise<PubMedSearchResponse> {
        const response = await api.post('/api/tools/pubmed/search', request);
        return response.data;
    },

    /**
     * Search Gmail for messages
     */
    async searchGmail(request: GmailSearchRequest): Promise<GmailSearchResponse> {
        const response = await api.post('/api/tools/gmail/search', request);
        return response.data;
    },

    /**
     * List all available LLM models for testing
     */
    async listLLMModels(): Promise<LLMModelsResponse> {
        const response = await api.get('/api/tools/llm-models');
        return response.data;
    },

    /**
     * Test an LLM with a context and questions
     */
    async testLLM(request: LLMTestRequest): Promise<LLMTestResponse> {
        const response = await api.post('/api/tools/test-llm', request);
        return response.data;
    }
};
