/**
 * WorkflowSelectorModal
 *
 * Modal for browsing and starting workflows.
 */

import { useState, useEffect, useCallback } from 'react';
import {
    XMarkIcon,
    BeakerIcon,
    DocumentTextIcon,
    ChartBarIcon,
    CpuChipIcon,
    PlayIcon,
    ArrowRightIcon,
} from '@heroicons/react/24/solid';
import { listWorkflows, WorkflowSummary, WorkflowTemplate, getWorkflowTemplate } from '../../lib/workflows';

interface WorkflowSelectorModalProps {
    isOpen: boolean;
    onClose: () => void;
    onStartWorkflow: (workflowId: string, initialInput: Record<string, any>) => void;
}

// Icon mapping
const ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
    beaker: BeakerIcon,
    document: DocumentTextIcon,
    chart: ChartBarIcon,
    cpu: CpuChipIcon,
};

// Category colors
const CATEGORY_COLORS: Record<string, string> = {
    research: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300',
    data: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
    content: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
    automation: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300',
};

export default function WorkflowSelectorModal({
    isOpen,
    onClose,
    onStartWorkflow,
}: WorkflowSelectorModalProps) {
    const [workflows, setWorkflows] = useState<WorkflowSummary[]>([]);
    const [categories, setCategories] = useState<string[]>([]);
    const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
    const [selectedWorkflow, setSelectedWorkflow] = useState<WorkflowTemplate | null>(null);
    const [inputValues, setInputValues] = useState<Record<string, string>>({});
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Load workflows
    useEffect(() => {
        if (!isOpen) return;

        const load = async () => {
            setIsLoading(true);
            setError(null);
            try {
                const result = await listWorkflows();
                setWorkflows(result.workflows);
                setCategories(result.categories);
            } catch (e) {
                setError('Failed to load workflows');
                console.error(e);
            } finally {
                setIsLoading(false);
            }
        };

        load();
    }, [isOpen]);

    // Load selected workflow details
    const handleSelectWorkflow = useCallback(async (workflow: WorkflowSummary) => {
        try {
            const template = await getWorkflowTemplate(workflow.id);
            setSelectedWorkflow(template);
            // Initialize input values
            const initialValues: Record<string, string> = {};
            if (template.input_schema.properties) {
                for (const key of Object.keys(template.input_schema.properties)) {
                    initialValues[key] = '';
                }
            }
            setInputValues(initialValues);
        } catch (e) {
            console.error('Failed to load workflow template:', e);
        }
    }, []);

    // Handle start
    const handleStart = useCallback(() => {
        if (!selectedWorkflow) return;

        // Validate required fields
        const required = selectedWorkflow.input_schema.required || [];
        for (const field of required) {
            if (!inputValues[field]?.trim()) {
                setError(`${field} is required`);
                return;
            }
        }

        onStartWorkflow(selectedWorkflow.id, inputValues);
        onClose();
    }, [selectedWorkflow, inputValues, onStartWorkflow, onClose]);

    // Reset on close
    useEffect(() => {
        if (!isOpen) {
            setSelectedWorkflow(null);
            setInputValues({});
            setSelectedCategory(null);
            setError(null);
        }
    }, [isOpen]);

    if (!isOpen) return null;

    // Filter workflows by category
    const filteredWorkflows = selectedCategory
        ? workflows.filter(w => w.category === selectedCategory)
        : workflows;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
            <div className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col">
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                    <div>
                        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                            {selectedWorkflow ? selectedWorkflow.name : 'Start a Workflow'}
                        </h2>
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                            {selectedWorkflow
                                ? selectedWorkflow.description
                                : 'Choose a workflow template to get started'}
                        </p>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                    >
                        <XMarkIcon className="h-5 w-5" />
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-6">
                    {isLoading ? (
                        <div className="flex items-center justify-center h-40">
                            <div className="text-gray-500">Loading workflows...</div>
                        </div>
                    ) : error && !selectedWorkflow ? (
                        <div className="flex items-center justify-center h-40">
                            <div className="text-red-500">{error}</div>
                        </div>
                    ) : selectedWorkflow ? (
                        // Workflow input form
                        <div className="space-y-6">
                            {/* Steps overview */}
                            <div>
                                <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                                    Workflow Steps
                                </h3>
                                <div className="flex flex-wrap gap-2">
                                    {Object.values(selectedWorkflow.nodes || {})
                                        .filter(n => n.node_type === 'execute' || n.node_type === 'checkpoint')
                                        .map((node, i) => (
                                            <div
                                                key={node.id}
                                                className="flex items-center gap-2 px-3 py-1.5 bg-gray-100 dark:bg-gray-800 rounded-full text-sm"
                                            >
                                                <span className="w-5 h-5 flex items-center justify-center bg-gray-200 dark:bg-gray-700 rounded-full text-xs">
                                                    {i + 1}
                                                </span>
                                                <span className="text-gray-700 dark:text-gray-300">
                                                    {node.name}
                                                </span>
                                            </div>
                                        ))}
                                </div>
                            </div>

                            {/* Input fields */}
                            <div>
                                <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                                    Input
                                </h3>
                                {selectedWorkflow.input_schema.properties &&
                                    Object.entries(selectedWorkflow.input_schema.properties).map(
                                        ([key, schema]: [string, any]) => (
                                            <div key={key} className="mb-4">
                                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                                    {key}
                                                    {selectedWorkflow.input_schema.required?.includes(key) && (
                                                        <span className="text-red-500 ml-1">*</span>
                                                    )}
                                                </label>
                                                <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                                                    {schema.description}
                                                </p>
                                                <textarea
                                                    value={inputValues[key] || ''}
                                                    onChange={(e) =>
                                                        setInputValues((prev) => ({
                                                            ...prev,
                                                            [key]: e.target.value,
                                                        }))
                                                    }
                                                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white resize-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                                                    rows={3}
                                                    placeholder={`Enter ${key}...`}
                                                />
                                            </div>
                                        )
                                    )}

                                {error && (
                                    <div className="text-red-500 text-sm mt-2">{error}</div>
                                )}
                            </div>
                        </div>
                    ) : (
                        // Workflow list
                        <div className="space-y-6">
                            {/* Category filter */}
                            {categories.length > 1 && (
                                <div className="flex flex-wrap gap-2">
                                    <button
                                        onClick={() => setSelectedCategory(null)}
                                        className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                                            selectedCategory === null
                                                ? 'bg-gray-900 text-white dark:bg-white dark:text-gray-900'
                                                : 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                                        }`}
                                    >
                                        All
                                    </button>
                                    {categories.map((cat) => (
                                        <button
                                            key={cat}
                                            onClick={() => setSelectedCategory(cat)}
                                            className={`px-3 py-1.5 rounded-full text-sm font-medium capitalize transition-colors ${
                                                selectedCategory === cat
                                                    ? 'bg-gray-900 text-white dark:bg-white dark:text-gray-900'
                                                    : 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                                            }`}
                                        >
                                            {cat}
                                        </button>
                                    ))}
                                </div>
                            )}

                            {/* Workflow grid */}
                            <div className="grid grid-cols-1 gap-4">
                                {filteredWorkflows.map((workflow) => {
                                    const Icon = ICONS[workflow.icon] || BeakerIcon;
                                    const categoryColor =
                                        CATEGORY_COLORS[workflow.category] || CATEGORY_COLORS.research;

                                    return (
                                        <button
                                            key={workflow.id}
                                            onClick={() => handleSelectWorkflow(workflow)}
                                            className="flex items-start gap-4 p-4 border border-gray-200 dark:border-gray-700 rounded-xl hover:border-purple-300 dark:hover:border-purple-700 hover:bg-purple-50 dark:hover:bg-purple-900/10 transition-colors text-left"
                                        >
                                            <div className="flex-shrink-0 w-12 h-12 flex items-center justify-center bg-purple-100 dark:bg-purple-900/30 rounded-xl">
                                                <Icon className="h-6 w-6 text-purple-600 dark:text-purple-400" />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2 mb-1">
                                                    <h3 className="font-medium text-gray-900 dark:text-white">
                                                        {workflow.name}
                                                    </h3>
                                                    <span
                                                        className={`px-2 py-0.5 rounded-full text-xs font-medium capitalize ${categoryColor}`}
                                                    >
                                                        {workflow.category}
                                                    </span>
                                                </div>
                                                <p className="text-sm text-gray-500 dark:text-gray-400 line-clamp-2">
                                                    {workflow.description}
                                                </p>
                                            </div>
                                            <ArrowRightIcon className="h-5 w-5 text-gray-400 flex-shrink-0" />
                                        </button>
                                    );
                                })}
                            </div>

                            {filteredWorkflows.length === 0 && (
                                <div className="text-center py-8 text-gray-500">
                                    No workflows available in this category
                                </div>
                            )}
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between px-6 py-4 border-t border-gray-200 dark:border-gray-700">
                    {selectedWorkflow ? (
                        <>
                            <button
                                onClick={() => setSelectedWorkflow(null)}
                                className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
                            >
                                Back
                            </button>
                            <button
                                onClick={handleStart}
                                className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
                            >
                                <PlayIcon className="h-4 w-4" />
                                Start Workflow
                            </button>
                        </>
                    ) : (
                        <div className="w-full text-center text-sm text-gray-500 dark:text-gray-400">
                            Select a workflow to get started
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
