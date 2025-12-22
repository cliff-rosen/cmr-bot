import { useState } from 'react';
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
    CalculatorIcon
} from '@heroicons/react/24/solid';
import { toolsApi } from '../../lib/api/toolsApi';

// ============================================================================
// Types
// ============================================================================

type AnswerType = 'exact' | 'contains' | 'one_of' | 'free_response';

interface TestQuestion {
    id: string;
    question: string;
    expectedAnswer?: string;
    expectedAnswers?: string[];  // For one_of type
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
    isCorrect: boolean | null;  // null for free_response
    expectedAnswer?: string;
}

interface ModelResult {
    modelId: string;
    modelName: string;
    results: TestResult[];
    rawResponse: string;  // Full LLM response
    totalCorrect: number;
    totalQuestions: number;
    latencyMs: number;  // Single request latency
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
            {
                id: 'q1',
                question: 'Did Dr. Chen work at Meridian Pharmaceuticals before 2019?',
                expectedAnswer: 'No',
                answerType: 'exact'
            },
            {
                id: 'q2',
                question: 'Is Dr. Chen currently the Chief Scientific Officer?',
                expectedAnswer: 'Unclear',
                answerType: 'exact'
            },
            {
                id: 'q3',
                question: 'Did the R&D budget increase after Dr. Chen joined?',
                expectedAnswer: 'Yes',
                answerType: 'exact'
            },
            {
                id: 'q4',
                question: 'Was the stock price growth entirely due to Dr. Chen\'s leadership?',
                expectedAnswer: 'No',
                answerType: 'exact'
            },
            {
                id: 'q5',
                question: 'Does Dr. Chen have experience with cancer research?',
                expectedAnswer: 'Yes',
                answerType: 'exact'
            }
        ]
    },
    {
        id: 'logical-reasoning-1',
        name: 'Logical Reasoning: Conditional Statements',
        description: 'Tests understanding of if-then logic and contrapositive reasoning',
        icon: LightBulbIcon,
        category: 'reasoning',
        context: `Answer each question with exactly one word: Yes, No, or Unclear.

Given the following rules:
1. If it rains, the ground gets wet.
2. If the ground is wet, the flowers bloom.
3. If John goes outside without an umbrella when it rains, he gets wet.
4. John never takes his umbrella when the sun is shining.`,
        questions: [
            {
                id: 'q1',
                question: 'If it rains, will the flowers bloom?',
                expectedAnswer: 'Yes',
                answerType: 'exact'
            },
            {
                id: 'q2',
                question: 'If the flowers are not blooming, did it rain?',
                expectedAnswer: 'No',
                answerType: 'exact'
            },
            {
                id: 'q3',
                question: 'If John is wet, did it definitely rain?',
                expectedAnswer: 'Unclear',
                answerType: 'exact'
            },
            {
                id: 'q4',
                question: 'If the sun is shining and John goes outside, will he get wet from rain?',
                expectedAnswer: 'No',
                answerType: 'exact'
            }
        ]
    },
    {
        id: 'math-word-problems',
        name: 'Math Word Problems',
        description: 'Tests arithmetic and problem-solving with real-world scenarios',
        icon: CalculatorIcon,
        category: 'reasoning',
        context: `Solve each problem. Give only the numerical answer (no units or explanation).`,
        questions: [
            {
                id: 'q1',
                question: 'A store sells apples for $2 each and oranges for $3 each. If you buy 4 apples and 3 oranges, how much do you spend in total?',
                expectedAnswer: '17',
                answerType: 'exact'
            },
            {
                id: 'q2',
                question: 'A train travels at 60 mph. How many miles does it travel in 2.5 hours?',
                expectedAnswer: '150',
                answerType: 'exact'
            },
            {
                id: 'q3',
                question: 'If 15% of a number is 45, what is the number?',
                expectedAnswer: '300',
                answerType: 'exact'
            },
            {
                id: 'q4',
                question: 'A rectangle has a perimeter of 24 cm and a width of 4 cm. What is its length in cm?',
                expectedAnswer: '8',
                answerType: 'exact'
            }
        ]
    }
];

// ============================================================================
// Available Models (expandable)
// ============================================================================

interface ModelConfig {
    id: string;
    name: string;
    provider: string;
    available: boolean;
}

const AVAILABLE_MODELS: ModelConfig[] = [
    { id: 'claude-sonnet-4', name: 'Claude Sonnet 4', provider: 'Anthropic', available: true },
    { id: 'claude-haiku-3.5', name: 'Claude Haiku 3.5', provider: 'Anthropic', available: false },
    { id: 'gpt-4o', name: 'GPT-4o', provider: 'OpenAI', available: false },
    { id: 'gpt-4o-mini', name: 'GPT-4o Mini', provider: 'OpenAI', available: false },
    { id: 'gemini-pro', name: 'Gemini Pro', provider: 'Google', available: false },
];

// ============================================================================
// Component
// ============================================================================

export default function LLMTesting() {
    const [selectedTemplate, setSelectedTemplate] = useState<TestTemplate | null>(null);
    const [selectedModels, setSelectedModels] = useState<Set<string>>(new Set(['claude-sonnet-4']));
    const [isRunning, setIsRunning] = useState(false);
    const [results, setResults] = useState<ModelResult[]>([]);

    // Custom test state
    const [customContext, setCustomContext] = useState('');
    const [customQuestions, setCustomQuestions] = useState<TestQuestion[]>([]);
    const [showCustomForm, setShowCustomForm] = useState(false);

    const handleSelectTemplate = (template: TestTemplate) => {
        setSelectedTemplate(template);
        setResults([]);
        setShowCustomForm(false);
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

        // Initialize results for each model
        const initialResults: ModelResult[] = Array.from(selectedModels).map(modelId => ({
            modelId,
            modelName: AVAILABLE_MODELS.find(m => m.id === modelId)?.name || modelId,
            results: [],
            rawResponse: '',
            totalCorrect: 0,
            totalQuestions: selectedTemplate.questions.length,
            latencyMs: 0,
            status: 'pending'
        }));
        setResults(initialResults);

        // Run tests for each model - ALL QUESTIONS SENT AT ONCE
        for (const modelId of selectedModels) {
            const modelConfig = AVAILABLE_MODELS.find(m => m.id === modelId);
            if (!modelConfig?.available) continue;

            // Update status to running
            setResults(prev => prev.map(r =>
                r.modelId === modelId ? { ...r, status: 'running' } : r
            ));

            try {
                // Send ALL questions in a single request
                const data = await toolsApi.testLLM({
                    model: modelId,
                    context: selectedTemplate.context,
                    questions: selectedTemplate.questions.map(q => q.question)
                });

                if (!data.success) {
                    throw new Error(data.error || 'LLM test failed');
                }

                // Match parsed answers to questions
                const modelResults: TestResult[] = selectedTemplate.questions.map((question, index) => {
                    const llmResponse = data.parsed_answers[index]?.trim() || '';

                    // Check correctness
                    let isCorrect: boolean | null = null;
                    if (question.answerType === 'exact' && question.expectedAnswer) {
                        isCorrect = llmResponse.toLowerCase() === question.expectedAnswer.toLowerCase();
                    } else if (question.answerType === 'contains' && question.expectedAnswer) {
                        isCorrect = llmResponse.toLowerCase().includes(question.expectedAnswer.toLowerCase());
                    } else if (question.answerType === 'one_of' && question.expectedAnswers) {
                        isCorrect = question.expectedAnswers.some(a =>
                            llmResponse.toLowerCase() === a.toLowerCase()
                        );
                    }

                    return {
                        questionId: question.id,
                        response: llmResponse,
                        isCorrect,
                        expectedAnswer: question.expectedAnswer
                    };
                });

                const totalCorrect = modelResults.filter(r => r.isCorrect === true).length;

                // Update with complete results
                setResults(prev => prev.map(r =>
                    r.modelId === modelId ? {
                        ...r,
                        results: modelResults,
                        rawResponse: data.raw_response,
                        totalCorrect,
                        latencyMs: data.latency_ms,
                        status: 'complete'
                    } : r
                ));

            } catch (error) {
                setResults(prev => prev.map(r =>
                    r.modelId === modelId ? {
                        ...r,
                        status: 'error',
                        error: error instanceof Error ? error.message : 'Unknown error'
                    } : r
                ));
            }
        }

        setIsRunning(false);
    };

    const addCustomQuestion = () => {
        setCustomQuestions([
            ...customQuestions,
            {
                id: `custom-${Date.now()}`,
                question: '',
                expectedAnswer: '',
                answerType: 'exact'
            }
        ]);
    };

    const updateCustomQuestion = (id: string, updates: Partial<TestQuestion>) => {
        setCustomQuestions(prev =>
            prev.map(q => q.id === id ? { ...q, ...updates } : q)
        );
    };

    const removeCustomQuestion = (id: string) => {
        setCustomQuestions(prev => prev.filter(q => q.id !== id));
    };

    const handleCreateCustomTest = () => {
        if (!customContext.trim() || customQuestions.length === 0) return;

        const customTemplate: TestTemplate = {
            id: `custom-${Date.now()}`,
            name: 'Custom Test',
            description: 'User-defined test',
            icon: BeakerIcon,
            category: 'custom',
            context: customContext,
            questions: customQuestions.filter(q => q.question.trim())
        };

        setSelectedTemplate(customTemplate);
        setShowCustomForm(false);
        setResults([]);
    };

    return (
        <div className="space-y-6">
            {/* Test Templates */}
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
                <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                    <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                        Test Templates
                    </h2>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                        Select a predefined test or create your own
                    </p>
                </div>

                <div className="p-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {TEST_TEMPLATES.map((template) => {
                            const Icon = template.icon;
                            const isSelected = selectedTemplate?.id === template.id;
                            return (
                                <button
                                    key={template.id}
                                    onClick={() => handleSelectTemplate(template)}
                                    className={`text-left p-4 rounded-lg border-2 transition-all ${
                                        isSelected
                                            ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                                            : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                                    }`}
                                >
                                    <div className="flex items-start gap-3">
                                        <div className={`p-2 rounded-lg ${
                                            isSelected
                                                ? 'bg-blue-100 dark:bg-blue-800'
                                                : 'bg-gray-100 dark:bg-gray-700'
                                        }`}>
                                            <Icon className={`h-5 w-5 ${
                                                isSelected
                                                    ? 'text-blue-600 dark:text-blue-400'
                                                    : 'text-gray-500 dark:text-gray-400'
                                            }`} />
                                        </div>
                                        <div>
                                            <h3 className="font-medium text-gray-900 dark:text-white">
                                                {template.name}
                                            </h3>
                                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                                                {template.description}
                                            </p>
                                            <span className="inline-block mt-2 px-2 py-0.5 text-xs rounded-full bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400">
                                                {template.questions.length} questions
                                            </span>
                                        </div>
                                    </div>
                                </button>
                            );
                        })}

                        {/* Create Custom */}
                        <button
                            onClick={() => {
                                setShowCustomForm(true);
                                setSelectedTemplate(null);
                            }}
                            className={`text-left p-4 rounded-lg border-2 border-dashed transition-all ${
                                showCustomForm
                                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                                    : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'
                            }`}
                        >
                            <div className="flex items-start gap-3">
                                <div className={`p-2 rounded-lg ${
                                    showCustomForm
                                        ? 'bg-blue-100 dark:bg-blue-800'
                                        : 'bg-gray-100 dark:bg-gray-700'
                                }`}>
                                    <PlusIcon className={`h-5 w-5 ${
                                        showCustomForm
                                            ? 'text-blue-600 dark:text-blue-400'
                                            : 'text-gray-500 dark:text-gray-400'
                                    }`} />
                                </div>
                                <div>
                                    <h3 className="font-medium text-gray-900 dark:text-white">
                                        Create Custom Test
                                    </h3>
                                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                                        Define your own context and questions
                                    </p>
                                </div>
                            </div>
                        </button>
                    </div>
                </div>
            </div>

            {/* Custom Test Form */}
            {showCustomForm && (
                <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
                    <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                            Create Custom Test
                        </h2>
                    </div>

                    <div className="p-6 space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                Context / Instructions
                            </label>
                            <textarea
                                value={customContext}
                                onChange={(e) => setCustomContext(e.target.value)}
                                rows={6}
                                placeholder="Enter the context, paragraph, or instructions the LLM should use..."
                                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                            />
                        </div>

                        <div>
                            <div className="flex items-center justify-between mb-2">
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                                    Questions
                                </label>
                                <button
                                    onClick={addCustomQuestion}
                                    className="flex items-center gap-1 text-sm text-blue-600 dark:text-blue-400 hover:text-blue-700"
                                >
                                    <PlusIcon className="h-4 w-4" />
                                    Add Question
                                </button>
                            </div>

                            <div className="space-y-3">
                                {customQuestions.map((q, index) => (
                                    <div key={q.id} className="flex gap-3 items-start p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                                        <span className="text-sm font-medium text-gray-500 mt-2">
                                            {index + 1}.
                                        </span>
                                        <div className="flex-1 space-y-2">
                                            <input
                                                type="text"
                                                value={q.question}
                                                onChange={(e) => updateCustomQuestion(q.id, { question: e.target.value })}
                                                placeholder="Question..."
                                                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-sm"
                                            />
                                            <div className="flex gap-2">
                                                <input
                                                    type="text"
                                                    value={q.expectedAnswer || ''}
                                                    onChange={(e) => updateCustomQuestion(q.id, { expectedAnswer: e.target.value })}
                                                    placeholder="Expected answer (optional)"
                                                    className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-sm"
                                                />
                                                <select
                                                    value={q.answerType}
                                                    onChange={(e) => updateCustomQuestion(q.id, { answerType: e.target.value as AnswerType })}
                                                    className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-sm"
                                                >
                                                    <option value="exact">Exact match</option>
                                                    <option value="contains">Contains</option>
                                                    <option value="free_response">Free response</option>
                                                </select>
                                            </div>
                                        </div>
                                        <button
                                            onClick={() => removeCustomQuestion(q.id)}
                                            className="p-1 text-gray-400 hover:text-red-500"
                                        >
                                            <TrashIcon className="h-4 w-4" />
                                        </button>
                                    </div>
                                ))}

                                {customQuestions.length === 0 && (
                                    <p className="text-sm text-gray-400 dark:text-gray-500 text-center py-4">
                                        No questions added yet
                                    </p>
                                )}
                            </div>
                        </div>

                        <div className="flex justify-end">
                            <button
                                onClick={handleCreateCustomTest}
                                disabled={!customContext.trim() || customQuestions.length === 0}
                                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                            >
                                Create Test
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Selected Test Preview & Model Selection */}
            {selectedTemplate && (
                <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
                    <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                        <div className="flex items-center justify-between">
                            <div>
                                <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                                    {selectedTemplate.name}
                                </h2>
                                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                                    {selectedTemplate.questions.length} questions
                                </p>
                            </div>
                            <button
                                onClick={handleRunTest}
                                disabled={isRunning || selectedModels.size === 0}
                                className="flex items-center gap-2 px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
                            >
                                {isRunning ? (
                                    <>
                                        <ArrowPathIcon className="h-5 w-5 animate-spin" />
                                        Running...
                                    </>
                                ) : (
                                    <>
                                        <PlayIcon className="h-5 w-5" />
                                        Run Test
                                    </>
                                )}
                            </button>
                        </div>
                    </div>

                    <div className="p-6">
                        {/* Model Selection */}
                        <div className="mb-6">
                            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                                Select Models to Test
                            </h3>
                            <div className="flex flex-wrap gap-2">
                                {AVAILABLE_MODELS.map((model) => {
                                    const isSelected = selectedModels.has(model.id);
                                    return (
                                        <button
                                            key={model.id}
                                            onClick={() => model.available && handleToggleModel(model.id)}
                                            disabled={!model.available}
                                            className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                                                !model.available
                                                    ? 'bg-gray-100 dark:bg-gray-700 text-gray-400 cursor-not-allowed'
                                                    : isSelected
                                                        ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border-2 border-blue-500'
                                                        : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                                            }`}
                                        >
                                            {model.name}
                                            {!model.available && (
                                                <span className="ml-1 text-xs opacity-70">(coming soon)</span>
                                            )}
                                        </button>
                                    );
                                })}
                            </div>
                        </div>

                        {/* Context Preview */}
                        <div className="mb-6">
                            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                Context
                            </h3>
                            <div className="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                                <pre className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap font-sans">
                                    {selectedTemplate.context}
                                </pre>
                            </div>
                        </div>

                        {/* Questions Preview */}
                        <div>
                            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                Questions
                            </h3>
                            <div className="space-y-2">
                                {selectedTemplate.questions.map((q, index) => (
                                    <div key={q.id} className="flex items-start gap-3 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                                        <span className="text-sm font-medium text-gray-500">
                                            {index + 1}.
                                        </span>
                                        <div className="flex-1">
                                            <p className="text-sm text-gray-900 dark:text-white">
                                                {q.question}
                                            </p>
                                            {q.expectedAnswer && (
                                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                                                    Expected: <span className="font-mono">{q.expectedAnswer}</span>
                                                </p>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Results */}
            {results.length > 0 && (
                <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
                    <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                            Results
                        </h2>
                    </div>

                    <div className="p-6">
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            {results.map((modelResult) => (
                                <ModelResultCard
                                    key={modelResult.modelId}
                                    result={modelResult}
                                    questions={selectedTemplate?.questions || []}
                                />
                            ))}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

// ============================================================================
// Result Card Component
// ============================================================================

function ModelResultCard({ result, questions }: { result: ModelResult; questions: TestQuestion[] }) {
    const [showRawResponse, setShowRawResponse] = useState(false);
    const scorePercentage = result.totalQuestions > 0
        ? Math.round((result.totalCorrect / result.totalQuestions) * 100)
        : 0;

    return (
        <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
            {/* Header */}
            <div className="p-4 bg-gray-50 dark:bg-gray-700/50 border-b border-gray-200 dark:border-gray-700">
                <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-gray-900 dark:text-white">
                        {result.modelName}
                    </h3>
                    <div className="flex items-center gap-3">
                        {result.status === 'running' && (
                            <ArrowPathIcon className="h-5 w-5 text-blue-500 animate-spin" />
                        )}
                        {result.status === 'complete' && (
                            <span className={`text-lg font-bold ${
                                scorePercentage >= 80
                                    ? 'text-green-600 dark:text-green-400'
                                    : scorePercentage >= 50
                                        ? 'text-yellow-600 dark:text-yellow-400'
                                        : 'text-red-600 dark:text-red-400'
                            }`}>
                                {result.totalCorrect}/{result.totalQuestions} ({scorePercentage}%)
                            </span>
                        )}
                        {result.status === 'error' && (
                            <span className="text-red-600 dark:text-red-400 text-sm">
                                Error
                            </span>
                        )}
                    </div>
                </div>
                {result.status === 'complete' && (
                    <div className="flex items-center justify-between mt-1">
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                            Total latency: {result.latencyMs}ms
                        </p>
                        <button
                            onClick={() => setShowRawResponse(!showRawResponse)}
                            className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                        >
                            {showRawResponse ? 'Hide' : 'Show'} raw response
                        </button>
                    </div>
                )}
                {result.status === 'error' && result.error && (
                    <p className="text-xs text-red-500 mt-1">{result.error}</p>
                )}
            </div>

            {/* Raw Response (collapsible) */}
            {showRawResponse && result.rawResponse && (
                <div className="p-3 bg-gray-100 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
                    <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Raw Response:</p>
                    <pre className="text-xs text-gray-700 dark:text-gray-300 whitespace-pre-wrap font-mono bg-white dark:bg-gray-900 p-2 rounded border border-gray-200 dark:border-gray-700">
                        {result.rawResponse}
                    </pre>
                </div>
            )}

            {/* Results */}
            <div className="divide-y divide-gray-200 dark:divide-gray-700">
                {result.results.map((r, index) => {
                    const question = questions.find(q => q.id === r.questionId);
                    return (
                        <div key={r.questionId} className="p-3">
                            <div className="flex items-start gap-2">
                                {r.isCorrect === true && (
                                    <CheckCircleIcon className="h-5 w-5 text-green-500 flex-shrink-0 mt-0.5" />
                                )}
                                {r.isCorrect === false && (
                                    <XCircleIcon className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
                                )}
                                {r.isCorrect === null && (
                                    <QuestionMarkCircleIcon className="h-5 w-5 text-gray-400 flex-shrink-0 mt-0.5" />
                                )}
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm text-gray-700 dark:text-gray-300">
                                        <span className="font-medium">Q{index + 1}:</span> {question?.question}
                                    </p>
                                    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                                        <span className="text-gray-500">
                                            Response: <span className="font-mono text-gray-900 dark:text-white">{r.response || '(empty)'}</span>
                                        </span>
                                        {r.expectedAnswer && r.isCorrect === false && (
                                            <span className="text-red-500">
                                                Expected: <span className="font-mono">{r.expectedAnswer}</span>
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                    );
                })}

                {result.results.length === 0 && result.status === 'pending' && (
                    <div className="p-4 text-center text-gray-400 dark:text-gray-500 text-sm">
                        Waiting to start...
                    </div>
                )}
            </div>
        </div>
    );
}
