/**
 * Workflow API - Step execution via dedicated agent with SSE streaming
 */

import { api } from './index';
import { makeStreamRequest } from './streamUtils';

export interface StepInputSource {
    content: string;
    data?: any;  // Structured data when source produced 'data' content_type
}

export interface StepExecutionRequest {
    step_number: number;
    description: string;
    input_data: Record<string, StepInputSource>;  // Named inputs with content and optional structured data
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
    data?: any;  // Structured data when content_type is 'data'
    tool_calls: ToolCallRecord[];
    error: string | null;
}

export interface ToolProgressUpdate {
    stage: string;
    message: string;
    data?: Record<string, any>;
    progress?: number;  // 0-1 progress indicator
}

export interface StepStatusUpdate {
    status: 'thinking' | 'tool_start' | 'tool_progress' | 'tool_complete' | 'complete' | 'error';
    message: string;
    tool_name?: string;
    tool_input?: Record<string, any>;
    tool_output?: string;
    tool_progress?: ToolProgressUpdate;  // Present on 'tool_progress' status
    result?: StepExecutionResult;
}

export interface ToolInfo {
    name: string;
    description: string;
    category: string;
}

export const workflowApi = {
    /**
     * Get all available tools from the backend.
     */
    async getTools(): Promise<ToolInfo[]> {
        const response = await api.get('/workflow/tools');
        return response.data;
    },
    /**
     * Execute a workflow step with SSE streaming for status updates.
     * Yields status updates as they arrive, final update contains result.
     */
    async *executeStepStreaming(request: StepExecutionRequest): AsyncGenerator<StepStatusUpdate> {
        try {
            const rawStream = makeStreamRequest('/workflow/execute-step', request, 'POST');

            // Buffer for incomplete SSE messages (chunks may not align with message boundaries)
            let buffer = '';

            for await (const update of rawStream) {
                buffer += update.data;

                // SSE messages are separated by double newlines
                const messages = buffer.split('\n\n');

                // Keep the last incomplete message in the buffer
                buffer = messages.pop() || '';

                for (const message of messages) {
                    if (!message.trim()) continue;

                    // Parse SSE data lines
                    for (const line of message.split('\n')) {
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
            }

            // Process any remaining data in buffer
            if (buffer.trim()) {
                for (const line of buffer.split('\n')) {
                    if (line.startsWith('data: ')) {
                        const jsonStr = line.slice(6);
                        try {
                            const data: StepStatusUpdate = JSON.parse(jsonStr);
                            yield data;
                        } catch (e) {
                            console.error('Failed to parse remaining stream data:', jsonStr, e);
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
