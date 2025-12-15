import { useState, useMemo } from 'react';
import {
    XMarkIcon, DocumentIcon, TrashIcon,
    MagnifyingGlassIcon, DocumentTextIcon, CodeBracketIcon,
    LinkIcon, TableCellsIcon, PhotoIcon, PencilIcon,
    CheckIcon, ArrowsPointingOutIcon, ChevronUpIcon, ChevronDownIcon, FunnelIcon
} from '@heroicons/react/24/solid';
import { CheckCircleIcon as CheckCircleOutlineIcon } from '@heroicons/react/24/outline';
import { Asset, AssetType, AssetUpdate } from '../../lib/api';
import { MarkdownRenderer } from '../common/MarkdownRenderer';
import { TableColumn } from '../../types/chat';

interface AssetBrowserModalProps {
    isOpen: boolean;
    assets: Asset[];
    onClose: () => void;
    onToggleContext: (assetId: number) => void;
    onDelete: (assetId: number) => void;
    onUpdateAsset?: (assetId: number, updates: AssetUpdate) => void;
}

// Helper to get asset type icon
const getAssetTypeInfo = (type: AssetType) => {
    switch (type) {
        case 'document':
            return { icon: DocumentTextIcon, color: 'text-blue-500', bg: 'bg-blue-100 dark:bg-blue-900/30', label: 'Document' };
        case 'code':
            return { icon: CodeBracketIcon, color: 'text-green-500', bg: 'bg-green-100 dark:bg-green-900/30', label: 'Code' };
        case 'data':
            return { icon: TableCellsIcon, color: 'text-purple-500', bg: 'bg-purple-100 dark:bg-purple-900/30', label: 'Data' };
        case 'link':
            return { icon: LinkIcon, color: 'text-cyan-500', bg: 'bg-cyan-100 dark:bg-cyan-900/30', label: 'Link' };
        case 'file':
            return { icon: PhotoIcon, color: 'text-orange-500', bg: 'bg-orange-100 dark:bg-orange-900/30', label: 'File' };
        default:
            return { icon: DocumentIcon, color: 'text-gray-500', bg: 'bg-gray-100 dark:bg-gray-900/30', label: type };
    }
};

type FilterType = 'all' | 'in_context' | AssetType;

// Table data structure
interface TableData {
    columns: TableColumn[];
    rows: Record<string, any>[];
    source?: string;
}

// Try to parse asset content as table data
function parseTableData(content: string | undefined): TableData | null {
    if (!content) return null;
    try {
        const parsed = JSON.parse(content);
        if (parsed.columns && Array.isArray(parsed.columns) &&
            parsed.rows && Array.isArray(parsed.rows)) {
            return parsed as TableData;
        }
    } catch {
        // Not valid JSON or not table data
    }
    return null;
}

// Simple table viewer component for asset browser
function AssetTableViewer({ tableData }: { tableData: TableData }) {
    const [sortColumn, setSortColumn] = useState<string | null>(null);
    const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
    const [filters, setFilters] = useState<Record<string, string>>({});
    const [showFilters, setShowFilters] = useState(false);

    const handleSort = (columnKey: string) => {
        if (sortColumn === columnKey) {
            setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
        } else {
            setSortColumn(columnKey);
            setSortDirection('asc');
        }
    };

    const processedRows = useMemo(() => {
        let result = [...tableData.rows];

        // Apply filters
        Object.entries(filters).forEach(([key, value]) => {
            if (value) {
                result = result.filter(row => {
                    const cellValue = row[key];
                    if (cellValue === null || cellValue === undefined) return false;
                    return String(cellValue).toLowerCase().includes(value.toLowerCase());
                });
            }
        });

        // Apply sorting
        if (sortColumn) {
            const column = tableData.columns.find(c => c.key === sortColumn);
            result.sort((a, b) => {
                const aVal = a[sortColumn];
                const bVal = b[sortColumn];
                if (aVal === null || aVal === undefined) return 1;
                if (bVal === null || bVal === undefined) return -1;

                let comparison = 0;
                if (column?.type === 'number') {
                    comparison = Number(aVal) - Number(bVal);
                } else {
                    comparison = String(aVal).localeCompare(String(bVal));
                }
                return sortDirection === 'desc' ? -comparison : comparison;
            });
        }

        return result;
    }, [tableData.rows, tableData.columns, filters, sortColumn, sortDirection]);

    const activeFilterCount = Object.values(filters).filter(v => v).length;

    return (
        <div className="flex flex-col h-full">
            {/* Toolbar */}
            <div className="flex items-center justify-between px-4 py-2 bg-purple-50 dark:bg-purple-900/20 border-b border-purple-200 dark:border-purple-800">
                <span className="text-sm text-purple-700 dark:text-purple-300">
                    {processedRows.length} of {tableData.rows.length} rows
                </span>
                <button
                    onClick={() => setShowFilters(!showFilters)}
                    className={`p-2 rounded-lg transition-colors ${
                        showFilters || activeFilterCount > 0
                            ? 'bg-purple-100 dark:bg-purple-800 text-purple-600 dark:text-purple-300'
                            : 'hover:bg-purple-100 dark:hover:bg-purple-800 text-gray-500'
                    }`}
                >
                    <FunnelIcon className="h-4 w-4" />
                    {activeFilterCount > 0 && <span className="ml-1 text-xs">{activeFilterCount}</span>}
                </button>
            </div>

            {/* Filter bar */}
            {showFilters && (
                <div className="px-4 py-2 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 flex flex-wrap gap-3">
                    {tableData.columns.filter(col => col.filterable !== false).map(col => (
                        <div key={col.key} className="flex items-center gap-2">
                            <label className="text-xs text-gray-500">{col.label}:</label>
                            <input
                                type="text"
                                value={filters[col.key] || ''}
                                onChange={e => setFilters(prev => ({ ...prev, [col.key]: e.target.value }))}
                                placeholder="Filter..."
                                className="text-sm px-2 py-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 w-28"
                            />
                        </div>
                    ))}
                    {activeFilterCount > 0 && (
                        <button
                            onClick={() => setFilters({})}
                            className="text-xs text-red-600 hover:underline"
                        >
                            Clear all
                        </button>
                    )}
                </div>
            )}

            {/* Table */}
            <div className="flex-1 overflow-auto">
                <table className="w-full text-sm">
                    <thead className="bg-gray-100 dark:bg-gray-800 sticky top-0">
                        <tr>
                            {tableData.columns.map(col => (
                                <th
                                    key={col.key}
                                    onClick={() => col.sortable !== false && handleSort(col.key)}
                                    className={`px-4 py-2 text-left font-medium text-gray-700 dark:text-gray-300 ${
                                        col.sortable !== false ? 'cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-700' : ''
                                    }`}
                                >
                                    <div className="flex items-center gap-1">
                                        {col.label}
                                        {sortColumn === col.key && (
                                            sortDirection === 'asc'
                                                ? <ChevronUpIcon className="h-4 w-4 text-purple-500" />
                                                : <ChevronDownIcon className="h-4 w-4 text-purple-500" />
                                        )}
                                    </div>
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                        {processedRows.map((row, idx) => (
                            <tr key={idx} className="hover:bg-gray-50 dark:hover:bg-gray-900/50">
                                {tableData.columns.map(col => (
                                    <td key={col.key} className="px-4 py-2 text-gray-900 dark:text-gray-100">
                                        {col.type === 'link' && row[col.key] ? (
                                            <a
                                                href={row[col.key]}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="text-blue-600 hover:underline"
                                            >
                                                Link
                                            </a>
                                        ) : col.type === 'boolean' ? (
                                            row[col.key] ? <span className="text-green-600">Yes</span> : <span className="text-red-600">No</span>
                                        ) : row[col.key] ?? <span className="text-gray-400">-</span>}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

export default function AssetBrowserModal({
    isOpen,
    assets,
    onClose,
    onToggleContext,
    onDelete,
    onUpdateAsset
}: AssetBrowserModalProps) {
    const [filter, setFilter] = useState<FilterType>('all');
    const [searchQuery, setSearchQuery] = useState('');
    const [confirmDelete, setConfirmDelete] = useState<number | null>(null);
    const [viewingAsset, setViewingAsset] = useState<Asset | null>(null);
    const [isEditing, setIsEditing] = useState(false);
    const [editContent, setEditContent] = useState('');
    const [editName, setEditName] = useState('');
    const [isEditingName, setIsEditingName] = useState(false);

    if (!isOpen) return null;

    // Filter assets
    const filteredAssets = assets
        .filter(a => {
            if (filter === 'all') return true;
            if (filter === 'in_context') return a.is_in_context;
            return a.asset_type === filter;
        })
        .filter(a => {
            if (!searchQuery.trim()) return true;
            return a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                   a.description?.toLowerCase().includes(searchQuery.toLowerCase());
        })
        .sort((a, b) => {
            // Sort by date only - don't re-sort by context to avoid items jumping around
            return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        });

    // Count by type
    const counts: Record<string, number> = {
        all: assets.length,
        in_context: assets.filter(a => a.is_in_context).length,
        document: assets.filter(a => a.asset_type === 'document').length,
        code: assets.filter(a => a.asset_type === 'code').length,
        data: assets.filter(a => a.asset_type === 'data').length,
        link: assets.filter(a => a.asset_type === 'link').length,
        file: assets.filter(a => a.asset_type === 'file').length,
    };

    const handleDelete = (assetId: number) => {
        if (confirmDelete === assetId) {
            onDelete(assetId);
            setConfirmDelete(null);
        } else {
            setConfirmDelete(assetId);
            setTimeout(() => setConfirmDelete(null), 3000);
        }
    };

    const handleViewAsset = (asset: Asset) => {
        setViewingAsset(asset);
        setEditContent(asset.content || '');
        setEditName(asset.name);
        setIsEditing(false);
        setIsEditingName(false);
    };

    const handleCloseViewer = () => {
        setViewingAsset(null);
        setIsEditing(false);
        setIsEditingName(false);
        setEditContent('');
        setEditName('');
    };

    const handleSaveEdit = () => {
        if (viewingAsset && onUpdateAsset && editContent !== viewingAsset.content) {
            onUpdateAsset(viewingAsset.asset_id, { content: editContent });
            setViewingAsset({ ...viewingAsset, content: editContent });
        }
        setIsEditing(false);
    };

    const handleSaveName = () => {
        if (viewingAsset && onUpdateAsset && editName.trim() && editName !== viewingAsset.name) {
            onUpdateAsset(viewingAsset.asset_id, { name: editName.trim() });
            setViewingAsset({ ...viewingAsset, name: editName.trim() });
        }
        setIsEditingName(false);
    };

    const handleNameKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            handleSaveName();
        } else if (e.key === 'Escape') {
            setEditName(viewingAsset?.name || '');
            setIsEditingName(false);
        }
    };

    const filterButtons: { key: FilterType; label: string; icon?: React.ComponentType<{ className?: string }>; color?: string }[] = [
        { key: 'all', label: 'All' },
        { key: 'in_context', label: 'In Context', icon: CheckIcon, color: 'text-orange-500' },
        { key: 'document', label: 'Documents', icon: DocumentTextIcon, color: 'text-blue-500' },
        { key: 'code', label: 'Code', icon: CodeBracketIcon, color: 'text-green-500' },
        { key: 'data', label: 'Data', icon: TableCellsIcon, color: 'text-purple-500' },
        { key: 'link', label: 'Links', icon: LinkIcon, color: 'text-cyan-500' },
        { key: 'file', label: 'Files', icon: PhotoIcon, color: 'text-orange-500' },
    ];

    // Asset viewer/editor modal (nested)
    if (viewingAsset) {
        const typeInfo = getAssetTypeInfo(viewingAsset.asset_type);
        const TypeIcon = typeInfo.icon;
        const isEditable = ['document', 'code', 'data'].includes(viewingAsset.asset_type);

        return (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
                <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl w-[95vw] h-[95vh] max-w-6xl flex flex-col">
                    {/* Header */}
                    <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                            <TypeIcon className={`h-6 w-6 flex-shrink-0 ${typeInfo.color}`} />
                            <div className="flex-1 min-w-0">
                                {isEditingName ? (
                                    <div className="flex items-center gap-2">
                                        <input
                                            type="text"
                                            value={editName}
                                            onChange={(e) => setEditName(e.target.value)}
                                            onKeyDown={handleNameKeyDown}
                                            onBlur={handleSaveName}
                                            autoFocus
                                            className="flex-1 px-2 py-1 text-xl font-semibold bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                                        />
                                    </div>
                                ) : (
                                    <div className="flex items-center gap-2 group">
                                        <h2 className="text-xl font-semibold text-gray-900 dark:text-white truncate">
                                            {viewingAsset.name}
                                        </h2>
                                        {onUpdateAsset && (
                                            <button
                                                onClick={() => setIsEditingName(true)}
                                                className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 opacity-0 group-hover:opacity-100 transition-opacity"
                                                title="Edit name"
                                            >
                                                <PencilIcon className="h-4 w-4" />
                                            </button>
                                        )}
                                    </div>
                                )}
                                {viewingAsset.description && (
                                    <p className="text-sm text-gray-500 truncate">{viewingAsset.description}</p>
                                )}
                            </div>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                            {isEditable && !isEditing && onUpdateAsset && (
                                <button
                                    onClick={() => setIsEditing(true)}
                                    className="flex items-center gap-1 px-3 py-2 text-sm text-gray-600 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
                                >
                                    <PencilIcon className="h-4 w-4" />
                                    Edit Content
                                </button>
                            )}
                            {isEditing && (
                                <>
                                    <button
                                        onClick={handleSaveEdit}
                                        className="flex items-center gap-1 px-3 py-2 text-sm text-green-600 hover:text-green-700 dark:text-green-400 dark:hover:text-green-300 hover:bg-green-50 dark:hover:bg-green-900/20 rounded-lg transition-colors"
                                    >
                                        <CheckIcon className="h-4 w-4" />
                                        Save
                                    </button>
                                    <button
                                        onClick={() => {
                                            setEditContent(viewingAsset.content || '');
                                            setIsEditing(false);
                                        }}
                                        className="flex items-center gap-1 px-3 py-2 text-sm text-gray-600 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
                                    >
                                        <XMarkIcon className="h-4 w-4" />
                                        Cancel
                                    </button>
                                </>
                            )}
                            <button
                                onClick={handleCloseViewer}
                                className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg"
                            >
                                <XMarkIcon className="h-6 w-6" />
                            </button>
                        </div>
                    </div>

                    {/* Content */}
                    <div className="flex-1 overflow-y-auto p-6">
                        {(() => {
                            // Check if this is table data
                            const tableData = viewingAsset.asset_type === 'data' ? parseTableData(viewingAsset.content || undefined) : null;

                            if (isEditing) {
                                return (
                                    <textarea
                                        value={editContent}
                                        onChange={(e) => setEditContent(e.target.value)}
                                        className="w-full h-full min-h-[60vh] p-4 text-sm font-mono bg-gray-50 dark:bg-gray-950 border border-gray-300 dark:border-gray-600 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 dark:text-white"
                                    />
                                );
                            }

                            if (tableData) {
                                return (
                                    <div className="h-[60vh] border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
                                        <AssetTableViewer tableData={tableData} />
                                    </div>
                                );
                            }

                            if (viewingAsset.asset_type === 'code') {
                                return (
                                    <pre className="p-4 bg-gray-900 dark:bg-black rounded-lg text-sm text-gray-100 overflow-x-auto whitespace-pre-wrap min-h-[60vh]">
                                        {viewingAsset.content || 'No content'}
                                    </pre>
                                );
                            }

                            return (
                                <div className="p-4 bg-gray-50 dark:bg-gray-950 rounded-lg min-h-[60vh]">
                                    <MarkdownRenderer content={viewingAsset.content || 'No content'} />
                                </div>
                            );
                        })()}
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
            <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl w-[90vw] h-[85vh] max-w-5xl flex flex-col">
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                    <div className="flex items-center gap-3">
                        <DocumentIcon className="h-6 w-6 text-orange-500" />
                        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                            Assets
                        </h2>
                        <span className="text-sm text-gray-500">({counts.all} total)</span>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg"
                    >
                        <XMarkIcon className="h-6 w-6" />
                    </button>
                </div>

                {/* Toolbar */}
                <div className="px-6 py-3 border-b border-gray-200 dark:border-gray-700 space-y-3">
                    {/* Search */}
                    <div className="relative">
                        <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                        <input
                            type="text"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            placeholder="Search assets..."
                            className="w-full pl-9 pr-4 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                        />
                    </div>

                    {/* Filter tabs */}
                    <div className="flex flex-wrap gap-2">
                        {filterButtons.map(({ key, label, icon: Icon, color }) => (
                            counts[key] > 0 || key === 'all' || key === 'in_context' ? (
                                <button
                                    key={key}
                                    onClick={() => setFilter(key)}
                                    className={`px-3 py-1.5 text-sm rounded-full transition-colors flex items-center gap-1.5 ${
                                        filter === key
                                            ? 'bg-gray-900 dark:bg-white text-white dark:text-gray-900'
                                            : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                                    }`}
                                >
                                    {Icon && <Icon className={`h-3.5 w-3.5 ${filter === key ? '' : color}`} />}
                                    {label}
                                    {counts[key] > 0 && (
                                        <span className={`text-xs ${filter === key ? 'opacity-70' : 'text-gray-500'}`}>
                                            {counts[key]}
                                        </span>
                                    )}
                                </button>
                            ) : null
                        ))}
                    </div>
                </div>

                {/* Asset list */}
                <div className="flex-1 overflow-y-auto p-6">
                    {filteredAssets.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full text-gray-400 dark:text-gray-500">
                            <DocumentIcon className="h-12 w-12 mb-3 opacity-50" />
                            <p className="text-lg">No assets found</p>
                            {searchQuery && (
                                <p className="text-sm mt-1">Try a different search term</p>
                            )}
                        </div>
                    ) : (
                        <div className="space-y-2">
                            {filteredAssets.map((asset) => {
                                const typeInfo = getAssetTypeInfo(asset.asset_type);
                                const TypeIcon = typeInfo.icon;
                                const isConfirmingDelete = confirmDelete === asset.asset_id;

                                return (
                                    <div
                                        key={asset.asset_id}
                                        className={`rounded-lg border overflow-hidden ${
                                            asset.is_in_context
                                                ? 'border-orange-200 dark:border-orange-800 bg-orange-50 dark:bg-orange-900/20'
                                                : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800'
                                        }`}
                                    >
                                        {/* Asset row */}
                                        <div className="flex items-center gap-3 p-4">
                                            {/* Type icon */}
                                            <div className={`p-2 rounded-lg ${typeInfo.bg}`}>
                                                <TypeIcon className={`h-4 w-4 ${typeInfo.color}`} />
                                            </div>

                                            {/* Content */}
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm font-medium text-gray-900 dark:text-white">
                                                    {asset.name}
                                                </p>
                                                {asset.description && (
                                                    <p className="text-xs text-gray-500 mt-1 line-clamp-1">
                                                        {asset.description}
                                                    </p>
                                                )}
                                                <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
                                                    <span className={`px-2 py-0.5 rounded ${typeInfo.bg} ${typeInfo.color}`}>
                                                        {typeInfo.label}
                                                    </span>
                                                    <span>
                                                        {new Date(asset.created_at).toLocaleDateString()}
                                                    </span>
                                                </div>
                                            </div>

                                            {/* Actions */}
                                            <div className="flex items-center gap-1">
                                                {/* View/Edit button */}
                                                {asset.content && (
                                                    <button
                                                        onClick={() => handleViewAsset(asset)}
                                                        className="p-2 text-gray-400 hover:text-blue-500 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
                                                        title="View/Edit"
                                                    >
                                                        <ArrowsPointingOutIcon className="h-5 w-5" />
                                                    </button>
                                                )}

                                                {/* Context toggle */}
                                                <button
                                                    onClick={() => onToggleContext(asset.asset_id)}
                                                    className={`p-2 rounded-lg transition-colors ${
                                                        asset.is_in_context
                                                            ? 'text-orange-500 hover:bg-orange-100 dark:hover:bg-orange-900/50'
                                                            : 'text-gray-400 hover:text-orange-500 hover:bg-gray-100 dark:hover:bg-gray-700'
                                                    }`}
                                                    title={asset.is_in_context ? 'Remove from context' : 'Add to context'}
                                                >
                                                    {asset.is_in_context ? (
                                                        <CheckIcon className="h-5 w-5" />
                                                    ) : (
                                                        <CheckCircleOutlineIcon className="h-5 w-5" />
                                                    )}
                                                </button>

                                                {/* Delete button */}
                                                <button
                                                    onClick={() => handleDelete(asset.asset_id)}
                                                    className={`p-2 rounded-lg transition-colors ${
                                                        isConfirmingDelete
                                                            ? 'bg-red-500 text-white'
                                                            : 'text-gray-400 hover:text-red-500 hover:bg-gray-100 dark:hover:bg-gray-700'
                                                    }`}
                                                    title={isConfirmingDelete ? 'Click again to confirm' : 'Delete'}
                                                >
                                                    <TrashIcon className="h-5 w-5" />
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
