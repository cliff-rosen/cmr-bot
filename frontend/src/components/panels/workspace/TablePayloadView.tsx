/**
 * TablePayloadView - Interactive table display for TABILIZER functionality
 *
 * Renders tabular data with sortable columns and filterable rows.
 * Supports adding AI-computed columns via the Add Column feature.
 */

import { useState, useMemo, useCallback } from 'react';
import { ChevronUpIcon, ChevronDownIcon, FunnelIcon, XMarkIcon, PlusIcon, SparklesIcon } from '@heroicons/react/24/solid';
import { WorkspacePayload, TableColumn } from '../../../types/chat';
import { payloadTypeConfig } from './types';
import AddColumnModal, { ColumnConfig } from './AddColumnModal';
import settings from '../../../config/settings';

interface TablePayloadViewProps {
    payload: WorkspacePayload;
    onSaveAsAsset?: (payload: WorkspacePayload) => void;
    isSaving?: boolean;
}

type SortDirection = 'asc' | 'desc' | null;

interface SortState {
    column: string | null;
    direction: SortDirection;
}

interface FilterState {
    [columnKey: string]: string;
}

interface ComputeProgress {
    completed: number;
    total: number;
    status: string;
}

export default function TablePayloadView({ payload, onSaveAsAsset, isSaving = false }: TablePayloadViewProps) {
    const config = payloadTypeConfig[payload.type];
    const initialTableData = payload.table_data;

    // Mutable table state (columns and rows can be augmented)
    const [columns, setColumns] = useState<TableColumn[]>(initialTableData?.columns || []);
    const [rows, setRows] = useState<Record<string, any>[]>(initialTableData?.rows || []);

    // Sort state
    const [sort, setSort] = useState<SortState>({ column: null, direction: null });

    // Filter state
    const [filters, setFilters] = useState<FilterState>({});
    const [showFilters, setShowFilters] = useState(false);

    // Add Column modal state
    const [showAddColumn, setShowAddColumn] = useState(false);
    const [isComputing, setIsComputing] = useState(false);
    const [computeProgress, setComputeProgress] = useState<ComputeProgress | null>(null);
    const [computingColumnKey, setComputingColumnKey] = useState<string | null>(null);

    // Handle saving with current state (including any computed columns)
    const handleSaveAsAsset = useCallback(() => {
        if (!onSaveAsAsset) return;

        // Build updated payload with current columns and rows
        const updatedPayload: WorkspacePayload = {
            ...payload,
            table_data: {
                ...payload.table_data!,
                columns,
                rows
            }
        };
        onSaveAsAsset(updatedPayload);
    }, [payload, columns, rows, onSaveAsAsset]);

    // Handle adding a computed column
    const handleAddColumn = useCallback(async (config: ColumnConfig) => {
        setShowAddColumn(false);
        setIsComputing(true);
        setComputingColumnKey(config.key);
        setComputeProgress({ completed: 0, total: rows.length, status: 'Starting...' });

        // Add the column immediately so it appears right away
        const newColumn: TableColumn = {
            key: config.key,
            label: config.name,
            type: config.type,
            sortable: true,
            filterable: true,
            computed: true
        };
        setColumns(prev => [...prev, newColumn]);

        try {
            const token = localStorage.getItem('authToken');
            const response = await fetch(`${settings.apiUrl}/api/table/compute-column`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
                },
                body: JSON.stringify({
                    rows: rows,
                    prompt: config.prompt,
                    column_key: config.key,
                    column_type: config.type
                })
            });

            if (!response.ok) {
                throw new Error('Failed to compute column');
            }

            // Handle SSE streaming response
            const reader = response.body?.getReader();
            if (!reader) throw new Error('No response body');

            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            if (data.type === 'progress') {
                                setComputeProgress({
                                    completed: data.completed,
                                    total: data.total,
                                    status: data.message || `Processing ${data.completed}/${data.total}...`
                                });
                            } else if (data.type === 'row_result') {
                                // Update the specific row immediately as results come in
                                setRows(prev => prev.map((row, idx) =>
                                    idx === data.row_index
                                        ? { ...row, [config.key]: data.value }
                                        : row
                                ));
                            } else if (data.type === 'error') {
                                throw new Error(data.message);
                            }
                        } catch (e) {
                            // Skip invalid JSON
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Error computing column:', error);
            // Remove the column if there was an error
            setColumns(prev => prev.filter(c => c.key !== config.key));
        } finally {
            setIsComputing(false);
            setComputeProgress(null);
            setComputingColumnKey(null);
        }
    }, [rows]);

    if (!initialTableData) {
        return (
            <div className="p-4 text-gray-500 dark:text-gray-400">
                No table data available
            </div>
        );
    }

    // Handle column header click for sorting
    const handleSort = (columnKey: string) => {
        const column = columns.find(c => c.key === columnKey);
        if (!column?.sortable) return;

        setSort(prev => {
            if (prev.column !== columnKey) {
                return { column: columnKey, direction: 'asc' };
            }
            if (prev.direction === 'asc') {
                return { column: columnKey, direction: 'desc' };
            }
            return { column: null, direction: null };
        });
    };

    // Handle filter change
    const handleFilterChange = (columnKey: string, value: string) => {
        setFilters(prev => ({
            ...prev,
            [columnKey]: value
        }));
    };

    // Clear all filters
    const clearFilters = () => {
        setFilters({});
    };

    // Apply filters and sorting
    const processedRows = useMemo(() => {
        let result = [...rows];

        // Apply filters
        Object.entries(filters).forEach(([columnKey, filterValue]) => {
            if (filterValue) {
                result = result.filter(row => {
                    const cellValue = row[columnKey];
                    if (cellValue === null || cellValue === undefined) return false;
                    return String(cellValue).toLowerCase().includes(filterValue.toLowerCase());
                });
            }
        });

        // Apply sorting
        if (sort.column && sort.direction) {
            const column = columns.find(c => c.key === sort.column);
            result.sort((a, b) => {
                const aVal = a[sort.column!];
                const bVal = b[sort.column!];

                // Handle nulls
                if (aVal === null || aVal === undefined) return 1;
                if (bVal === null || bVal === undefined) return -1;

                // Sort based on column type
                let comparison = 0;
                if (column?.type === 'number') {
                    comparison = Number(aVal) - Number(bVal);
                } else if (column?.type === 'date') {
                    comparison = new Date(aVal).getTime() - new Date(bVal).getTime();
                } else {
                    comparison = String(aVal).localeCompare(String(bVal));
                }

                return sort.direction === 'desc' ? -comparison : comparison;
            });
        }

        return result;
    }, [rows, filters, sort, columns]);

    // Render cell content based on column type
    const renderCell = (column: TableColumn, value: any) => {
        if (value === null || value === undefined) {
            // Show loading indicator if this column is currently being computed
            if (computingColumnKey === column.key) {
                return (
                    <span className="inline-flex items-center gap-1 text-teal-500">
                        <span className="animate-pulse">●</span>
                    </span>
                );
            }
            return <span className="text-gray-400">-</span>;
        }

        switch (column.type) {
            case 'boolean':
                return value ? (
                    <span className="text-green-600 dark:text-green-400">Yes</span>
                ) : (
                    <span className="text-red-600 dark:text-red-400">No</span>
                );
            case 'link':
                return (
                    <a
                        href={value}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 dark:text-blue-400 hover:underline"
                    >
                        Link
                    </a>
                );
            case 'date':
                return new Date(value).toLocaleDateString();
            default:
                return String(value);
        }
    };

    const activeFilterCount = Object.values(filters).filter(v => v).length;

    return (
        <div className="flex flex-col h-full relative">
            {/* Header */}
            <div className={`flex items-center justify-between px-4 py-3 ${config.bg} border-b ${config.border}`}>
                <div className="flex items-center gap-2">
                    <config.icon className={`h-5 w-5 ${config.color}`} />
                    <span className="font-medium text-gray-900 dark:text-white">{payload.title}</span>
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                        ({processedRows.length} of {rows.length} rows)
                    </span>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setShowFilters(!showFilters)}
                        className={`p-2 rounded-lg transition-colors ${
                            showFilters || activeFilterCount > 0
                                ? 'bg-teal-100 dark:bg-teal-900/50 text-teal-600 dark:text-teal-400'
                                : 'hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500'
                        }`}
                        title="Toggle filters"
                    >
                        <FunnelIcon className="h-4 w-4" />
                        {activeFilterCount > 0 && (
                            <span className="ml-1 text-xs">{activeFilterCount}</span>
                        )}
                    </button>
                    <button
                        onClick={() => setShowAddColumn(true)}
                        disabled={isComputing || rows.length === 0}
                        className="flex items-center gap-1 px-3 py-1.5 text-sm bg-teal-500 hover:bg-teal-600 disabled:bg-gray-300 dark:disabled:bg-gray-700 text-white rounded-lg transition-colors"
                        title="Add AI-computed column"
                    >
                        <SparklesIcon className="h-4 w-4" />
                        <PlusIcon className="h-3 w-3" />
                        Column
                    </button>
                    {onSaveAsAsset && (
                        <button
                            onClick={handleSaveAsAsset}
                            disabled={isSaving}
                            className="flex items-center gap-1 px-3 py-1.5 text-sm bg-gray-200 dark:bg-gray-600 hover:bg-gray-300 dark:hover:bg-gray-500 text-gray-700 dark:text-gray-100 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {isSaving && (
                                <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                            )}
                            {isSaving ? 'Saving...' : 'Save as Asset'}
                        </button>
                    )}
                </div>
            </div>

            {/* Computing banner */}
            {isComputing && computeProgress && (
                <div className="px-4 py-2 bg-teal-50 dark:bg-teal-900/30 border-b border-teal-200 dark:border-teal-800 flex items-center gap-3">
                    <SparklesIcon className="h-4 w-4 text-teal-500 animate-pulse" />
                    <span className="text-sm text-teal-700 dark:text-teal-300">
                        Computing column values... {computeProgress.completed} of {computeProgress.total} complete
                    </span>
                    <div className="flex-1 max-w-xs">
                        <div className="w-full bg-teal-200 dark:bg-teal-800 rounded-full h-1.5">
                            <div
                                className="bg-teal-500 h-1.5 rounded-full transition-all duration-150"
                                style={{ width: `${(computeProgress.completed / computeProgress.total) * 100}%` }}
                            />
                        </div>
                    </div>
                </div>
            )}

            {/* Filter bar */}
            {showFilters && (
                <div className="px-4 py-2 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
                    <div className="flex items-center gap-4 flex-wrap">
                        {columns.filter(col => col.filterable !== false).map(column => (
                            <div key={column.key} className="flex items-center gap-2">
                                <label className="text-xs text-gray-500 dark:text-gray-400">
                                    {column.label}:
                                </label>
                                {column.type === 'boolean' ? (
                                    <select
                                        value={filters[column.key] || ''}
                                        onChange={e => handleFilterChange(column.key, e.target.value)}
                                        className="text-sm px-2 py-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                                    >
                                        <option value="">All</option>
                                        <option value="true">Yes</option>
                                        <option value="false">No</option>
                                    </select>
                                ) : (
                                    <input
                                        type="text"
                                        value={filters[column.key] || ''}
                                        onChange={e => handleFilterChange(column.key, e.target.value)}
                                        placeholder="Filter..."
                                        className="text-sm px-2 py-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 w-32"
                                    />
                                )}
                            </div>
                        ))}
                        {activeFilterCount > 0 && (
                            <button
                                onClick={clearFilters}
                                className="text-xs text-red-600 dark:text-red-400 hover:underline flex items-center gap-1"
                            >
                                <XMarkIcon className="h-3 w-3" />
                                Clear all
                            </button>
                        )}
                    </div>
                </div>
            )}

            {/* Table */}
            <div className="flex-1 overflow-auto">
                <table className="w-full text-sm">
                    <thead className="bg-gray-100 dark:bg-gray-800 sticky top-0">
                        <tr>
                            {columns.map(column => (
                                <th
                                    key={column.key}
                                    onClick={() => handleSort(column.key)}
                                    className={`px-4 py-2 text-left font-medium text-gray-700 dark:text-gray-300 ${
                                        column.sortable !== false ? 'cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-700' : ''
                                    }`}
                                    style={{ width: column.width }}
                                >
                                    <div className="flex items-center gap-1">
                                        {column.label}
                                        {column.computed && (
                                            <span className="text-xs text-teal-500" title="AI-computed column">*</span>
                                        )}
                                        {column.sortable !== false && sort.column === column.key && (
                                            sort.direction === 'asc' ? (
                                                <ChevronUpIcon className="h-4 w-4 text-teal-500" />
                                            ) : (
                                                <ChevronDownIcon className="h-4 w-4 text-teal-500" />
                                            )
                                        )}
                                    </div>
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                        {processedRows.map((row, rowIndex) => (
                            <tr
                                key={rowIndex}
                                className="hover:bg-gray-50 dark:hover:bg-gray-900/50"
                            >
                                {columns.map(column => (
                                    <td
                                        key={column.key}
                                        className="px-4 py-2 text-gray-900 dark:text-gray-100"
                                    >
                                        {renderCell(column, row[column.key])}
                                    </td>
                                ))}
                            </tr>
                        ))}
                        {processedRows.length === 0 && (
                            <tr>
                                <td
                                    colSpan={columns.length}
                                    className="px-4 py-8 text-center text-gray-500 dark:text-gray-400"
                                >
                                    No matching rows
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            {/* Footer with summary */}
            {payload.content && (
                <div className="px-4 py-2 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
                    <p className="text-sm text-gray-600 dark:text-gray-400">{payload.content}</p>
                </div>
            )}

            {/* Add Column Modal */}
            {showAddColumn && rows.length > 0 && (
                <AddColumnModal
                    existingColumns={columns}
                    sampleRow={rows[0]}
                    onSubmit={handleAddColumn}
                    onClose={() => setShowAddColumn(false)}
                />
            )}
        </div>
    );
}
