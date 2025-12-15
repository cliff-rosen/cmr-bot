/**
 * Frontend Workflow Registry
 *
 * Maps workflow types to their view components and provides
 * a factory for creating workflow handlers.
 */

import { ComponentType } from 'react';
import { WorkflowInstanceState, WorkflowEvent } from '../../types/workflow';
import * as workflowApi from '../api/workflowEngineApi';

// State updater type (supports both direct value and functional updates)
type StateUpdater<T> = T | ((prevState: T) => T);

// Dependencies passed to handler factories
export interface WorkflowDeps {
    // Function to update the displayed workflow state (supports functional updates)
    setWorkflowState: (state: StateUpdater<WorkflowInstanceState | null>) => void;
    // Function to show a toast/notification
    showNotification?: (message: string, type: 'success' | 'error' | 'info') => void;
    // Function to indicate processing state (for UX feedback)
    setIsProcessing?: (isProcessing: boolean) => void;
    // Function to receive live events as they occur
    setCurrentEvent?: (event: WorkflowEvent | null) => void;
    // Conversation ID for association
    conversationId?: number;
}

// Handlers for workflow UI interactions
export interface WorkflowHandlers {
    // Called when user approves at a checkpoint
    onApprove: (userData?: Record<string, any>) => Promise<void>;
    // Called when user edits at a checkpoint
    onEdit: (userData: Record<string, any>) => Promise<void>;
    // Called when user rejects/cancels at a checkpoint
    onReject: () => Promise<void>;
    // Called to cancel the entire workflow
    onCancel: () => Promise<void>;
    // Called to pause the workflow
    onPause: () => Promise<void>;
}

// Props passed to workflow view components
export interface WorkflowViewProps {
    instanceState: WorkflowInstanceState;
    handlers: WorkflowHandlers;
    // Current event being processed (for animations/progress)
    currentEvent?: WorkflowEvent;
}

// Workflow UI configuration
export interface WorkflowUIConfig {
    // Icon identifier
    icon: string;
    // Primary color for theming
    color: string;
    // Component to render the workflow
    component: ComponentType<WorkflowViewProps>;
    // Stage-specific components (optional)
    stageComponents?: Record<string, ComponentType<WorkflowViewProps>>;
}

// Registry of workflow UI configurations
const workflowUIRegistry = new Map<string, WorkflowUIConfig>();

/**
 * Register a workflow UI configuration.
 */
export function registerWorkflowUI(workflowId: string, config: WorkflowUIConfig): void {
    workflowUIRegistry.set(workflowId, config);
}

/**
 * Get the UI configuration for a workflow.
 */
export function getWorkflowUI(workflowId: string): WorkflowUIConfig | undefined {
    return workflowUIRegistry.get(workflowId);
}

/**
 * Create handlers for a workflow instance.
 */
export function createWorkflowHandlers(
    instanceId: string,
    deps: WorkflowDeps,
    abortController?: AbortController
): WorkflowHandlers {
    const { setWorkflowState, showNotification, setIsProcessing, setCurrentEvent } = deps;

    // Store abort controller for cancellation
    let currentAbortController = abortController;

    // Helper to update node states incrementally based on events
    function updateNodeState(nodeId: string, status: 'pending' | 'running' | 'completed' | 'failed') {
        setWorkflowState((prevState: WorkflowInstanceState | null) => {
            if (!prevState) return prevState;
            return {
                ...prevState,
                node_states: {
                    ...prevState.node_states,
                    [nodeId]: {
                        ...prevState.node_states[nodeId],
                        status,
                        execution_count: (prevState.node_states[nodeId]?.execution_count || 0) + (status === 'running' ? 1 : 0)
                    }
                },
                // Update current_node for step_start
                ...(status === 'running' ? {
                    current_node: {
                        id: nodeId,
                        name: nodeId.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
                        description: '',
                        node_type: 'execute'
                    }
                } : {})
            };
        });
    }

    // Helper to process event stream and update state
    async function processEventStream(
        eventGenerator: AsyncGenerator<WorkflowEvent>
    ): Promise<void> {
        try {
            for await (const event of eventGenerator) {
                console.log('Workflow event:', event);

                // Send all events to the UI for live display
                setCurrentEvent?.(event);

                if (event.event_type === 'error') {
                    showNotification?.(event.error || 'Workflow error', 'error');
                    setIsProcessing?.(false);
                    setCurrentEvent?.(null);
                    // Refresh state to get error status
                    const state = await workflowApi.getWorkflowState(instanceId);
                    setWorkflowState(state);
                    return;
                }

                if (event.event_type === 'complete') {
                    showNotification?.('Workflow completed', 'success');
                    setIsProcessing?.(false);
                    setCurrentEvent?.(null);
                    const state = await workflowApi.getWorkflowState(instanceId);
                    setWorkflowState(state);
                    return;
                }

                if (event.event_type === 'cancelled') {
                    showNotification?.('Workflow cancelled', 'info');
                    setIsProcessing?.(false);
                    setCurrentEvent?.(null);
                    setWorkflowState(null);
                    return;
                }

                if (event.event_type === 'checkpoint') {
                    // At checkpoint - refresh state to show checkpoint UI
                    setIsProcessing?.(false);
                    setCurrentEvent?.(null);
                    const state = await workflowApi.getWorkflowState(instanceId);
                    setWorkflowState(state);
                    return; // Stop processing, wait for user action
                }

                // Update node states incrementally for step events
                if (event.event_type === 'step_start' && event.node_id) {
                    updateNodeState(event.node_id, 'running');
                }

                if (event.event_type === 'step_complete' && event.node_id) {
                    updateNodeState(event.node_id, 'completed');
                }

                // For step_progress, just continue (currentEvent is already set)
            }

            // Stream ended - refresh state
            setIsProcessing?.(false);
            setCurrentEvent?.(null);
            const state = await workflowApi.getWorkflowState(instanceId);
            setWorkflowState(state);
        } catch (err) {
            // Check if this is an abort error
            if (err instanceof Error && err.name === 'AbortError') {
                console.log('Workflow stream aborted');
                return; // Don't show error for intentional abort
            }
            // Re-throw other errors
            throw err;
        }
    }

    // Helper to set new abort controller for resume operations
    function setAbortController(controller: AbortController) {
        currentAbortController = controller;
    }

    return {
        onApprove: async (userData?: Record<string, any>) => {
            setIsProcessing?.(true);
            // Create new abort controller for this operation
            const controller = new AbortController();
            setAbortController(controller);
            const events = workflowApi.resumeWorkflow(instanceId, 'approve', userData, controller.signal);
            await processEventStream(events);
        },

        onEdit: async (userData: Record<string, any>) => {
            setIsProcessing?.(true);
            // Create new abort controller for this operation
            const controller = new AbortController();
            setAbortController(controller);
            const events = workflowApi.resumeWorkflow(instanceId, 'edit', userData, controller.signal);
            await processEventStream(events);
        },

        onReject: async () => {
            setIsProcessing?.(true);
            // Create new abort controller for this operation
            const controller = new AbortController();
            setAbortController(controller);
            const events = workflowApi.resumeWorkflow(instanceId, 'reject', undefined, controller.signal);
            await processEventStream(events);
        },

        onCancel: async () => {
            // First abort any running stream
            if (currentAbortController) {
                currentAbortController.abort();
            }
            // Then tell backend to cancel
            try {
                await workflowApi.cancelWorkflow(instanceId);
            } catch (err) {
                console.log('Cancel request error (may be expected):', err);
            }
            // Update UI state
            setIsProcessing?.(false);
            setCurrentEvent?.(null);
            setWorkflowState(null);
            showNotification?.('Workflow cancelled', 'info');
        },

        onPause: async () => {
            // Abort running stream
            if (currentAbortController) {
                currentAbortController.abort();
            }
            // Tell backend to pause
            try {
                await workflowApi.pauseWorkflow(instanceId);
                const state = await workflowApi.getWorkflowState(instanceId);
                setWorkflowState(state);
                showNotification?.('Workflow paused', 'info');
            } catch (err) {
                console.error('Pause error:', err);
            }
            setIsProcessing?.(false);
        },
    };
}

/**
 * Start a workflow and return the initial state.
 */
export async function startWorkflowWithUI(
    workflowId: string,
    initialInput: Record<string, any>,
    deps: WorkflowDeps
): Promise<{ instanceId: string; handlers: WorkflowHandlers }> {
    // Indicate processing has started
    deps.setIsProcessing?.(true);

    // Create abort controller for the initial run
    const abortController = new AbortController();

    // Create the instance
    const { instance_id } = await workflowApi.startWorkflow(
        workflowId,
        initialInput,
        deps.conversationId
    );

    // Create handlers with the abort controller
    const handlers = createWorkflowHandlers(instance_id, deps, abortController);

    // Start running and process events
    const events = workflowApi.runWorkflow(instance_id, abortController.signal);

    // Process in background
    (async () => {
        try {
            for await (const event of events) {
                console.log('Workflow event:', event);

                // Send all events to the UI for live display
                deps.setCurrentEvent?.(event);

                if (event.event_type === 'error') {
                    deps.showNotification?.(event.error || 'Workflow error', 'error');
                    deps.setIsProcessing?.(false);
                    deps.setCurrentEvent?.(null);
                    const state = await workflowApi.getWorkflowState(instance_id);
                    deps.setWorkflowState(state);
                    return;
                }

                if (event.event_type === 'complete') {
                    deps.showNotification?.('Workflow completed', 'success');
                    deps.setIsProcessing?.(false);
                    deps.setCurrentEvent?.(null);
                    const state = await workflowApi.getWorkflowState(instance_id);
                    deps.setWorkflowState(state);
                    return;
                }

                if (event.event_type === 'checkpoint') {
                    deps.setIsProcessing?.(false);
                    deps.setCurrentEvent?.(null);
                    const state = await workflowApi.getWorkflowState(instance_id);
                    deps.setWorkflowState(state);
                    return;
                }

                // For step_start and step_complete, continue processing
            }

            // Stream ended
            deps.setIsProcessing?.(false);
            deps.setCurrentEvent?.(null);
            const state = await workflowApi.getWorkflowState(instance_id);
            deps.setWorkflowState(state);
        } catch (err) {
            // Handle abort gracefully
            if (err instanceof Error && err.name === 'AbortError') {
                console.log('Workflow stream aborted during start');
                return;
            }
            console.error('Error processing workflow events:', err);
            deps.setIsProcessing?.(false);
            deps.setCurrentEvent?.(null);
        }
    })();

    return { instanceId: instance_id, handlers };
}
