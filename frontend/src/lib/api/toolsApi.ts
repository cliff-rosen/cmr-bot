/**
 * Tools API client
 *
 * Endpoints for testing backend services directly.
 */

import { api } from './index';

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

export const toolsApi = {
    /**
     * Search PubMed for articles
     */
    async searchPubMed(request: PubMedSearchRequest): Promise<PubMedSearchResponse> {
        const response = await api.post('/api/tools/pubmed/search', request);
        return response.data;
    }
};
