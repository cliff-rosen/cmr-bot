/**
 * Workspace View Registries
 *
 * Maps payload types and workflow IDs to their view components.
 * Add new entries here when creating new payload types or custom workflow views.
 */

import { PayloadViewRegistry, WorkflowViewRegistry, PayloadViewProps, WorkflowViewProps } from './workspaceMode';

// Import payload view components
import StandardPayloadView from '../../components/panels/workspace/StandardPayloadView';
import AgentPayloadView from '../../components/panels/workspace/AgentPayloadView';
import TablePayloadView from '../../components/panels/workspace/TablePayloadView';
import ResearchWorkflowView from '../../components/panels/workspace/ResearchWorkflowView';
import ResearchResultView from '../../components/panels/workspace/ResearchResultView';
import ReviewCollectionView from '../../components/panels/workspace/ReviewCollectionView';
import EntityVerificationView from '../../components/panels/workspace/EntityVerificationView';
import WorkflowGraphView from '../../components/panels/workspace/WorkflowGraphView';

// Import workflow view components
import WorkflowExecutionView from '../../components/panels/workspace/WorkflowExecutionView';
import VendorFinderWorkflowView from '../../components/panels/workspace/VendorFinderWorkflowView';

// =============================================================================
// Payload View Registry
// =============================================================================

/**
 * Maps payload.type to the component that renders it.
 * If a type is not found, StandardPayloadView is used as fallback.
 */
export const payloadViewRegistry: PayloadViewRegistry = {
    // Agent creation/update
    'agent_create': AgentPayloadView as React.ComponentType<PayloadViewProps>,
    'agent_update': AgentPayloadView as React.ComponentType<PayloadViewProps>,

    // Table display (from pubmed_search, pubmed_smart_search)
    'table': TablePayloadView as React.ComponentType<PayloadViewProps>,

    // LLM-orchestrated research workflow (from manage_research_workflow tool)
    'research': ResearchWorkflowView as React.ComponentType<PayloadViewProps>,

    // Research results (from deep_research tool)
    'research_result': ResearchResultView as React.ComponentType<PayloadViewProps>,

    // Review collection results (from collect_reviews tool)
    'review_collection': ReviewCollectionView as React.ComponentType<PayloadViewProps>,

    // Entity verification results (from verify_entity tool)
    'entity_verification': EntityVerificationView as React.ComponentType<PayloadViewProps>,

    // Workflow graph design (from design_workflow tool)
    'workflow_graph': WorkflowGraphView as React.ComponentType<PayloadViewProps>,

    // Standard types use StandardPayloadView (draft, summary, data, code)
    // These don't need explicit entries - they fall through to default
};

/**
 * Get the view component for a payload type.
 * Returns StandardPayloadView if no specific view is registered.
 */
export function getPayloadView(payloadType: string): React.ComponentType<PayloadViewProps> {
    return payloadViewRegistry[payloadType] || (StandardPayloadView as React.ComponentType<PayloadViewProps>);
}

// =============================================================================
// Workflow View Registry
// =============================================================================

/**
 * Maps workflow ID to a custom view component.
 * If a workflow ID is not found, WorkflowExecutionView is used as fallback.
 *
 * Add entries here for workflows that need custom UX beyond the generic view.
 */
export const workflowViewRegistry: WorkflowViewRegistry = {
    // Custom workflow views
    'vendor_finder': VendorFinderWorkflowView,
};

/**
 * Get the view component for a workflow ID.
 * Returns WorkflowExecutionView if no custom view is registered.
 */
export function getWorkflowView(workflowId: string): React.ComponentType<WorkflowViewProps> {
    return workflowViewRegistry[workflowId] || (WorkflowExecutionView as React.ComponentType<WorkflowViewProps>);
}
