import { PlusIcon, ChatBubbleLeftRightIcon, TrashIcon } from '@heroicons/react/24/solid';

interface Conversation {
    conversation_id: number;
    title: string | null;
    updated_at: string;
}

interface ConversationSidebarProps {
    conversations: Conversation[];
    currentConversationId: number | null;
    isLoading: boolean;
    confirmDeleteId: number | null;
    onNewConversation: () => void;
    onSelectConversation: (id: number) => void;
    onDeleteConversation: (id: number, e: React.MouseEvent) => void;
}

export default function ConversationSidebar({
    conversations,
    currentConversationId,
    isLoading,
    confirmDeleteId,
    onNewConversation,
    onSelectConversation,
    onDeleteConversation
}: ConversationSidebarProps) {
    return (
        <div className="flex flex-col h-full">
            {/* Sidebar Header */}
            <div className="flex items-center justify-between px-4 py-4 border-b border-gray-200 dark:border-gray-700 min-w-[256px]">
                <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
                    Conversations
                </h2>
                <button
                    onClick={onNewConversation}
                    className="p-1.5 text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white hover:bg-gray-200 dark:hover:bg-gray-700 rounded"
                    title="New conversation"
                >
                    <PlusIcon className="h-5 w-5" />
                </button>
            </div>

            {/* Conversation List */}
            <div className="flex-1 overflow-y-auto min-w-[256px]">
                {isLoading ? (
                    <div className="p-4 text-center text-gray-500 dark:text-gray-400 text-sm">
                        Loading...
                    </div>
                ) : conversations.length === 0 ? (
                    <div className="p-4 text-center text-gray-500 dark:text-gray-400 text-sm">
                        No conversations yet
                    </div>
                ) : (
                    <div className="py-2">
                        {conversations.map((conv) => {
                            const isConfirmingDelete = confirmDeleteId === conv.conversation_id;
                            return (
                                <div
                                    key={conv.conversation_id}
                                    onClick={() => onSelectConversation(conv.conversation_id)}
                                    className={`group flex items-center gap-2 px-4 py-2.5 cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-800 ${
                                        conv.conversation_id === currentConversationId
                                            ? 'bg-gray-200 dark:bg-gray-800'
                                            : ''
                                    }`}
                                >
                                    <ChatBubbleLeftRightIcon className="h-4 w-4 text-gray-400 flex-shrink-0" />
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm text-gray-900 dark:text-white truncate">
                                            {conv.title || 'New conversation'}
                                        </p>
                                        <p className="text-xs text-gray-500 dark:text-gray-400">
                                            {new Date(conv.updated_at).toLocaleDateString()}
                                        </p>
                                    </div>
                                    <button
                                        onClick={(e) => onDeleteConversation(conv.conversation_id, e)}
                                        className={`p-1 rounded transition-all ${
                                            isConfirmingDelete
                                                ? 'bg-red-500 text-white opacity-100'
                                                : 'text-gray-400 hover:text-red-600 dark:hover:text-red-400 opacity-0 group-hover:opacity-100'
                                        }`}
                                        title={isConfirmingDelete ? 'Click again to confirm' : 'Delete conversation'}
                                    >
                                        <TrashIcon className="h-4 w-4" />
                                    </button>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
}
