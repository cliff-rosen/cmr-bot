import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { WrenchScrewdriverIcon, ChevronDownIcon, ChevronUpIcon } from '@heroicons/react/24/solid';
import { ToolCall } from '../../types/chat';

interface MarkdownRendererProps {
    content: string;
    className?: string;
    compact?: boolean;
    toolHistory?: ToolCall[];
    onToolClick?: (toolCall: ToolCall, index: number) => void;
}

// Regex to match [[tool:N]] markers
const TOOL_MARKER_REGEX = /\[\[tool:(\d+)\]\]/g;

interface InlineToolChipProps {
    toolCall: ToolCall;
    index: number;
    onClick?: (toolCall: ToolCall, index: number) => void;
}

function InlineToolChip({ toolCall, index, onClick }: InlineToolChipProps) {
    const [expanded, setExpanded] = useState(false);
    const displayName = toolCall.tool_name.replace(/_/g, ' ');

    const handleClick = () => {
        if (onClick) {
            onClick(toolCall, index);
        } else {
            setExpanded(!expanded);
        }
    };

    return (
        <span className="relative inline-flex items-center align-middle mx-1">
            <button
                onClick={handleClick}
                className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-800/50 transition-colors"
            >
                <WrenchScrewdriverIcon className="h-3 w-3" />
                {displayName}
                {!onClick && (
                    expanded ? (
                        <ChevronUpIcon className="h-3 w-3" />
                    ) : (
                        <ChevronDownIcon className="h-3 w-3" />
                    )
                )}
            </button>
            {!onClick && expanded && (
                <div className="absolute z-20 mt-1 top-full left-0 w-80 max-h-60 overflow-auto p-3 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 text-left">
                    <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Input:</div>
                    <pre className="text-xs bg-gray-50 dark:bg-gray-900 p-2 rounded mb-2 overflow-x-auto whitespace-pre-wrap text-gray-800 dark:text-gray-200">
                        {JSON.stringify(toolCall.input, null, 2)}
                    </pre>
                    <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Output:</div>
                    <pre className="text-xs bg-gray-50 dark:bg-gray-900 p-2 rounded overflow-x-auto whitespace-pre-wrap max-h-32 text-gray-800 dark:text-gray-200">
                        {typeof toolCall.output === 'string'
                            ? toolCall.output.slice(0, 500) + (toolCall.output.length > 500 ? '...' : '')
                            : JSON.stringify(toolCall.output, null, 2).slice(0, 500)
                        }
                    </pre>
                </div>
            )}
        </span>
    );
}

// Common markdown components configuration
const getMarkdownComponents = (compact: boolean) => ({
    // Text elements
    p: ({ children }: { children?: React.ReactNode }) => (
        <p className={`text-gray-900 dark:text-gray-100 ${compact ? 'mb-1' : 'mb-4'}`}>
            {children}
        </p>
    ),
    h1: ({ children }: { children?: React.ReactNode }) => (
        <h1 className={`text-2xl font-bold text-gray-900 dark:text-gray-100 ${compact ? 'mb-2' : 'mb-4'}`}>
            {children}
        </h1>
    ),
    h2: ({ children }: { children?: React.ReactNode }) => (
        <h2 className={`text-xl font-bold text-gray-900 dark:text-gray-100 ${compact ? 'mb-2' : 'mb-3'}`}>
            {children}
        </h2>
    ),
    h3: ({ children }: { children?: React.ReactNode }) => (
        <h3 className={`text-lg font-bold text-gray-900 dark:text-gray-100 ${compact ? 'mb-1' : 'mb-2'}`}>
            {children}
        </h3>
    ),

    // Lists
    ul: ({ children }: { children?: React.ReactNode }) => (
        <ul className={`list-disc list-inside space-y-1 text-gray-900 dark:text-gray-100 ${compact ? 'mb-2' : 'mb-4'}`}>
            {children}
        </ul>
    ),
    ol: ({ children }: { children?: React.ReactNode }) => (
        <ol className={`list-decimal list-inside space-y-1 text-gray-900 dark:text-gray-100 ${compact ? 'mb-2' : 'mb-4'}`}>
            {children}
        </ol>
    ),
    li: ({ children }: { children?: React.ReactNode }) => (
        <li className="text-gray-900 dark:text-gray-100">
            {children}
        </li>
    ),

    // Table elements
    table: ({ children }: { children?: React.ReactNode }) => (
        <table className="min-w-full border-collapse border border-gray-200 dark:border-gray-700">
            {children}
        </table>
    ),
    thead: ({ children }: { children?: React.ReactNode }) => (
        <thead className="bg-gray-50 dark:bg-gray-800">
            {children}
        </thead>
    ),
    tbody: ({ children }: { children?: React.ReactNode }) => (
        <tbody className="bg-white dark:bg-gray-900">
            {children}
        </tbody>
    ),
    tr: ({ children }: { children?: React.ReactNode }) => (
        <tr className="border-b border-gray-200 dark:border-gray-700">
            {children}
        </tr>
    ),
    th: ({ children }: { children?: React.ReactNode }) => (
        <th className="px-4 py-2 text-left text-sm font-semibold text-gray-900 dark:text-gray-100 border-r border-gray-200 dark:border-gray-700 last:border-r-0">
            {children}
        </th>
    ),
    td: ({ children }: { children?: React.ReactNode }) => (
        <td className="px-4 py-2 text-sm text-gray-900 dark:text-gray-100 border-r border-gray-200 dark:border-gray-700 last:border-r-0">
            {children}
        </td>
    ),

    // Code elements
    code: ({ children }: { children?: React.ReactNode }) => (
        <code className="bg-gray-100 dark:bg-gray-800 rounded px-1 py-0.5 text-sm font-mono text-gray-900 dark:text-gray-100">
            {children}
        </code>
    ),
    pre: ({ children }: { children?: React.ReactNode }) => (
        <pre className="bg-gray-100 dark:bg-gray-800 rounded p-4 overflow-x-auto text-gray-900 dark:text-gray-100">
            {children}
        </pre>
    ),

    // Other elements
    blockquote: ({ children }: { children?: React.ReactNode }) => (
        <blockquote className="border-l-4 border-gray-200 dark:border-gray-700 pl-4 italic text-gray-600 dark:text-gray-300">
            {children}
        </blockquote>
    ),
    a: (props: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
        <a
            {...props}
            className="text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
            target="_blank"
            rel="noopener noreferrer"
        />
    ),
    img: (props: React.ImgHTMLAttributes<HTMLImageElement>) => (
        <img
            {...props}
            className="max-w-full h-auto rounded-lg"
            alt={props.alt || ''}
        />
    ),
});

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({
    content,
    className = '',
    compact = false,
    toolHistory,
    onToolClick
}) => {
    const components = getMarkdownComponents(compact);

    // If no tool history or no markers, render normally
    if (!toolHistory || !TOOL_MARKER_REGEX.test(content)) {
        return (
            <div className={`prose prose-gray dark:prose-invert max-w-none ${className}`}>
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
                    {content}
                </ReactMarkdown>
            </div>
        );
    }

    // Split content by tool markers and render with inline chips
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match;

    // Reset regex state
    const regex = new RegExp(TOOL_MARKER_REGEX.source, 'g');

    while ((match = regex.exec(content)) !== null) {
        // Add text before the marker
        if (match.index > lastIndex) {
            const textBefore = content.slice(lastIndex, match.index);
            parts.push(
                <ReactMarkdown
                    key={`text-${lastIndex}`}
                    remarkPlugins={[remarkGfm]}
                    components={components}
                >
                    {textBefore}
                </ReactMarkdown>
            );
        }

        // Add the tool chip
        const toolIndex = parseInt(match[1], 10);
        const toolCall = toolHistory[toolIndex];
        if (toolCall) {
            parts.push(
                <InlineToolChip
                    key={`tool-${toolIndex}`}
                    toolCall={toolCall}
                    index={toolIndex}
                    onClick={onToolClick}
                />
            );
        }

        lastIndex = match.index + match[0].length;
    }

    // Add remaining text after last marker
    if (lastIndex < content.length) {
        const textAfter = content.slice(lastIndex);
        parts.push(
            <ReactMarkdown
                key={`text-${lastIndex}`}
                remarkPlugins={[remarkGfm]}
                components={components}
            >
                {textAfter}
            </ReactMarkdown>
        );
    }

    return (
        <div className={`prose prose-gray dark:prose-invert max-w-none ${className}`}>
            {parts}
        </div>
    );
};

export default MarkdownRenderer; 