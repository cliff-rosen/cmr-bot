/**
 * Workflow Engine API Client
 *
 * API calls for workflow operations.
 */

import settings from '../../config/settings';
import {
    WorkflowSummary,
    WorkflowTemplate,
    WorkflowInstanceState,
    WorkflowEvent,
    CheckpointAction,
} from '../../types/workflow';

const WORKFLOWS_API = `${settings.apiUrl}/api/workflows`;

// Helper to get auth headers
function getAuthHeaders(): Record<string, string> {
    const token = localStorage.getItem('authToken');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

/**
 * List all available workflow templates.
 */
export async function listWorkflows(): Promise<{
    workflows: WorkflowSummary[];
    categories: string[];
}> {
    const response = await fetch(`${WORKFLOWS_API}/list`, {
        headers: getAuthHeaders(),
    });

    if (!response.ok) {
        throw new Error(`Failed to list workflows: ${response.statusText}`);
    }

    return response.json();
}

/**
 * Get details of a specific workflow template.
 */
export async function getWorkflowTemplate(workflowId: string): Promise<WorkflowTemplate> {
    const response = await fetch(`${WORKFLOWS_API}/templates/${workflowId}`, {
        headers: getAuthHeaders(),
    });

    if (!response.ok) {
        throw new Error(`Failed to get workflow template: ${response.statusText}`);
    }

    return response.json();
}

/**
 * Start a new workflow instance.
 */
export async function startWorkflow(
    workflowId: string,
    initialInput: Record<string, any>,
    conversationId?: number
): Promise<{ instance_id: string; workflow_id: string; status: string }> {
    const response = await fetch(`${WORKFLOWS_API}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({
            workflow_id: workflowId,
            initial_input: initialInput,
            conversation_id: conversationId,
        }),
    });

    if (!response.ok) {
        throw new Error(`Failed to start workflow: ${response.statusText}`);
    }

    return response.json();
}

/**
 * Run a workflow instance and stream events.
 * Returns an async generator and an abort function.
 */
export function runWorkflow(instanceId: string, signal?: AbortSignal): AsyncGenerator<WorkflowEvent> {
    return createEventStream(`${WORKFLOWS_API}/instances/${instanceId}/run`, 'POST', undefined, signal);
}

/**
 * Helper to create an SSE event stream with abort support.
 */
async function* createEventStream(
    url: string,
    method: string,
    body?: Record<string, any>,
    signal?: AbortSignal
): AsyncGenerator<WorkflowEvent> {
    const headers: Record<string, string> = {
        'Accept': 'text/event-stream',
        ...getAuthHeaders(),
    };

    if (body) {
        headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(url, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
        signal,
    });

    if (!response.ok) {
        throw new Error(`Request failed: ${response.statusText}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
        throw new Error('No response body');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const event = JSON.parse(line.slice(6)) as WorkflowEvent;
                        yield event;
                    } catch (e) {
                        console.error('Failed to parse workflow event:', e);
                    }
                }
            }
        }
    } finally {
        // Ensure reader is released
        reader.releaseLock();
    }
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
    return createEventStream(
        `${WORKFLOWS_API}/instances/${instanceId}/resume`,
        'POST',
        { action, user_data: userData },
        signal
    );
}

/**
 * Get the current state of a workflow instance.
 */
export async function getWorkflowState(instanceId: string): Promise<WorkflowInstanceState> {
    const response = await fetch(`${WORKFLOWS_API}/instances/${instanceId}`, {
        headers: getAuthHeaders(),
    });

    if (!response.ok) {
        throw new Error(`Failed to get workflow state: ${response.statusText}`);
    }

    return response.json();
}

/**
 * Cancel a running workflow.
 */
export async function cancelWorkflow(instanceId: string): Promise<void> {
    const response = await fetch(`${WORKFLOWS_API}/instances/${instanceId}/cancel`, {
        method: 'POST',
        headers: getAuthHeaders(),
    });

    if (!response.ok) {
        throw new Error(`Failed to cancel workflow: ${response.statusText}`);
    }
}

/**
 * Pause a running workflow.
 */
export async function pauseWorkflow(instanceId: string): Promise<void> {
    const response = await fetch(`${WORKFLOWS_API}/instances/${instanceId}/pause`, {
        method: 'POST',
        headers: getAuthHeaders(),
    });

    if (!response.ok) {
        throw new Error(`Failed to pause workflow: ${response.statusText}`);
    }
}
