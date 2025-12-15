/**
 * Workspace library
 *
 * Contains the workspace mode system and view registries.
 */

// Mode system
export { getWorkspaceMode } from './workspaceMode';
export type {
    WorkspaceMode,
    WorkspaceModeInputs,
    PayloadViewProps,
    WorkflowViewProps,
    PayloadViewRegistry,
    WorkflowViewRegistry,
} from './workspaceMode';

// View registries
export {
    getPayloadView,
    getWorkflowView,
    payloadViewRegistry,
    workflowViewRegistry
} from './workspaceRegistry';
