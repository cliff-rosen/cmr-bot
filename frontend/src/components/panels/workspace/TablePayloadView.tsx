/**
 * TablePayloadView - Interactive table display for TABILIZER functionality
 *
 * Renders tabular data with sortable columns and filterable rows.
 */

import { useState, useMemo } from 'react';
import { ChevronUpIcon, ChevronDownIcon, FunnelIcon, XMarkIcon } from '@heroicons/react/24/solid';
import { WorkspacePayload, TableColumn } from '../../../types/chat';
import { payloadTypeConfig } from './types';

interface TablePayloadViewProps {
    payload: WorkspacePayload;
    onSaveAsAsset?: (payload: WorkspacePayload) => void;
}

type SortDirection = 'asc' | 'desc' | null;

interface SortState {
    column: string | null;
    direction: SortDirection;
}

interface FilterState {
    [columnKey: string]: string;
}

export default function TablePayloadView({ payload, onSaveAsAsset }: TablePayloadViewProps) {
    const config = payloadTypeConfig[payload.type];
    const tableData = payload.table_data;

    // Sort state
    const [sort, setSort] = useState<SortState>({ column: null, direction: null });

    // Filter state
    const [filters, setFilters] = useState<FilterState>({});
    const [showFilters, setShowFilters] = useState(false);

    if (!tableData) {
        return (
            <div className="p-4 text-gray-500 dark:text-gray-400">
                No table data available
            </div>
        );
    }

    const { columns, rows } = tableData;

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
        <div className="flex flex-col h-full">
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
                    {onSaveAsAsset && (
                        <button
                            onClick={() => onSaveAsAsset(payload)}
                            className="px-3 py-1.5 text-sm bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
                        >
                            Save as Asset
                        </button>
                    )}
                </div>
            </div>

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
        </div>
    );
}
