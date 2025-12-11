import { useState } from 'react';
import {
    XMarkIcon, DocumentIcon, TrashIcon,
    MagnifyingGlassIcon, DocumentTextIcon, CodeBracketIcon,
    LinkIcon, TableCellsIcon, PhotoIcon, PencilIcon,
    CheckIcon, ArrowsPointingOutIcon
} from '@heroicons/react/24/solid';
import { CheckCircleIcon as CheckCircleOutlineIcon } from '@heroicons/react/24/outline';
import { Asset, AssetType, AssetUpdate } from '../../lib/api';
import { MarkdownRenderer } from '../common/MarkdownRenderer';

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
            // In context first, then by date
            if (a.is_in_context && !b.is_in_context) return -1;
            if (!a.is_in_context && b.is_in_context) return 1;
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
                        {isEditing ? (
                            <textarea
                                value={editContent}
                                onChange={(e) => setEditContent(e.target.value)}
                                className="w-full h-full min-h-[60vh] p-4 text-sm font-mono bg-gray-50 dark:bg-gray-950 border border-gray-300 dark:border-gray-600 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 dark:text-white"
                            />
                        ) : viewingAsset.asset_type === 'code' ? (
                            <pre className="p-4 bg-gray-900 dark:bg-black rounded-lg text-sm text-gray-100 overflow-x-auto whitespace-pre-wrap min-h-[60vh]">
                                {viewingAsset.content || 'No content'}
                            </pre>
                        ) : (
                            <div className="p-4 bg-gray-50 dark:bg-gray-950 rounded-lg min-h-[60vh]">
                                <MarkdownRenderer content={viewingAsset.content || 'No content'} />
                            </div>
                        )}
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
