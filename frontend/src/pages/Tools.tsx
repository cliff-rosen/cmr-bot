import { useState } from 'react';
import {
    BeakerIcon,
    EnvelopeIcon,
    DocumentMagnifyingGlassIcon,
    CpuChipIcon
} from '@heroicons/react/24/solid';
import PubMedSearch from '../components/tools/PubMedSearch';
import GmailSearch from '../components/tools/GmailSearch';
import LLMTesting from '../components/tools/LLMTesting';

type ToolTab = 'llm-testing' | 'pubmed' | 'gmail';

interface TabConfig {
    id: ToolTab;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    description: string;
}

const TABS: TabConfig[] = [
    {
        id: 'llm-testing',
        label: 'LLM Testing',
        icon: CpuChipIcon,
        description: 'Test and compare different LLMs'
    },
    {
        id: 'pubmed',
        label: 'PubMed',
        icon: BeakerIcon,
        description: 'Search medical literature'
    },
    {
        id: 'gmail',
        label: 'Gmail',
        icon: EnvelopeIcon,
        description: 'Search email messages'
    },
];

export default function Tools() {
    const [activeTab, setActiveTab] = useState<ToolTab>('llm-testing');

    const renderContent = () => {
        switch (activeTab) {
            case 'llm-testing':
                return <LLMTesting />;
            case 'pubmed':
                return <PubMedSearch />;
            case 'gmail':
                return <GmailSearch />;
            default:
                return null;
        }
    };

    return (
        <div className="h-full flex flex-col">
            {/* Header with tabs on same row */}
            <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
                <div className="px-6 flex items-center gap-6">
                    {/* Title */}
                    <div className="py-3 flex-shrink-0">
                        <h1 className="text-xl font-bold text-gray-900 dark:text-white">
                            Tools
                        </h1>
                    </div>

                    {/* Tab navigation */}
                    <div className="flex gap-1 flex-1">
                        {TABS.map((tab) => {
                            const Icon = tab.icon;
                            const isActive = activeTab === tab.id;
                            return (
                                <button
                                    key={tab.id}
                                    onClick={() => setActiveTab(tab.id)}
                                    className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                                        isActive
                                            ? 'border-blue-500 text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20'
                                            : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
                                    }`}
                                >
                                    <Icon className={`h-5 w-5 ${isActive ? 'text-blue-500' : ''}`} />
                                    {tab.label}
                                </button>
                            );
                        })}
                    </div>
                </div>
            </div>

            {/* Content area - full width, no max-width constraint */}
            <div className="flex-1 overflow-hidden bg-gray-50 dark:bg-gray-900">
                <div className="h-full p-6">
                    {renderContent()}
                </div>
            </div>
        </div>
    );
}
