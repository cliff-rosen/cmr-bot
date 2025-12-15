/**
 * Workspace Mode System
 *
 * Determines what content to display in the workspace panel.
 * Uses a discriminated union for type-safe mode handling.
 */

import { ComponentType } from 'react';
import { ToolCall, WorkspacePayload } from '../../types/chat';
import { WorkflowInstanceState, WorkflowHandlers, WorkflowEvent } from '../workflows';

// =============================================================================
// Workspace Mode Types
// =============================================================================

export type WorkspaceMode =
    | { mode: 'empty' }
    | { mode: 'workflow'; instance: WorkflowInstanceState; handlers: WorkflowHandlers; isProcessing?: boolean; currentEvent?: WorkflowEvent | null }
    | { mode: 'workflow_loading'; handlers?: WorkflowHandlers | null; currentEvent?: WorkflowEvent | null }
    | { mode: 'tool'; tool: ToolCall }
    | { mode: 'tool_history'; history: ToolCall[] }
    | { mode: 'payload'; payload: WorkspacePayload };

// =============================================================================
// Mode Determination
// =============================================================================

export interface WorkspaceModeInputs {
    workflowInstance: WorkflowInstanceState | null;
    workflowHandlers: WorkflowHandlers | null;
    isWorkflowProcessing: boolean;
    currentWorkflowEvent: WorkflowEvent | null;
    selectedTool: ToolCall | null;
    selectedToolHistory: ToolCall[] | null;
    activePayload: WorkspacePayload | null;
}

/**
 * Determines the current workspace mode based on state.
 * Priority order is explicit in the function body.
 */
export function getWorkspaceMode(inputs: WorkspaceModeInputs): WorkspaceMode {
    const {
        workflowInstance,
        workflowHandlers,
        isWorkflowProcessing,
        currentWorkflowEvent,
        selectedTool,
        selectedToolHistory,
        activePayload,
    } = inputs;

    // Priority 1: Workflow loading state (processing but no instance yet)
    if (isWorkflowProcessing && !workflowInstance) {
        return {
            mode: 'workflow_loading',
            handlers: workflowHandlers,
            currentEvent: currentWorkflowEvent,
        };
    }

    // Priority 2: Active workflow instance
    if (workflowInstance && workflowHandlers) {
        return {
            mode: 'workflow',
            instance: workflowInstance,
            handlers: workflowHandlers,
            isProcessing: isWorkflowProcessing,
            currentEvent: currentWorkflowEvent,
        };
    }

    // Priority 3: Single tool inspection
    if (selectedTool) {
        return { mode: 'tool', tool: selectedTool };
    }

    // Priority 4: Tool history inspection
    if (selectedToolHistory && selectedToolHistory.length > 0) {
        return { mode: 'tool_history', history: selectedToolHistory };
    }

    // Priority 5: Payload display
    if (activePayload) {
        return { mode: 'payload', payload: activePayload };
    }

    // Default: Empty state
    return { mode: 'empty' };
}

// =============================================================================
// View Registry Types
// =============================================================================

/**
 * Props passed to payload view components
 */
export interface PayloadViewProps {
    payload: WorkspacePayload;
    onSaveAsAsset?: (payload: WorkspacePayload, andClose?: boolean) => void;
    isSaving?: boolean;
    onPayloadEdit?: (payload: WorkspacePayload) => void;
    onAccept?: (payload: WorkspacePayload) => void;
    onReject?: () => void;
    // Research workflow specific (for LLM-orchestrated research)
    onUpdateWorkflow?: (workflow: any) => void;
    onProceed?: () => void;
    onRunRetrieval?: () => void;
    onPauseRetrieval?: () => void;
    onCompile?: () => void;
    onComplete?: () => void;
}

/**
 * Props passed to workflow view components
 */
export interface WorkflowViewProps {
    instance: WorkflowInstanceState;
    handlers: WorkflowHandlers;
    isProcessing?: boolean;
    currentEvent?: WorkflowEvent | null;
}

/**
 * Registry mapping payload types to their view components
 */
export type PayloadViewRegistry = Record<string, ComponentType<PayloadViewProps>>;

/**
 * Registry mapping workflow IDs to their view components
 * If a workflow ID is not in the registry, the default view is used
 */
export type WorkflowViewRegistry = Record<string, ComponentType<WorkflowViewProps>>;
