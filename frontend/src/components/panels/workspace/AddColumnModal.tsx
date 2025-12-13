/**
 * AddColumnModal - Configure a new computed column for a table
 *
 * Allows user to specify column name, type, and the prompt to run on each row.
 */

import { useState } from 'react';
import { XMarkIcon, SparklesIcon, DocumentTextIcon } from '@heroicons/react/24/solid';
import { TableColumn } from '../../../types/chat';

interface AddColumnModalProps {
    existingColumns: TableColumn[];
    sampleRow: Record<string, any>;
    onSubmit: (config: ColumnConfig) => void;
    onClose: () => void;
}

export interface ColumnConfig {
    name: string;
    key: string;
    type: 'text' | 'boolean' | 'number';
    prompt: string;
}

export default function AddColumnModal({
    existingColumns,
    sampleRow,
    onSubmit,
    onClose
}: AddColumnModalProps) {
    const [name, setName] = useState('');
    const [type, setType] = useState<'text' | 'boolean' | 'number'>('text');
    const [prompt, setPrompt] = useState('');

    // Get available fields from the sample row
    const availableFields = Object.keys(sampleRow).filter(key => {
        const value = sampleRow[key];
        return value !== null && value !== undefined && typeof value !== 'object';
    });

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!name.trim() || !prompt.trim()) return;

        // Generate a key from the name
        const key = name.toLowerCase().replace(/[^a-z0-9]+/g, '_');

        onSubmit({
            name: name.trim(),
            key,
            type,
            prompt: prompt.trim()
        });
    };

    const insertField = (field: string) => {
        setPrompt(prev => prev + `{${field}}`);
    };

    // Build article template from available fields
    const insertArticleTemplate = () => {
        const parts: string[] = [];

        if (sampleRow.title !== undefined) parts.push(`Title: {title}`);
        if (sampleRow.authors_display !== undefined) parts.push(`Authors: {authors_display}`);
        if (sampleRow.journal !== undefined) parts.push(`Journal: {journal}`);
        if (sampleRow.publication_date !== undefined) parts.push(`Date: {publication_date}`);
        if (sampleRow.abstract !== undefined) parts.push(`Abstract: {abstract}`);

        const template = parts.join('\n');
        setPrompt(prev => prev + template);
    };

    // Type-specific prompt suggestions
    const getPromptHint = () => {
        switch (type) {
            case 'boolean':
                return 'Answer with only "Yes" or "No".';
            case 'number':
                return 'Answer with only a number.';
            default:
                return 'Provide a brief response.';
        }
    };

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-4xl h-[80vh] flex flex-col">
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
                    <div className="flex items-center gap-2">
                        <SparklesIcon className="h-5 w-5 text-teal-500" />
                        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                            Add Computed Column
                        </h2>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                    >
                        <XMarkIcon className="h-5 w-5" />
                    </button>
                </div>

                {/* Scrollable content */}
                <div className="flex-1 overflow-y-auto">
                    {/* Form */}
                    <form onSubmit={handleSubmit} className="p-6 space-y-6 h-full flex flex-col">
                        {/* Column Name */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                            Column Name
                        </label>
                        <input
                            type="text"
                            value={name}
                            onChange={e => setName(e.target.value)}
                            placeholder="e.g., Relevant, Summary, Score"
                            className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                            autoFocus
                        />
                    </div>

                    {/* Column Type */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                            Column Type
                        </label>
                        <div className="flex gap-4">
                            {(['text', 'boolean', 'number'] as const).map(t => (
                                <label key={t} className="flex items-center gap-2 cursor-pointer">
                                    <input
                                        type="radio"
                                        name="columnType"
                                        value={t}
                                        checked={type === t}
                                        onChange={() => setType(t)}
                                        className="text-teal-500 focus:ring-teal-500"
                                    />
                                    <span className="text-sm text-gray-700 dark:text-gray-300 capitalize">
                                        {t === 'boolean' ? 'Yes/No' : t}
                                    </span>
                                </label>
                            ))}
                        </div>
                    </div>

                    {/* Available Fields */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                            Insert Fields
                        </label>
                        <div className="flex flex-wrap gap-2 mb-3">
                            {/* Article template button */}
                            <button
                                type="button"
                                onClick={insertArticleTemplate}
                                className="px-3 py-1.5 text-xs bg-blue-100 dark:bg-blue-900/50 hover:bg-blue-200 dark:hover:bg-blue-900 text-blue-700 dark:text-blue-300 rounded-lg border border-blue-300 dark:border-blue-700 transition-colors flex items-center gap-1.5 font-medium"
                            >
                                <DocumentTextIcon className="h-3.5 w-3.5" />
                                Insert Article
                            </button>
                        </div>
                        <div className="flex flex-wrap gap-2">
                            {availableFields.map(field => (
                                <button
                                    key={field}
                                    type="button"
                                    onClick={() => insertField(field)}
                                    className="px-2 py-1 text-xs bg-gray-100 dark:bg-gray-800 hover:bg-teal-100 dark:hover:bg-teal-900/50 text-gray-700 dark:text-gray-300 rounded border border-gray-300 dark:border-gray-600 transition-colors"
                                >
                                    {`{${field}}`}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Prompt */}
                    <div className="flex-1 flex flex-col min-h-0">
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                            Prompt (applied to each row)
                        </label>
                        <textarea
                            value={prompt}
                            onChange={e => setPrompt(e.target.value)}
                            placeholder={`For example:\n\nBased on the article below, determine if it is relevant to asbestos litigation.\n\n[Click "Insert Article" above to add the article template]\n\nAnswer with only "Yes" or "No".`}
                            className="flex-1 min-h-[180px] w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-teal-500 focus:border-transparent font-mono text-sm resize-none"
                        />
                        <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                            Use {'{field_name}'} to reference row data. {getPromptHint()}
                        </p>
                    </div>

                        {/* Actions */}
                        <div className="flex justify-end gap-3 pt-4 border-t border-gray-200 dark:border-gray-700 mt-auto">
                            <button
                                type="button"
                                onClick={onClose}
                                className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                type="submit"
                                disabled={!name.trim() || !prompt.trim()}
                                className="px-4 py-2 bg-teal-500 hover:bg-teal-600 disabled:bg-gray-300 dark:disabled:bg-gray-700 text-white rounded-lg transition-colors flex items-center gap-2"
                            >
                                <SparklesIcon className="h-4 w-4" />
                                Compute Column
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    );
}
