/**
 * Workflow API - Step execution via dedicated agent with SSE streaming
 */

import { makeStreamRequest } from './streamUtils';

export interface StepExecutionRequest {
    step_number: number;
    description: string;
    input_data: string;
    output_format: string;
    available_tools: string[];
}

export interface ToolCallRecord {
    tool_name: string;
    input: Record<string, any>;
    output: string;
}

export interface StepExecutionResult {
    success: boolean;
    output: string;
    content_type: 'document' | 'data' | 'code';
    tool_calls: ToolCallRecord[];
    error: string | null;
}

export interface StepStatusUpdate {
    status: 'thinking' | 'tool_start' | 'tool_complete' | 'complete' | 'error';
    message: string;
    tool_name?: string;
    tool_input?: Record<string, any>;
    tool_output?: string;
    result?: StepExecutionResult;
}

export const workflowApi = {
    /**
     * Execute a workflow step with SSE streaming for status updates.
     * Yields status updates as they arrive, final update contains result.
     */
    async *executeStepStreaming(request: StepExecutionRequest): AsyncGenerator<StepStatusUpdate> {
        try {
            const rawStream = makeStreamRequest('/workflow/execute-step', request, 'POST');

            for await (const update of rawStream) {
                const lines = update.data.split('\n');
                for (const line of lines) {
                    if (!line.trim()) continue;

                    if (line.startsWith('data: ')) {
                        const jsonStr = line.slice(6);
                        try {
                            const data: StepStatusUpdate = JSON.parse(jsonStr);
                            yield data;
                        } catch (e) {
                            console.error('Failed to parse stream data:', jsonStr, e);
                        }
                    }
                }
            }
        } catch (error) {
            yield {
                status: 'error',
                message: `Stream error: ${error instanceof Error ? error.message : String(error)}`
            };
        }
    }
};
