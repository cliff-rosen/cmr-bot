/**
 * WorkflowGraphView
 *
 * Displays a designed workflow graph from the design_workflow tool.
 * Shows nodes with step_type-specific details, edges, and data flow.
 */

import { useState, useMemo } from 'react';
import {
    BeakerIcon,
    CpuChipIcon,
    PauseCircleIcon,
    ChevronDownIcon,
    ChevronRightIcon,
    ArrowLongRightIcon,
    WrenchScrewdriverIcon,
    DocumentTextIcon,
    ExclamationTriangleIcon,
    ArrowDownIcon,
    LightBulbIcon,
    QuestionMarkCircleIcon,
    CodeBracketIcon,
} from '@heroicons/react/24/solid';
import {
    WorkflowNode,
    WorkflowEdge,
    WorkflowGraphData,
    WorkflowStepDefinition,
    StepType,
} from '../../../types/chat';
import { PayloadViewProps } from '../../../lib/workspace/workspaceMode';

interface WorkflowGraphViewProps extends PayloadViewProps {
    onTest?: (workflow: WorkflowGraphData, inputs: Record<string, any>) => void;
}

// Step type styling
function getStepTypeStyle(stepType: StepType) {
    switch (stepType) {
        case 'tool_call':
            return {
                icon: WrenchScrewdriverIcon,
                bg: 'bg-purple-50 dark:bg-purple-900/20',
                border: 'border-purple-200 dark:border-purple-800',
                iconColor: 'text-purple-600 dark:text-purple-400',
                label: 'Tool Call',
                labelBg: 'bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300',
            };
        case 'llm_transform':
            return {
                icon: LightBulbIcon,
                bg: 'bg-blue-50 dark:bg-blue-900/20',
                border: 'border-blue-200 dark:border-blue-800',
                iconColor: 'text-blue-600 dark:text-blue-400',
                label: 'LLM Transform',
                labelBg: 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300',
            };
        case 'llm_decision':
            return {
                icon: QuestionMarkCircleIcon,
                bg: 'bg-green-50 dark:bg-green-900/20',
                border: 'border-green-200 dark:border-green-800',
                iconColor: 'text-green-600 dark:text-green-400',
                label: 'LLM Decision',
                labelBg: 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300',
            };
        default:
            return {
                icon: CpuChipIcon,
                bg: 'bg-gray-50 dark:bg-gray-900/20',
                border: 'border-gray-200 dark:border-gray-800',
                iconColor: 'text-gray-600 dark:text-gray-400',
                label: 'Execute',
                labelBg: 'bg-gray-100 dark:bg-gray-900/40 text-gray-700 dark:text-gray-300',
            };
    }
}

// Checkpoint styling
const checkpointStyle = {
    icon: PauseCircleIcon,
    bg: 'bg-amber-50 dark:bg-amber-900/20',
    border: 'border-amber-200 dark:border-amber-800',
    iconColor: 'text-amber-600 dark:text-amber-400',
    label: 'Checkpoint',
    labelBg: 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300',
};

// Extract field references from input_mapping templates
function extractFieldsFromMapping(mapping: Record<string, string>): string[] {
    const fields = new Set<string>();
    Object.values(mapping).forEach(template => {
        const matches = template.match(/\{(\w+)(?:\.\w+)?\}/g);
        if (matches) {
            matches.forEach(m => {
                // Extract field name (before any dot)
                const field = m.replace(/[{}]/g, '').split('.')[0];
                fields.add(field);
            });
        }
    });
    return Array.from(fields);
}

// Render step definition details based on step_type
function StepDetails({ stepDef }: { stepDef: WorkflowStepDefinition }) {
    const inputFields = stepDef.step_type === 'tool_call' && stepDef.input_mapping
        ? extractFieldsFromMapping(stepDef.input_mapping)
        : stepDef.input_fields || [];

    return (
        <div className="space-y-3 text-sm">
            {/* Data Flow Summary */}
            <div className="flex items-center gap-2 p-2 bg-gray-100 dark:bg-gray-800 rounded-lg">
                <div className="flex-1">
                    <span className="text-xs text-gray-500 dark:text-gray-400">Reads:</span>
                    <div className="flex flex-wrap gap-1 mt-0.5">
                        {inputFields.length > 0 ? inputFields.map(f => (
                            <code key={f} className="text-xs px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 rounded">
                                {f}
                            </code>
                        )) : (
                            <span className="text-xs text-gray-400 italic">none</span>
                        )}
                    </div>
                </div>
                <ArrowLongRightIcon className="h-4 w-4 text-gray-400 flex-shrink-0" />
                <div className="flex-1">
                    <span className="text-xs text-gray-500 dark:text-gray-400">Writes:</span>
                    <div className="mt-0.5">
                        <code className="text-xs px-1.5 py-0.5 bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 rounded">
                            {stepDef.output_field}
                        </code>
                    </div>
                </div>
            </div>

            {/* Step Type Specific Details */}
            {stepDef.step_type === 'tool_call' && (
                <>
                    <div>
                        <span className="font-medium text-gray-700 dark:text-gray-300">Tool:</span>
                        <code className="ml-2 px-2 py-0.5 bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300 rounded text-xs">
                            {stepDef.tool}
                        </code>
                    </div>
                    {stepDef.input_mapping && (
                        <div>
                            <span className="font-medium text-gray-700 dark:text-gray-300">Input Mapping:</span>
                            <div className="mt-1 p-2 bg-gray-50 dark:bg-gray-900 rounded text-xs font-mono overflow-x-auto">
                                {Object.entries(stepDef.input_mapping).map(([key, value]) => (
                                    <div key={key} className="text-gray-600 dark:text-gray-400">
                                        <span className="text-purple-600 dark:text-purple-400">{key}</span>
                                        <span className="text-gray-400"> = </span>
                                        <span className="text-blue-600 dark:text-blue-400">"{value}"</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </>
            )}

            {stepDef.step_type === 'llm_transform' && (
                <>
                    <div>
                        <span className="font-medium text-gray-700 dark:text-gray-300">Goal:</span>
                        <p className="text-gray-600 dark:text-gray-400 mt-0.5">{stepDef.goal}</p>
                    </div>
                    {stepDef.output_schema && (
                        <div>
                            <span className="font-medium text-gray-700 dark:text-gray-300">Output Schema:</span>
                            <pre className="mt-1 p-2 bg-gray-50 dark:bg-gray-900 rounded text-xs font-mono overflow-x-auto max-h-32 text-gray-800 dark:text-gray-200">
                                {JSON.stringify(stepDef.output_schema, null, 2)}
                            </pre>
                        </div>
                    )}
                </>
            )}

            {stepDef.step_type === 'llm_decision' && (
                <>
                    <div>
                        <span className="font-medium text-gray-700 dark:text-gray-300">Goal:</span>
                        <p className="text-gray-600 dark:text-gray-400 mt-0.5">{stepDef.goal}</p>
                    </div>
                    {stepDef.choices && (
                        <div>
                            <span className="font-medium text-gray-700 dark:text-gray-300">Choices:</span>
                            <div className="flex flex-wrap gap-1 mt-1">
                                {stepDef.choices.map(choice => (
                                    <code key={choice} className="text-xs px-2 py-0.5 bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 rounded">
                                        {choice}
                                    </code>
                                ))}
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}

// Individual node card
function NodeCard({
    node,
    isExpanded,
    onToggle,
    isEntry,
}: {
    node: WorkflowNode;
    isExpanded: boolean;
    onToggle: () => void;
    isEntry: boolean;
}) {
    const stepDef = node.step_definition;
    const isCheckpoint = node.node_type === 'checkpoint';

    const style = isCheckpoint
        ? checkpointStyle
        : (stepDef?.step_type ? getStepTypeStyle(stepDef.step_type) : getStepTypeStyle('llm_transform'));

    const Icon = style.icon;

    return (
        <div
            className={`rounded-lg border-2 ${style.bg} ${style.border} ${
                isEntry ? 'ring-2 ring-green-500 ring-offset-2 dark:ring-offset-gray-900' : ''
            }`}
        >
            <button
                onClick={onToggle}
                className="w-full p-3 text-left flex items-start gap-3"
            >
                <Icon className={`h-5 w-5 mt-0.5 flex-shrink-0 ${style.iconColor}`} />
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium text-gray-900 dark:text-white">
                            {node.name}
                        </span>
                        <span className={`text-xs px-1.5 py-0.5 rounded ${style.labelBg}`}>
                            {style.label}
                        </span>
                        {isEntry && (
                            <span className="text-xs px-1.5 py-0.5 rounded bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300">
                                Entry
                            </span>
                        )}
                    </div>

                    {/* Quick summary line */}
                    <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 flex items-center gap-2 flex-wrap">
                        {!isCheckpoint && stepDef && (
                            <>
                                {stepDef.step_type === 'tool_call' && stepDef.tool && (
                                    <span className="flex items-center gap-1">
                                        <WrenchScrewdriverIcon className="h-3 w-3" />
                                        <code className="text-purple-600 dark:text-purple-400">{stepDef.tool}</code>
                                    </span>
                                )}
                                <span className="text-gray-400">→</span>
                                <code className="text-green-600 dark:text-green-400">{stepDef.output_field}</code>
                            </>
                        )}
                        {isCheckpoint && node.checkpoint_config && (
                            <span>{node.checkpoint_config.title}</span>
                        )}
                    </div>
                </div>
                {isExpanded ? (
                    <ChevronDownIcon className="h-5 w-5 text-gray-400 flex-shrink-0" />
                ) : (
                    <ChevronRightIcon className="h-5 w-5 text-gray-400 flex-shrink-0" />
                )}
            </button>

            {isExpanded && (
                <div className="px-3 pb-3 border-t border-gray-200 dark:border-gray-700 mt-1 pt-3 ml-8">
                    {!isCheckpoint && stepDef && <StepDetails stepDef={stepDef} />}

                    {isCheckpoint && node.checkpoint_config && (
                        <div className="space-y-2 text-sm">
                            <div>
                                <span className="font-medium text-gray-700 dark:text-gray-300">Description:</span>
                                <p className="text-gray-600 dark:text-gray-400 mt-0.5">
                                    {node.checkpoint_config.description}
                                </p>
                            </div>
                            <div>
                                <span className="font-medium text-gray-700 dark:text-gray-300">Actions:</span>
                                <div className="flex flex-wrap gap-1 mt-1">
                                    {node.checkpoint_config.allowed_actions.map((action) => (
                                        <span
                                            key={action}
                                            className="text-xs px-2 py-0.5 bg-gray-100 dark:bg-gray-800 rounded capitalize"
                                        >
                                            {action}
                                        </span>
                                    ))}
                                </div>
                            </div>
                            {node.checkpoint_config.editable_fields?.length > 0 && (
                                <div>
                                    <span className="font-medium text-gray-700 dark:text-gray-300">Editable:</span>
                                    <div className="flex flex-wrap gap-1 mt-1">
                                        {node.checkpoint_config.editable_fields.map(f => (
                                            <code key={f} className="text-xs px-1.5 py-0.5 bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 rounded">
                                                {f}
                                            </code>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// Edge display
function EdgeDisplay({ edge, nodes }: { edge: WorkflowEdge; nodes: Record<string, WorkflowNode> }) {
    const fromNode = nodes[edge.from_node];
    const toNode = nodes[edge.to_node];

    return (
        <div className="flex items-center gap-2 py-1 px-2 text-sm text-gray-500 dark:text-gray-400">
            <span className="font-medium">{fromNode?.name || edge.from_node}</span>
            <ArrowLongRightIcon className="h-4 w-4 flex-shrink-0" />
            <span className="font-medium">{toNode?.name || edge.to_node}</span>
            {edge.condition_expr && (
                <code className="text-xs px-2 py-0.5 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded ml-1">
                    if: {edge.condition_expr}
                </code>
            )}
        </div>
    );
}

// Data flow summary
function DataFlowSummary({ workflow }: { workflow: WorkflowGraphData }) {
    // Collect all fields
    const inputSchemaFields = Object.keys(workflow.input_schema?.properties || {});
    const outputFields: { field: string; node: string; stepType: string }[] = [];

    Object.entries(workflow.nodes).forEach(([id, node]) => {
        if (node.step_definition?.output_field) {
            outputFields.push({
                field: node.step_definition.output_field,
                node: node.name,
                stepType: node.step_definition.step_type,
            });
        }
    });

    return (
        <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3">
            <h4 className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">Data Flow</h4>

            <div className="space-y-2 text-xs">
                <div>
                    <span className="text-gray-500 dark:text-gray-400">Initial Inputs:</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                        {inputSchemaFields.map(f => (
                            <code key={f} className="px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 rounded">
                                {f}
                            </code>
                        ))}
                    </div>
                </div>

                <div className="flex justify-center">
                    <ArrowDownIcon className="h-4 w-4 text-gray-400" />
                </div>

                <div>
                    <span className="text-gray-500 dark:text-gray-400">Produced Fields:</span>
                    <div className="space-y-1 mt-1">
                        {outputFields.map(({ field, node, stepType }, idx) => (
                            <div key={`${node}-${field}-${idx}`} className="flex items-center gap-2">
                                <code className="px-1.5 py-0.5 bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 rounded">
                                    {field}
                                </code>
                                <span className="text-gray-400">←</span>
                                <span className="text-gray-600 dark:text-gray-400">{node}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}

export default function WorkflowGraphView({ payload, onTest }: WorkflowGraphViewProps) {
    const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
    const [showDataFlow, setShowDataFlow] = useState(true);
    const [showAllEdges, setShowAllEdges] = useState(false);
    const [inputValues, setInputValues] = useState<Record<string, string>>({});

    const workflow = payload.workflow_graph_data;

    const inputFields = useMemo(() => {
        const schema = workflow?.input_schema;
        if (!schema?.properties) return [];
        return Object.entries(schema.properties).map(([key, prop]: [string, any]) => ({
            key,
            type: prop.type || 'string',
            description: prop.description || '',
            required: schema.required?.includes(key) ?? false,
        }));
    }, [workflow]);

    const handleTest = () => {
        if (workflow && onTest) {
            onTest(workflow, inputValues);
        }
    };

    const canTest = useMemo(() => {
        if (!workflow?.input_schema?.required) return true;
        return workflow.input_schema.required.every(
            (key: string) => inputValues[key]?.trim()
        );
    }, [workflow, inputValues]);

    if (!workflow) {
        return (
            <div className="h-full flex flex-col items-center justify-center p-8 text-gray-500 dark:text-gray-400">
                <ExclamationTriangleIcon className="h-12 w-12 mb-4 opacity-50" />
                <p>No workflow data available</p>
            </div>
        );
    }

    const toggleNode = (nodeId: string) => {
        setExpandedNodes((prev) => {
            const next = new Set(prev);
            if (next.has(nodeId)) next.delete(nodeId);
            else next.add(nodeId);
            return next;
        });
    };

    const orderedNodes = useMemo(() => {
        const visited = new Set<string>();
        const order: string[] = [];
        const queue = [workflow.entry_node];

        while (queue.length > 0) {
            const nodeId = queue.shift()!;
            if (visited.has(nodeId)) continue;
            visited.add(nodeId);
            order.push(nodeId);

            const outgoing = workflow.edges.filter((e) => e.from_node === nodeId);
            for (const edge of outgoing) {
                if (!visited.has(edge.to_node)) {
                    queue.push(edge.to_node);
                }
            }
        }

        for (const nodeId of Object.keys(workflow.nodes)) {
            if (!visited.has(nodeId)) {
                order.push(nodeId);
            }
        }

        return order;
    }, [workflow]);

    const nodeCount = Object.keys(workflow.nodes).length;
    const toolCallCount = Object.values(workflow.nodes).filter(
        n => n.step_definition?.step_type === 'tool_call'
    ).length;
    const transformCount = Object.values(workflow.nodes).filter(
        n => n.step_definition?.step_type === 'llm_transform'
    ).length;
    const decisionCount = Object.values(workflow.nodes).filter(
        n => n.step_definition?.step_type === 'llm_decision'
    ).length;
    const checkpointCount = Object.values(workflow.nodes).filter(
        n => n.node_type === 'checkpoint'
    ).length;

    return (
        <div className="h-full flex flex-col">
            {/* Header */}
            <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                            <DocumentTextIcon className="h-5 w-5 text-indigo-500" />
                            <h2 className="text-lg font-semibold text-gray-900 dark:text-white truncate">
                                {workflow.name}
                            </h2>
                        </div>
                        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                            {workflow.description}
                        </p>
                        <div className="flex items-center gap-2 mt-2 text-xs flex-wrap">
                            <span className="text-gray-500">{nodeCount} nodes:</span>
                            {toolCallCount > 0 && (
                                <span className="px-1.5 py-0.5 bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300 rounded">
                                    {toolCallCount} tool
                                </span>
                            )}
                            {transformCount > 0 && (
                                <span className="px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 rounded">
                                    {transformCount} transform
                                </span>
                            )}
                            {decisionCount > 0 && (
                                <span className="px-1.5 py-0.5 bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 rounded">
                                    {decisionCount} decision
                                </span>
                            )}
                            {checkpointCount > 0 && (
                                <span className="px-1.5 py-0.5 bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 rounded">
                                    {checkpointCount} checkpoint
                                </span>
                            )}
                        </div>
                    </div>
                    {onTest && (
                        <button
                            onClick={handleTest}
                            disabled={!canTest}
                            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors flex-shrink-0 ${
                                canTest
                                    ? 'bg-blue-600 hover:bg-blue-700 text-white'
                                    : 'bg-gray-300 dark:bg-gray-700 text-gray-500 cursor-not-allowed'
                            }`}
                        >
                            <BeakerIcon className="h-4 w-4" />
                            Test
                        </button>
                    )}
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {/* Data Flow Summary */}
                <div>
                    <button
                        onClick={() => setShowDataFlow(!showDataFlow)}
                        className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
                    >
                        {showDataFlow ? <ChevronDownIcon className="h-4 w-4" /> : <ChevronRightIcon className="h-4 w-4" />}
                        Data Flow Overview
                    </button>
                    {showDataFlow && <DataFlowSummary workflow={workflow} />}
                </div>

                {/* Nodes */}
                <div>
                    <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                        Workflow Steps
                    </h3>
                    <div className="space-y-2">
                        {orderedNodes.map((nodeId) => {
                            const node = workflow.nodes[nodeId];
                            if (!node) return null;
                            return (
                                <NodeCard
                                    key={nodeId}
                                    node={node}
                                    isExpanded={expandedNodes.has(nodeId)}
                                    onToggle={() => toggleNode(nodeId)}
                                    isEntry={nodeId === workflow.entry_node}
                                />
                            );
                        })}
                    </div>
                </div>

                {/* Edges */}
                <div>
                    <button
                        onClick={() => setShowAllEdges(!showAllEdges)}
                        className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
                    >
                        {showAllEdges ? <ChevronDownIcon className="h-4 w-4" /> : <ChevronRightIcon className="h-4 w-4" />}
                        Flow Connections ({workflow.edges.length})
                    </button>
                    {showAllEdges && (
                        <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-2 space-y-1">
                            {workflow.edges.map((edge, idx) => (
                                <EdgeDisplay key={idx} edge={edge} nodes={workflow.nodes} />
                            ))}
                        </div>
                    )}
                </div>

                {/* Test Inputs Form */}
                {inputFields.length > 0 && (
                    <div>
                        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                            Test Inputs
                        </h3>
                        <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3 space-y-3">
                            {inputFields.map((field) => (
                                <div key={field.key}>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                        <code className="text-blue-600 dark:text-blue-400">{field.key}</code>
                                        {field.required && <span className="text-red-500 ml-1">*</span>}
                                    </label>
                                    {field.description && (
                                        <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">
                                            {field.description}
                                        </p>
                                    )}
                                    <textarea
                                        value={inputValues[field.key] || ''}
                                        onChange={(e) => setInputValues(prev => ({
                                            ...prev,
                                            [field.key]: e.target.value
                                        }))}
                                        placeholder={`Enter ${field.key}...`}
                                        rows={2}
                                        className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                                    />
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
