/**
 * Workflow API - Step execution via dedicated agent
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface StepExecutionRequest {
    step_number: number;
    description: string;
    input_data: string;
    output_format: string;
    available_tools: string[];
}

export interface StepExecutionResponse {
    success: boolean;
    output: string;
    content_type: 'document' | 'data' | 'code';
    error: string | null;
}

export const workflowApi = {
    /**
     * Execute a single workflow step using the dedicated step agent.
     */
    async executeStep(request: StepExecutionRequest): Promise<StepExecutionResponse> {
        const response = await fetch(`${API_BASE}/workflow/execute-step`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(request),
        });

        if (!response.ok) {
            const error = await response.text();
            throw new Error(`Failed to execute step: ${error}`);
        }

        return response.json();
    }
};
