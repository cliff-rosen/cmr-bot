/**
 * Frontend Workflow Registry
 *
 * Maps workflow types to their view components and provides
 * a factory for creating workflow handlers.
 */

import { ComponentType } from 'react';
import { WorkflowInstanceState, WorkflowEvent } from '../../types/workflow';
import * as workflowApi from '../api/workflowEngineApi';

// Dependencies passed to handler factories
export interface WorkflowDeps {
    // Function to update the displayed workflow state
    setWorkflowState: (state: WorkflowInstanceState | null) => void;
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
    deps: WorkflowDeps
): WorkflowHandlers {
    const { setWorkflowState, showNotification, setIsProcessing, setCurrentEvent } = deps;

    // Helper to process event stream and update state
    async function processEventStream(
        eventGenerator: AsyncGenerator<WorkflowEvent>
    ): Promise<void> {
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

            // For step_start and step_complete, continue processing
            // The event has already been sent to setCurrentEvent
        }

        // Stream ended - refresh state
        setIsProcessing?.(false);
        setCurrentEvent?.(null);
        const state = await workflowApi.getWorkflowState(instanceId);
        setWorkflowState(state);
    }

    return {
        onApprove: async (userData?: Record<string, any>) => {
            setIsProcessing?.(true);
            const events = workflowApi.resumeWorkflow(instanceId, 'approve', userData);
            await processEventStream(events);
        },

        onEdit: async (userData: Record<string, any>) => {
            setIsProcessing?.(true);
            const events = workflowApi.resumeWorkflow(instanceId, 'edit', userData);
            await processEventStream(events);
        },

        onReject: async () => {
            setIsProcessing?.(true);
            const events = workflowApi.resumeWorkflow(instanceId, 'reject');
            await processEventStream(events);
        },

        onCancel: async () => {
            setIsProcessing?.(true);
            await workflowApi.cancelWorkflow(instanceId);
            setIsProcessing?.(false);
            setWorkflowState(null);
            showNotification?.('Workflow cancelled', 'info');
        },

        onPause: async () => {
            setIsProcessing?.(true);
            await workflowApi.pauseWorkflow(instanceId);
            setIsProcessing?.(false);
            const state = await workflowApi.getWorkflowState(instanceId);
            setWorkflowState(state);
            showNotification?.('Workflow paused', 'info');
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

    // Create the instance
    const { instance_id } = await workflowApi.startWorkflow(
        workflowId,
        initialInput,
        deps.conversationId
    );

    // Create handlers
    const handlers = createWorkflowHandlers(instance_id, deps);

    // Start running and process events
    const events = workflowApi.runWorkflow(instance_id);

    // Process in background
    (async () => {
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
    })();

    return { instanceId: instance_id, handlers };
}
