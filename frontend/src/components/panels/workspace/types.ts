/**
 * Shared types and configuration for workspace components
 */

import {
    DocumentTextIcon, TableCellsIcon, CodeBracketIcon,
    ClipboardDocumentListIcon, PlayIcon, ArrowPathIcon, CheckCircleIcon,
    CpuChipIcon, PencilSquareIcon, Squares2X2Icon, BeakerIcon, StarIcon
} from '@heroicons/react/24/solid';
import { ComponentType } from 'react';

export interface PayloadTypeConfig {
    icon: ComponentType<{ className?: string }>;
    color: string;
    bg: string;
    border: string;
    label: string;
    editable: boolean;
}

export const payloadTypeConfig: Record<string, PayloadTypeConfig> = {
    draft: {
        icon: DocumentTextIcon,
        color: 'text-blue-500',
        bg: 'bg-blue-50 dark:bg-blue-900/20',
        border: 'border-blue-200 dark:border-blue-800',
        label: 'Draft',
        editable: true
    },
    summary: {
        icon: ClipboardDocumentListIcon,
        color: 'text-green-500',
        bg: 'bg-green-50 dark:bg-green-900/20',
        border: 'border-green-200 dark:border-green-800',
        label: 'Summary',
        editable: false
    },
    data: {
        icon: TableCellsIcon,
        color: 'text-purple-500',
        bg: 'bg-purple-50 dark:bg-purple-900/20',
        border: 'border-purple-200 dark:border-purple-800',
        label: 'Data',
        editable: false
    },
    code: {
        icon: CodeBracketIcon,
        color: 'text-orange-500',
        bg: 'bg-orange-50 dark:bg-orange-900/20',
        border: 'border-orange-200 dark:border-orange-800',
        label: 'Code',
        editable: true
    },
    plan: {
        icon: PlayIcon,
        color: 'text-indigo-500',
        bg: 'bg-indigo-50 dark:bg-indigo-900/20',
        border: 'border-indigo-200 dark:border-indigo-800',
        label: 'Workflow Plan',
        editable: false
    },
    wip: {
        icon: ArrowPathIcon,
        color: 'text-amber-500',
        bg: 'bg-amber-50 dark:bg-amber-900/20',
        border: 'border-amber-200 dark:border-amber-800',
        label: 'Work in Progress',
        editable: true
    },
    final: {
        icon: CheckCircleIcon,
        color: 'text-green-500',
        bg: 'bg-green-50 dark:bg-green-900/20',
        border: 'border-green-200 dark:border-green-800',
        label: 'Workflow Complete',
        editable: false
    },
    agent_create: {
        icon: CpuChipIcon,
        color: 'text-cyan-500',
        bg: 'bg-cyan-50 dark:bg-cyan-900/20',
        border: 'border-cyan-200 dark:border-cyan-800',
        label: 'Create Agent',
        editable: false
    },
    agent_update: {
        icon: PencilSquareIcon,
        color: 'text-amber-500',
        bg: 'bg-amber-50 dark:bg-amber-900/20',
        border: 'border-amber-200 dark:border-amber-800',
        label: 'Update Agent',
        editable: false
    },
    table: {
        icon: Squares2X2Icon,
        color: 'text-teal-500',
        bg: 'bg-teal-50 dark:bg-teal-900/20',
        border: 'border-teal-200 dark:border-teal-800',
        label: 'Table',
        editable: false
    },
    research: {
        icon: BeakerIcon,
        color: 'text-purple-500',
        bg: 'bg-purple-50 dark:bg-purple-900/20',
        border: 'border-purple-200 dark:border-purple-800',
        label: 'Research',
        editable: false
    },
    research_result: {
        icon: BeakerIcon,
        color: 'text-purple-500',
        bg: 'bg-purple-50 dark:bg-purple-900/20',
        border: 'border-purple-200 dark:border-purple-800',
        label: 'Research Results',
        editable: false
    },
    review_collection: {
        icon: StarIcon,
        color: 'text-yellow-500',
        bg: 'bg-yellow-50 dark:bg-yellow-900/20',
        border: 'border-yellow-200 dark:border-yellow-800',
        label: 'Review Collection',
        editable: false
    }
};
