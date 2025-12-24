import { useState, useEffect, useMemo } from 'react';
import {
    PlayIcon,
    PlusIcon,
    TrashIcon,
    CheckCircleIcon,
    XCircleIcon,
    QuestionMarkCircleIcon,
    ArrowPathIcon,
    BeakerIcon,
    DocumentTextIcon,
    LightBulbIcon,
    CalculatorIcon,
    ExclamationTriangleIcon,
    ExclamationCircleIcon,
    ChevronDownIcon,
    ChevronRightIcon,
    ClockIcon,
    XMarkIcon,
    InformationCircleIcon,
    CpuChipIcon,
    BoltIcon,
    CheckIcon
} from '@heroicons/react/24/solid';
import { toolsApi, LLMModelInfo } from '../../lib/api/toolsApi';

// ============================================================================
// Types
// ============================================================================

type AnswerType = 'exact' | 'contains' | 'one_of' | 'free_response';

interface TestQuestion {
    id: string;
    question: string;
    expectedAnswer?: string;
    expectedAnswers?: string[];
    answerType: AnswerType;
}

interface TestTemplate {
    id: string;
    name: string;
    description: string;
    icon: React.ComponentType<{ className?: string }>;
    category: 'comprehension' | 'reasoning' | 'knowledge' | 'custom';
    context: string;
    questions: TestQuestion[];
}

interface TestResult {
    questionId: string;
    response: string;
    isCorrect: boolean | null;
    expectedAnswer?: string;
}

interface ModelResult {
    modelId: string;
    modelName: string;
    provider: string;
    results: TestResult[];
    rawResponse: string;
    totalCorrect: number;
    totalQuestions: number;
    latencyMs: number;
    status: 'pending' | 'running' | 'complete' | 'error';
    error?: string;
}

// ============================================================================
// Test Templates
// ============================================================================

const TEST_TEMPLATES: TestTemplate[] = [
    {
        id: 'reading-comprehension-1',
        name: 'Reading Comprehension: Dr. Chen',
        description: 'Tests literal comprehension, temporal reasoning, and nuanced understanding',
        icon: DocumentTextIcon,
        category: 'comprehension',
        context: `Read the following paragraph carefully, then answer the 5 questions below. For each question, respond with exactly one word: Yes, No, or Unclear (if the paragraph doesn't provide enough information to determine the answer).

Paragraph:

Dr. Sarah Chen joined Meridian Pharmaceuticals in 2019 as Head of Research. Under her leadership, the company's R&D budget increased by 40%, and three new drug candidates entered clinical trials. In 2022, she was promoted to Chief Scientific Officer. The company's stock price doubled during her tenure, though industry analysts attributed much of this growth to favorable market conditions. Dr. Chen holds patents for two cancer treatment compounds and previously worked at Stanford Medical Center.`,
        questions: [
            { id: 'q1', question: 'Did Dr. Chen work at Meridian Pharmaceuticals before 2019?', expectedAnswer: 'No', answerType: 'exact' },
            { id: 'q2', question: 'Is Dr. Chen currently the Chief Scientific Officer?', expectedAnswer: 'Unclear', answerType: 'exact' },
            { id: 'q3', question: 'Did the R&D budget increase after Dr. Chen joined?', expectedAnswer: 'Yes', answerType: 'exact' },
            { id: 'q4', question: 'Was the stock price growth entirely due to Dr. Chen\'s leadership?', expectedAnswer: 'No', answerType: 'exact' },
            { id: 'q5', question: 'Does Dr. Chen have experience with cancer research?', expectedAnswer: 'Yes', answerType: 'exact' }
        ]
    },
    {
        id: 'logical-reasoning-1',
        name: 'Logical Reasoning: Deduction',
        description: 'Tests provability, contradiction, and underdetermination',
        icon: LightBulbIcon,
        category: 'reasoning',
        context: `Use ONLY the following rules. Do not use outside knowledge.

RULES:
1. All dogs are mammals.
2. All mammals are warm-blooded.
3. Fido is a dog.
4. Tweety is a bird.

Answer each question with exactly one word: Yes, No, or Unknown.
- "Yes" = provable from the rules
- "No" = contradicted by the rules
- "Unknown" = neither provable nor contradicted`,
        questions: [
            { id: 'q1', question: 'Is Fido a mammal?', expectedAnswer: 'Yes', answerType: 'exact' },
            { id: 'q2', question: 'Is Fido warm-blooded?', expectedAnswer: 'Yes', answerType: 'exact' },
            { id: 'q3', question: 'Is Tweety warm-blooded?', expectedAnswer: 'Unknown', answerType: 'exact' },
            { id: 'q4', question: 'Is Tweety a mammal?', expectedAnswer: 'Unknown', answerType: 'exact' },
            { id: 'q5', question: 'Can something be a dog and not be warm-blooded?', expectedAnswer: 'No', answerType: 'exact' }
        ]
    },
    {
        id: 'math-word-problems',
        name: 'Math Word Problems',
        description: 'Tests arithmetic and problem-solving',
        icon: CalculatorIcon,
        category: 'reasoning',
        context: `Solve each problem. Give only the numerical answer (no units or explanation).`,
        questions: [
            { id: 'q1', question: 'A store sells apples for $2 each and oranges for $3 each. If you buy 4 apples and 3 oranges, how much do you spend in total?', expectedAnswer: '17', answerType: 'exact' },
            { id: 'q2', question: 'A train travels at 60 mph. How many miles does it travel in 2.5 hours?', expectedAnswer: '150', answerType: 'exact' },
            { id: 'q3', question: 'If 15% of a number is 45, what is the number?', expectedAnswer: '300', answerType: 'exact' },
            { id: 'q4', question: 'A rectangle has a perimeter of 24 cm and a width of 4 cm. What is its length in cm?', expectedAnswer: '8', answerType: 'exact' }
        ]
    }
];

// ============================================================================
// Provider Config
// ============================================================================

const PROVIDER_CONFIG: Record<string, { displayName: string; color: string; bgClass: string }> = {
    anthropic: { displayName: 'Anthropic', color: 'orange', bgClass: 'bg-orange-500' },
    openai: { displayName: 'OpenAI', color: 'green', bgClass: 'bg-emerald-500' },
    google: { displayName: 'Google', color: 'blue', bgClass: 'bg-blue-500' },
};

// ============================================================================
// Main Component
// ============================================================================

export default function LLMTesting() {
    // UI State
    const [templatesExpanded, setTemplatesExpanded] = useState(true);
    const [selectedResultId, setSelectedResultId] = useState<string | null>(null);
    const [showModelBrowser, setShowModelBrowser] = useState(false);

    // Test State
    const [selectedTemplate, setSelectedTemplate] = useState<TestTemplate | null>(null);
    const [selectedModels, setSelectedModels] = useState<Set<string>>(new Set());
    const [isRunning, setIsRunning] = useState(false);
    const [results, setResults] = useState<ModelResult[]>([]);

    // Model State
    const [availableModels, setAvailableModels] = useState<LLMModelInfo[]>([]);
    const [configuredProviders, setConfiguredProviders] = useState<string[]>([]);
    const [isLoadingModels, setIsLoadingModels] = useState(true);
    const [modelLoadError, setModelLoadError] = useState<string | null>(null);

    // Custom Test State
    const [customContext, setCustomContext] = useState('');
    const [customQuestions, setCustomQuestions] = useState<TestQuestion[]>([]);
    const [showCustomForm, setShowCustomForm] = useState(false);

    // Fetch models on mount
    useEffect(() => {
        const fetchModels = async () => {
            try {
                setIsLoadingModels(true);
                const response = await toolsApi.listLLMModels();
                setAvailableModels(response.models);
                setConfiguredProviders(response.configured_providers);
                const firstConfigured = response.models.find(m => m.is_configured);
                if (firstConfigured) {
                    setSelectedModels(new Set([firstConfigured.id]));
                }
            } catch (error) {
                setModelLoadError(error instanceof Error ? error.message : 'Failed to load models');
            } finally {
                setIsLoadingModels(false);
            }
        };
        fetchModels();
    }, []);

    // Group models by provider
    const modelsByProvider = useMemo(() => {
        const grouped: Record<string, LLMModelInfo[]> = {};
        for (const model of availableModels) {
            if (!grouped[model.provider]) grouped[model.provider] = [];
            grouped[model.provider].push(model);
        }
        return grouped;
    }, [availableModels]);

    // Auto-select first result when results come in
    useEffect(() => {
        if (results.length > 0 && !selectedResultId) {
            setSelectedResultId(results[0].modelId);
        }
    }, [results, selectedResultId]);

    const handleSelectTemplate = (template: TestTemplate) => {
        setSelectedTemplate(template);
        setResults([]);
        setSelectedResultId(null);
        setShowCustomForm(false);
        setTemplatesExpanded(false);
    };

    const handleToggleModel = (modelId: string) => {
        const newSelected = new Set(selectedModels);
        if (newSelected.has(modelId)) {
            newSelected.delete(modelId);
        } else {
            newSelected.add(modelId);
        }
        setSelectedModels(newSelected);
    };

    const handleRunTest = async () => {
        if (!selectedTemplate || selectedModels.size === 0) return;

        setIsRunning(true);
        setResults([]);
        setSelectedResultId(null);

        const initialResults: ModelResult[] = Array.from(selectedModels).map(modelId => {
            const model = availableModels.find(m => m.id === modelId);
            return {
                modelId,
                modelName: model?.display_name || modelId,
                provider: model?.provider || 'unknown',
                results: [],
                rawResponse: '',
                totalCorrect: 0,
                totalQuestions: selectedTemplate.questions.length,
                latencyMs: 0,
                status: 'pending'
            };
        });
        setResults(initialResults);
        setSelectedResultId(initialResults[0]?.modelId || null);

        for (const modelId of selectedModels) {
            const modelConfig = availableModels.find(m => m.id === modelId);
            if (!modelConfig?.is_configured) continue;

            setResults(prev => prev.map(r =>
                r.modelId === modelId ? { ...r, status: 'running' } : r
            ));
            setSelectedResultId(modelId);

            try {
                const data = await toolsApi.testLLM({
                    model: modelId,
                    context: selectedTemplate.context,
                    questions: selectedTemplate.questions.map(q => q.question)
                });

                if (!data.success) throw new Error(data.error || 'LLM test failed');

                const modelResults: TestResult[] = selectedTemplate.questions.map((question, index) => {
                    const llmResponse = data.parsed_answers[index]?.trim() || '';
                    let isCorrect: boolean | null = null;
                    if (question.answerType === 'exact' && question.expectedAnswer) {
                        isCorrect = llmResponse.toLowerCase() === question.expectedAnswer.toLowerCase();
                    } else if (question.answerType === 'contains' && question.expectedAnswer) {
                        isCorrect = llmResponse.toLowerCase().includes(question.expectedAnswer.toLowerCase());
                    } else if (question.answerType === 'one_of' && question.expectedAnswers) {
                        isCorrect = question.expectedAnswers.some(a => llmResponse.toLowerCase() === a.toLowerCase());
                    }
                    return { questionId: question.id, response: llmResponse, isCorrect, expectedAnswer: question.expectedAnswer };
                });

                const totalCorrect = modelResults.filter(r => r.isCorrect === true).length;

                setResults(prev => prev.map(r =>
                    r.modelId === modelId ? {
                        ...r, results: modelResults, rawResponse: data.raw_response,
                        totalCorrect, latencyMs: data.latency_ms, status: 'complete'
                    } : r
                ));
            } catch (error) {
                setResults(prev => prev.map(r =>
                    r.modelId === modelId ? { ...r, status: 'error', error: error instanceof Error ? error.message : 'Unknown error' } : r
                ));
            }
        }
        setIsRunning(false);
    };

    const addCustomQuestion = () => {
        setCustomQuestions([...customQuestions, { id: `custom-${Date.now()}`, question: '', expectedAnswer: '', answerType: 'exact' }]);
    };

    const handleCreateCustomTest = () => {
        if (!customContext.trim() || customQuestions.length === 0) return;
        const customTemplate: TestTemplate = {
            id: `custom-${Date.now()}`, name: 'Custom Test', description: 'User-defined test',
            icon: BeakerIcon, category: 'custom', context: customContext,
            questions: customQuestions.filter(q => q.question.trim())
        };
        setSelectedTemplate(customTemplate);
        setShowCustomForm(false);
        setResults([]);
        setTemplatesExpanded(false);
    };

    const selectedResult = results.find(r => r.modelId === selectedResultId);

    return (
        <div className="h-full flex flex-col">
            {/* Model Browser Modal */}
            {showModelBrowser && (
                <ModelBrowserModal
                    models={availableModels}
                    configuredProviders={configuredProviders}
                    onClose={() => setShowModelBrowser(false)}
                />
            )}

            {/* Collapsible Templates Section */}
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow mb-4">
                <button
                    onClick={() => setTemplatesExpanded(!templatesExpanded)}
                    className="w-full p-4 flex items-center justify-between text-left"
                >
                    <div className="flex items-center gap-2">
                        {templatesExpanded ? <ChevronDownIcon className="h-5 w-5 text-gray-500" /> : <ChevronRightIcon className="h-5 w-5 text-gray-500" />}
                        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Test Templates</h2>
                        {selectedTemplate && !templatesExpanded && (
                            <span className="ml-2 px-2 py-0.5 text-xs rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">
                                {selectedTemplate.name}
                            </span>
                        )}
                    </div>
                </button>

                {templatesExpanded && (
                    <div className="px-4 pb-4">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                            {TEST_TEMPLATES.map((template) => {
                                const Icon = template.icon;
                                const isSelected = selectedTemplate?.id === template.id;
                                return (
                                    <button
                                        key={template.id}
                                        onClick={() => handleSelectTemplate(template)}
                                        className={`text-left p-3 rounded-lg border-2 transition-all ${
                                            isSelected ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' : 'border-gray-200 dark:border-gray-700 hover:border-gray-300'
                                        }`}
                                    >
                                        <div className="flex items-center gap-2 mb-1">
                                            <Icon className={`h-4 w-4 ${isSelected ? 'text-blue-600' : 'text-gray-500'}`} />
                                            <span className="font-medium text-sm text-gray-900 dark:text-white truncate">{template.name}</span>
                                        </div>
                                        <p className="text-xs text-gray-500 line-clamp-1">{template.description}</p>
                                    </button>
                                );
                            })}
                            <button
                                onClick={() => { setShowCustomForm(true); setSelectedTemplate(null); setTemplatesExpanded(false); }}
                                className="text-left p-3 rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600 hover:border-gray-400"
                            >
                                <div className="flex items-center gap-2 mb-1">
                                    <PlusIcon className="h-4 w-4 text-gray-500" />
                                    <span className="font-medium text-sm text-gray-900 dark:text-white">Custom Test</span>
                                </div>
                                <p className="text-xs text-gray-500">Define your own</p>
                            </button>
                        </div>
                    </div>
                )}
            </div>

            {/* Main Content Area: Two Columns */}
            <div className="flex-1 flex gap-4 min-h-0">
                {/* Left Column: Test Setup - fixed max width since it's just readable text */}
                <div className="w-[700px] flex-shrink-0 flex flex-col min-w-0 overflow-hidden">
                    <div className="flex-1 bg-white dark:bg-gray-800 rounded-lg shadow overflow-auto">
                        {showCustomForm ? (
                            <CustomTestForm
                                context={customContext}
                                questions={customQuestions}
                                onContextChange={setCustomContext}
                                onAddQuestion={addCustomQuestion}
                                onUpdateQuestion={(id, updates) => setCustomQuestions(prev => prev.map(q => q.id === id ? { ...q, ...updates } : q))}
                                onRemoveQuestion={(id) => setCustomQuestions(prev => prev.filter(q => q.id !== id))}
                                onCreate={handleCreateCustomTest}
                                onCancel={() => setShowCustomForm(false)}
                            />
                        ) : selectedTemplate ? (
                            <TestSetupPanel
                                template={selectedTemplate}
                                modelsByProvider={modelsByProvider}
                                configuredProviders={configuredProviders}
                                selectedModels={selectedModels}
                                isLoadingModels={isLoadingModels}
                                modelLoadError={modelLoadError}
                                isRunning={isRunning}
                                onToggleModel={handleToggleModel}
                                onRunTest={handleRunTest}
                                onOpenModelBrowser={() => setShowModelBrowser(true)}
                            />
                        ) : (
                            <div className="flex items-center justify-center h-full text-gray-400 dark:text-gray-500">
                                <p>Select a test template to begin</p>
                            </div>
                        )}
                    </div>
                </div>

                {/* Right Column: Results - expands to fill remaining space */}
                <div className="flex-1 min-w-[400px] flex flex-col bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
                    <div className="p-3 border-b border-gray-200 dark:border-gray-700">
                        <h3 className="font-semibold text-gray-900 dark:text-white">Results</h3>
                    </div>

                    {results.length === 0 ? (
                        <div className="flex-1 flex items-center justify-center text-gray-400 dark:text-gray-500 text-sm">
                            <p>Run a test to see results</p>
                        </div>
                    ) : (
                        <>
                            {/* Model Tabs */}
                            <div className="flex border-b border-gray-200 dark:border-gray-700 overflow-x-auto">
                                {results.map((r) => {
                                    const providerConfig = PROVIDER_CONFIG[r.provider] || { bgClass: 'bg-gray-500' };
                                    const isActive = r.modelId === selectedResultId;
                                    const scorePercent = r.totalQuestions > 0 ? Math.round((r.totalCorrect / r.totalQuestions) * 100) : 0;

                                    return (
                                        <button
                                            key={r.modelId}
                                            onClick={() => setSelectedResultId(r.modelId)}
                                            className={`flex-shrink-0 px-3 py-2 text-xs font-medium border-b-2 transition-colors ${
                                                isActive
                                                    ? 'border-blue-500 text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20'
                                                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700'
                                            }`}
                                        >
                                            <div className="flex items-center gap-2">
                                                <span className={`w-2 h-2 rounded-full ${providerConfig.bgClass}`} />
                                                <span className="truncate max-w-[100px]">{r.modelName}</span>
                                                {r.status === 'running' && <ArrowPathIcon className="h-3 w-3 animate-spin text-blue-500" />}
                                                {r.status === 'complete' && (
                                                    <span className={`${scorePercent >= 80 ? 'text-green-600' : scorePercent >= 50 ? 'text-yellow-600' : 'text-red-600'}`}>
                                                        {scorePercent}%
                                                    </span>
                                                )}
                                                {r.status === 'error' && <ExclamationCircleIcon className="h-3 w-3 text-red-500" />}
                                            </div>
                                        </button>
                                    );
                                })}
                            </div>

                            {/* Selected Result Detail */}
                            <div className="flex-1 overflow-auto">
                                {selectedResult && (
                                    <ResultDetail result={selectedResult} questions={selectedTemplate?.questions || []} />
                                )}
                            </div>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}

// ============================================================================
// Test Setup Panel
// ============================================================================

function TestSetupPanel({
    template, modelsByProvider, configuredProviders, selectedModels,
    isLoadingModels, modelLoadError, isRunning, onToggleModel, onRunTest, onOpenModelBrowser
}: {
    template: TestTemplate;
    modelsByProvider: Record<string, LLMModelInfo[]>;
    configuredProviders: string[];
    selectedModels: Set<string>;
    isLoadingModels: boolean;
    modelLoadError: string | null;
    isRunning: boolean;
    onToggleModel: (id: string) => void;
    onRunTest: () => void;
    onOpenModelBrowser: () => void;
}) {
    return (
        <div className="p-4 space-y-4">
            {/* Header with Run Button */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{template.name}</h2>
                    <p className="text-sm text-gray-500">{template.questions.length} questions</p>
                </div>
                <button
                    onClick={onRunTest}
                    disabled={isRunning || selectedModels.size === 0}
                    className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm font-medium"
                >
                    {isRunning ? <><ArrowPathIcon className="h-4 w-4 animate-spin" />Running...</> : <><PlayIcon className="h-4 w-4" />Run Test</>}
                </button>
            </div>

            {/* Model Selection */}
            <div>
                <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">Select Models</h3>
                    <button
                        onClick={onOpenModelBrowser}
                        className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1"
                    >
                        <InformationCircleIcon className="h-3.5 w-3.5" />
                        Browse All Models
                    </button>
                </div>
                {isLoadingModels ? (
                    <div className="flex items-center gap-2 text-gray-500 text-sm"><ArrowPathIcon className="h-4 w-4 animate-spin" />Loading...</div>
                ) : modelLoadError ? (
                    <div className="flex items-center gap-2 text-red-500 text-sm"><ExclamationCircleIcon className="h-4 w-4" />{modelLoadError}</div>
                ) : (
                    <div className="space-y-3">
                        {Object.entries(modelsByProvider).map(([provider, models]) => {
                            const config = PROVIDER_CONFIG[provider] || { displayName: provider, bgClass: 'bg-gray-500' };
                            const isConfigured = configuredProviders.includes(provider);
                            return (
                                <div key={provider}>
                                    <div className="flex items-center gap-2 mb-1">
                                        <span className={`w-2 h-2 rounded-full ${config.bgClass}`} />
                                        <span className="text-xs font-semibold text-gray-500 uppercase">{config.displayName}</span>
                                        {!isConfigured && (
                                            <span className="text-xs text-yellow-600 dark:text-yellow-400 flex items-center gap-1">
                                                <ExclamationTriangleIcon className="h-3 w-3" />Not configured
                                            </span>
                                        )}
                                    </div>
                                    <div className="flex flex-wrap gap-1">
                                        {models.map((model) => {
                                            const isSelected = selectedModels.has(model.id);
                                            return (
                                                <button
                                                    key={model.id}
                                                    onClick={() => model.is_configured && onToggleModel(model.id)}
                                                    disabled={!model.is_configured}
                                                    className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                                                        !model.is_configured ? 'bg-gray-100 dark:bg-gray-700 text-gray-400 cursor-not-allowed'
                                                        : isSelected ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 ring-1 ring-blue-500'
                                                        : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200'
                                                    }`}
                                                >
                                                    {model.display_name}
                                                </button>
                                            );
                                        })}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* Context */}
            <div>
                <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Context</h3>
                <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap max-h-84 overflow-auto">
                    {template.context}
                </div>
            </div>

            {/* Questions */}
            <div>
                <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Questions</h3>
                <div className="space-y-1">
                    {template.questions.map((q, i) => (
                        <div key={q.id} className="flex gap-2 p-2 bg-gray-50 dark:bg-gray-700/50 rounded text-sm">
                            <span className="text-gray-500 font-medium">{i + 1}.</span>
                            <div className="flex-1">
                                <p className="text-gray-900 dark:text-white">{q.question}</p>
                                {q.expectedAnswer && <p className="text-xs text-gray-500 mt-0.5">Expected: <span className="font-mono">{q.expectedAnswer}</span></p>}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}

// ============================================================================
// Result Detail
// ============================================================================

function ResultDetail({ result, questions }: { result: ModelResult; questions: TestQuestion[] }) {
    const [showRaw, setShowRaw] = useState(false);
    const scorePercent = result.totalQuestions > 0 ? Math.round((result.totalCorrect / result.totalQuestions) * 100) : 0;

    return (
        <div className="p-3 space-y-3">
            {/* Stats Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <span className={`text-2xl font-bold ${scorePercent >= 80 ? 'text-green-600' : scorePercent >= 50 ? 'text-yellow-600' : 'text-red-600'}`}>
                        {result.status === 'complete' ? `${scorePercent}%` : result.status === 'running' ? '...' : '--'}
                    </span>
                    <span className="text-sm text-gray-500">{result.totalCorrect}/{result.totalQuestions} correct</span>
                </div>
                {result.status === 'complete' && (
                    <div className="flex items-center gap-1 text-xs text-gray-500">
                        <ClockIcon className="h-3 w-3" />
                        {result.latencyMs}ms
                    </div>
                )}
            </div>

            {result.status === 'error' && (
                <div className="p-2 bg-red-50 dark:bg-red-900/20 rounded text-sm text-red-600 dark:text-red-400">
                    {result.error}
                </div>
            )}

            {result.status === 'running' && (
                <div className="flex items-center gap-2 text-sm text-blue-600">
                    <ArrowPathIcon className="h-4 w-4 animate-spin" />
                    Running...
                </div>
            )}

            {result.status === 'complete' && (
                <>
                    {/* Toggle Raw */}
                    <button onClick={() => setShowRaw(!showRaw)} className="text-xs text-blue-600 hover:underline">
                        {showRaw ? 'Hide' : 'Show'} raw response
                    </button>

                    {showRaw && (
                        <pre className="text-xs p-2 bg-gray-100 dark:bg-gray-900 rounded overflow-auto max-h-32 text-gray-700 dark:text-gray-300">
                            {result.rawResponse || '(empty)'}
                        </pre>
                    )}

                    {/* Question Results */}
                    <div className="space-y-2">
                        {result.results.map((r, i) => {
                            const q = questions.find(q => q.id === r.questionId);
                            return (
                                <div key={r.questionId} className="flex gap-2 text-sm">
                                    <div className="flex-shrink-0 mt-0.5">
                                        {r.isCorrect === true && <CheckCircleIcon className="h-4 w-4 text-green-500" />}
                                        {r.isCorrect === false && <XCircleIcon className="h-4 w-4 text-red-500" />}
                                        {r.isCorrect === null && <QuestionMarkCircleIcon className="h-4 w-4 text-gray-400" />}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-gray-700 dark:text-gray-300"><span className="font-medium">Q{i + 1}:</span> {q?.question}</p>
                                        <div className="flex flex-wrap gap-x-3 text-xs mt-0.5">
                                            <span className="text-gray-500">Got: <span className="font-mono text-gray-900 dark:text-white">{r.response || '(empty)'}</span></span>
                                            {r.isCorrect === false && r.expectedAnswer && (
                                                <span className="text-red-500">Expected: <span className="font-mono">{r.expectedAnswer}</span></span>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </>
            )}
        </div>
    );
}

// ============================================================================
// Custom Test Form
// ============================================================================

function CustomTestForm({
    context, questions, onContextChange, onAddQuestion, onUpdateQuestion, onRemoveQuestion, onCreate, onCancel
}: {
    context: string;
    questions: TestQuestion[];
    onContextChange: (v: string) => void;
    onAddQuestion: () => void;
    onUpdateQuestion: (id: string, updates: Partial<TestQuestion>) => void;
    onRemoveQuestion: (id: string) => void;
    onCreate: () => void;
    onCancel: () => void;
}) {
    return (
        <div className="p-4 space-y-4">
            <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Create Custom Test</h2>
                <button onClick={onCancel} className="text-sm text-gray-500 hover:text-gray-700">Cancel</button>
            </div>

            <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Context / Instructions</label>
                <textarea
                    value={context}
                    onChange={(e) => onContextChange(e.target.value)}
                    rows={4}
                    placeholder="Enter the context..."
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
                />
            </div>

            <div>
                <div className="flex items-center justify-between mb-2">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Questions</label>
                    <button onClick={onAddQuestion} className="text-sm text-blue-600 flex items-center gap-1"><PlusIcon className="h-4 w-4" />Add</button>
                </div>
                <div className="space-y-2">
                    {questions.map((q, i) => (
                        <div key={q.id} className="flex gap-2 items-start p-2 bg-gray-50 dark:bg-gray-700/50 rounded">
                            <span className="text-sm text-gray-500 mt-2">{i + 1}.</span>
                            <div className="flex-1 space-y-1">
                                <input
                                    type="text" value={q.question} onChange={(e) => onUpdateQuestion(q.id, { question: e.target.value })}
                                    placeholder="Question..." className="w-full px-2 py-1 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                                />
                                <input
                                    type="text" value={q.expectedAnswer || ''} onChange={(e) => onUpdateQuestion(q.id, { expectedAnswer: e.target.value })}
                                    placeholder="Expected answer (optional)" className="w-full px-2 py-1 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                                />
                            </div>
                            <button onClick={() => onRemoveQuestion(q.id)} className="p-1 text-gray-400 hover:text-red-500"><TrashIcon className="h-4 w-4" /></button>
                        </div>
                    ))}
                    {questions.length === 0 && <p className="text-sm text-gray-400 text-center py-2">No questions yet</p>}
                </div>
            </div>

            <button
                onClick={onCreate}
                disabled={!context.trim() || questions.length === 0}
                className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm font-medium"
            >
                Create Test
            </button>
        </div>
    );
}

// ============================================================================
// Model Browser Modal
// ============================================================================

function ModelBrowserModal({
    models,
    configuredProviders,
    onClose
}: {
    models: LLMModelInfo[];
    configuredProviders: string[];
    onClose: () => void;
}) {
    const [selectedProvider, setSelectedProvider] = useState<string | null>(null);

    // Group models by provider
    const modelsByProvider = useMemo(() => {
        const grouped: Record<string, LLMModelInfo[]> = {};
        for (const model of models) {
            if (!grouped[model.provider]) grouped[model.provider] = [];
            grouped[model.provider].push(model);
        }
        return grouped;
    }, [models]);

    const providers = Object.keys(modelsByProvider);
    const displayedModels = selectedProvider
        ? modelsByProvider[selectedProvider] || []
        : models;

    const formatNumber = (n: number) => {
        if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
        if (n >= 1000) return `${(n / 1000).toFixed(0)}K`;
        return n.toString();
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-8" onClick={onClose}>
            <div
                className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-[1200px] h-[90vh] flex flex-col"
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
                    <div className="flex items-center gap-3">
                        <CpuChipIcon className="h-6 w-6 text-blue-600" />
                        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Model Browser</h2>
                        <span className="text-sm text-gray-500">{models.length} models</span>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
                    >
                        <XMarkIcon className="h-5 w-5" />
                    </button>
                </div>

                {/* Provider Filter */}
                <div className="flex gap-2 p-4 border-b border-gray-200 dark:border-gray-700">
                    <button
                        onClick={() => setSelectedProvider(null)}
                        className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                            selectedProvider === null
                                ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                                : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200'
                        }`}
                    >
                        All
                    </button>
                    {providers.map(provider => {
                        const config = PROVIDER_CONFIG[provider] || { displayName: provider, bgClass: 'bg-gray-500' };
                        const isConfigured = configuredProviders.includes(provider);
                        return (
                            <button
                                key={provider}
                                onClick={() => setSelectedProvider(provider)}
                                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 ${
                                    selectedProvider === provider
                                        ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                                        : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200'
                                }`}
                            >
                                <span className={`w-2 h-2 rounded-full ${config.bgClass}`} />
                                {config.displayName}
                                {isConfigured && <CheckIcon className="h-3 w-3 text-green-500" />}
                            </button>
                        );
                    })}
                </div>

                {/* Model List */}
                <div className="flex-1 overflow-auto p-4">
                    <div className="grid gap-3">
                        {displayedModels.map(model => {
                            const providerConfig = PROVIDER_CONFIG[model.provider] || { displayName: model.provider, bgClass: 'bg-gray-500' };
                            const isConfigured = model.is_configured;

                            return (
                                <div
                                    key={model.id}
                                    className={`p-4 rounded-lg border ${
                                        isConfigured
                                            ? 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800'
                                            : 'border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 opacity-60'
                                    }`}
                                >
                                    <div className="flex items-start justify-between">
                                        <div className="flex-1">
                                            <div className="flex items-center gap-2 mb-1">
                                                <span className={`w-2 h-2 rounded-full ${providerConfig.bgClass}`} />
                                                <h3 className="font-semibold text-gray-900 dark:text-white">
                                                    {model.display_name}
                                                </h3>
                                                {model.is_reasoning && (
                                                    <span className="px-1.5 py-0.5 text-xs rounded bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300">
                                                        Reasoning
                                                    </span>
                                                )}
                                                {!isConfigured && (
                                                    <span className="px-1.5 py-0.5 text-xs rounded bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300">
                                                        Not Configured
                                                    </span>
                                                )}
                                            </div>
                                            <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">
                                                {model.notes || 'No description available'}
                                            </p>
                                            <div className="flex flex-wrap gap-4 text-xs">
                                                <div className="flex items-center gap-1.5">
                                                    <span className="text-gray-400">Context:</span>
                                                    <span className="font-medium text-gray-700 dark:text-gray-300">
                                                        {formatNumber(model.context_window)} tokens
                                                    </span>
                                                </div>
                                                <div className="flex items-center gap-1.5">
                                                    <span className="text-gray-400">Provider:</span>
                                                    <span className="font-medium text-gray-700 dark:text-gray-300">
                                                        {providerConfig.displayName}
                                                    </span>
                                                </div>
                                                <div className="flex items-center gap-1.5">
                                                    <span className="text-gray-400">Model ID:</span>
                                                    <code className="font-mono text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded">
                                                        {model.id}
                                                    </code>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>

                {/* Footer */}
                <div className="p-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                    <div className="flex items-center justify-between text-xs text-gray-500">
                        <div className="flex items-center gap-4">
                            <span className="flex items-center gap-1">
                                <CheckIcon className="h-3 w-3 text-green-500" />
                                Configured providers have API keys set
                            </span>
                            <span className="flex items-center gap-1">
                                <BoltIcon className="h-3 w-3 text-purple-500" />
                                Reasoning models use internal thinking
                            </span>
                        </div>
                        <button
                            onClick={onClose}
                            className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 font-medium"
                        >
                            Close
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
