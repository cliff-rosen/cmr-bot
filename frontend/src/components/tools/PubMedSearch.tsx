import { useState } from 'react';
import { toolsApi, PubMedArticle, PubMedSearchResponse } from '../../lib/api/toolsApi';

export default function PubMedSearch() {
    const [query, setQuery] = useState('');
    const [maxResults, setMaxResults] = useState(10);
    const [sortBy, setSortBy] = useState<'relevance' | 'date'>('relevance');
    const [isLoading, setIsLoading] = useState(false);
    const [result, setResult] = useState<PubMedSearchResponse | null>(null);
    const [error, setError] = useState<string | null>(null);

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!query.trim()) return;

        setIsLoading(true);
        setError(null);
        setResult(null);

        try {
            const response = await toolsApi.searchPubMed({
                query: query.trim(),
                max_results: maxResults,
                sort_by: sortBy
            });
            setResult(response);
            if (!response.success && response.error) {
                setError(response.error);
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Search failed');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
            <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                    PubMed Search
                </h2>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                    Test the PubMed service directly
                </p>
            </div>

            <div className="p-6">
                <form onSubmit={handleSearch} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                            Search Query
                        </label>
                        <input
                            type="text"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            placeholder="e.g., cancer immunotherapy, BRCA1 mutations"
                            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                        />
                    </div>

                    <div className="flex gap-4">
                        <div className="flex-1">
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                Max Results
                            </label>
                            <select
                                value={maxResults}
                                onChange={(e) => setMaxResults(Number(e.target.value))}
                                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                            >
                                <option value={5}>5</option>
                                <option value={10}>10</option>
                                <option value={20}>20</option>
                                <option value={50}>50</option>
                            </select>
                        </div>

                        <div className="flex-1">
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                Sort By
                            </label>
                            <select
                                value={sortBy}
                                onChange={(e) => setSortBy(e.target.value as 'relevance' | 'date')}
                                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                            >
                                <option value="relevance">Relevance</option>
                                <option value="date">Date</option>
                            </select>
                        </div>
                    </div>

                    <div className="flex justify-end">
                        <button
                            type="submit"
                            disabled={isLoading || !query.trim()}
                            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
                        >
                            {isLoading ? 'Searching...' : 'Search'}
                        </button>
                    </div>
                </form>

                {error && (
                    <div className="mt-4 bg-red-50 dark:bg-red-900/50 border border-red-200 dark:border-red-700 rounded-lg p-4">
                        <p className="text-red-800 dark:text-red-200">{error}</p>
                    </div>
                )}

                {result && result.success && (
                    <div className="mt-6">
                        <div className="mb-4 text-sm text-gray-600 dark:text-gray-400">
                            Found <span className="font-semibold">{result.total_results.toLocaleString()}</span> total results,
                            showing <span className="font-semibold">{result.returned}</span>
                        </div>

                        <div className="space-y-4">
                            {result.articles.map((article, index) => (
                                <ArticleCard key={article.pmid || index} article={article} index={index + 1} />
                            ))}
                        </div>
                    </div>
                )}

                {result && !result.success && !error && (
                    <div className="mt-4 text-gray-500 dark:text-gray-400">
                        No results found for "{result.query}"
                    </div>
                )}
            </div>
        </div>
    );
}

function ArticleCard({ article, index }: { article: PubMedArticle; index: number }) {
    const [showAbstract, setShowAbstract] = useState(false);

    const authorStr = article.authors.length > 3
        ? `${article.authors.slice(0, 3).join(', ')} et al.`
        : article.authors.join(', ');

    return (
        <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
            <div className="flex items-start gap-3">
                <span className="text-sm font-medium text-gray-400 dark:text-gray-500">
                    {index}.
                </span>
                <div className="flex-1 min-w-0">
                    <h3 className="text-base font-medium text-gray-900 dark:text-white">
                        {article.url ? (
                            <a
                                href={article.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="hover:text-blue-600 dark:hover:text-blue-400"
                            >
                                {article.title}
                            </a>
                        ) : (
                            article.title
                        )}
                    </h3>

                    {authorStr && (
                        <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                            {authorStr}
                        </p>
                    )}

                    <div className="flex items-center gap-2 mt-1 text-sm text-gray-500 dark:text-gray-500">
                        {article.journal && <span>{article.journal}</span>}
                        {article.journal && article.publication_date && <span>•</span>}
                        {article.publication_date && <span>{article.publication_date}</span>}
                        {article.pmid && (
                            <>
                                <span>•</span>
                                <span className="font-mono text-xs">PMID: {article.pmid}</span>
                            </>
                        )}
                    </div>

                    {article.abstract && (
                        <div className="mt-2">
                            <button
                                onClick={() => setShowAbstract(!showAbstract)}
                                className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
                            >
                                {showAbstract ? 'Hide abstract' : 'Show abstract'}
                            </button>
                            {showAbstract && (
                                <p className="mt-2 text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
                                    {article.abstract}
                                </p>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
