/**
 * Workspace panel components
 * Export all workspace-related components from this barrel file
 */

// View components
export { default as StandardPayloadView } from './StandardPayloadView';
export { default as ToolHistoryView } from './ToolHistoryView';
export { default as ToolResultView } from './ToolResultView';
export { default as AgentPayloadView } from './AgentPayloadView';
export { default as TablePayloadView } from './TablePayloadView';
export { default as ResearchWorkflowView } from './ResearchWorkflowView';
export { default as ResearchResultView } from './ResearchResultView';
export { default as ReviewCollectionView } from './ReviewCollectionView';
export { default as WorkflowExecutionView } from './WorkflowExecutionView';
export { default as VendorFinderWorkflowView } from './VendorFinderWorkflowView';
export { default as IteratorProgress } from './IteratorProgress';
export { default as MapReduceProgress } from './MapReduceProgress';
export { default as ToolProgress } from './ToolProgress';

// Payload type configuration
export { payloadTypeConfig } from './types';
export type { PayloadTypeConfig } from './types';

// Re-export workspace mode system from lib (for convenience)
export {
    getWorkspaceMode,
    getPayloadView,
    getWorkflowView,
    payloadViewRegistry,
    workflowViewRegistry
} from '../../../lib/workspace';
export type {
    WorkspaceMode,
    WorkspaceModeInputs,
    PayloadViewProps,
    WorkflowViewProps
} from '../../../lib/workspace';
