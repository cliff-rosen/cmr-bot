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
            {/* Header with tabs */}
            <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
                <div className="max-w-7xl mx-auto px-6">
                    <div className="flex items-center justify-between py-4">
                        <div>
                            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                                Tools
                            </h1>
                            <p className="text-sm text-gray-500 dark:text-gray-400">
                                Test and debug backend services
                            </p>
                        </div>
                    </div>

                    {/* Tab navigation */}
                    <div className="flex gap-1 -mb-px">
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

            {/* Content area */}
            <div className="flex-1 overflow-y-auto bg-gray-50 dark:bg-gray-900">
                <div className="max-w-7xl mx-auto p-6">
                    {renderContent()}
                </div>
            </div>
        </div>
    );
}
