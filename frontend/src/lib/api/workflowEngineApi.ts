/**
 * Workflow Engine API Client
 *
 * API calls for workflow operations.
 */

import { api } from './index';
import { makeStreamRequest } from './streamUtils';
import {
    WorkflowSummary,
    WorkflowTemplate,
    WorkflowInstanceState,
    WorkflowEvent,
    CheckpointAction,
} from '../../types/workflow';

/**
 * Helper to parse SSE events from a raw stream.
 * Uses makeStreamRequest and parses the SSE data lines.
 */
async function* parseSSEStream<T>(
    endpoint: string,
    params: Record<string, any>,
    signal?: AbortSignal
): AsyncGenerator<T> {
    const rawStream = makeStreamRequest(endpoint, params, 'POST', signal);

    // Buffer for accumulating partial SSE data lines across chunks
    let buffer = '';

    for await (const update of rawStream) {
        buffer += update.data;

        // Process complete lines from the buffer
        let newlineIndex: number;
        while ((newlineIndex = buffer.indexOf('\n')) !== -1) {
            const line = buffer.slice(0, newlineIndex);
            buffer = buffer.slice(newlineIndex + 1);

            // Skip empty lines and non-data lines
            if (!line.trim() || !line.startsWith('data: ')) {
                continue;
            }

            const jsonStr = line.slice(6); // Remove "data: " prefix

            // Skip ping/keepalive messages
            if (jsonStr === '' || jsonStr === 'ping') {
                continue;
            }

            try {
                const data = JSON.parse(jsonStr) as T;
                yield data;
            } catch (e) {
                // JSON parse failed - put it back and wait for more data
                buffer = line + '\n' + buffer;
                break;
            }
        }
    }

    // Process any remaining buffered data
    if (buffer.trim() && buffer.startsWith('data: ')) {
        const jsonStr = buffer.slice(6);
        try {
            const data = JSON.parse(jsonStr) as T;
            yield data;
        } catch (e) {
            console.error('Failed to parse final workflow event:', jsonStr.slice(0, 200));
        }
    }
}

/**
 * List all available workflow templates.
 */
export async function listWorkflows(): Promise<{
    workflows: WorkflowSummary[];
    categories: string[];
}> {
    const response = await api.get('/api/workflows/list');
    return response.data;
}

/**
 * Get details of a specific workflow template.
 */
export async function getWorkflowTemplate(workflowId: string): Promise<WorkflowTemplate> {
    const response = await api.get(`/api/workflows/templates/${workflowId}`);
    return response.data;
}

/**
 * Start a new workflow instance.
 *
 * Can accept either:
 * - workflowId: Reference to a registered template
 * - workflowGraph: Inline graph definition (for agent-designed workflows)
 */
export async function startWorkflow(
    workflowId: string | null,
    initialInput: Record<string, any>,
    conversationId?: number,
    workflowGraph?: Record<string, any>
): Promise<{ instance_id: string; workflow_id: string; status: string }> {
    const response = await api.post('/api/workflows/start', {
        workflow_id: workflowId,
        workflow_graph: workflowGraph,
        initial_input: initialInput,
        conversation_id: conversationId,
    });
    return response.data;
}

/**
 * Run a workflow instance and stream events.
 */
export function runWorkflow(instanceId: string, signal?: AbortSignal): AsyncGenerator<WorkflowEvent> {
    return parseSSEStream<WorkflowEvent>(
        `/api/workflows/instances/${instanceId}/run`,
        {}, // No body params needed
        signal
    );
}

/**
 * Resume a workflow from a checkpoint.
 */
export function resumeWorkflow(
    instanceId: string,
    action: CheckpointAction,
    userData?: Record<string, any>,
    signal?: AbortSignal
): AsyncGenerator<WorkflowEvent> {
    return parseSSEStream<WorkflowEvent>(
        `/api/workflows/instances/${instanceId}/resume`,
        { action, user_data: userData },
        signal
    );
}

/**
 * Get the current state of a workflow instance.
 */
export async function getWorkflowState(instanceId: string): Promise<WorkflowInstanceState> {
    const response = await api.get(`/api/workflows/instances/${instanceId}`);
    return response.data;
}

/**
 * Cancel a running workflow.
 */
export async function cancelWorkflow(instanceId: string): Promise<void> {
    await api.post(`/api/workflows/instances/${instanceId}/cancel`);
}

/**
 * Pause a running workflow.
 */
export async function pauseWorkflow(instanceId: string): Promise<void> {
    await api.post(`/api/workflows/instances/${instanceId}/pause`);
}
