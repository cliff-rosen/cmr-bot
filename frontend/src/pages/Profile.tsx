import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useProfile } from '../context/ProfileContext';

export default function Profile() {
    const { user } = useAuth();
    const { userProfile, isLoading, error, updateProfile, clearError } = useProfile();

    // Form state
    const [userForm, setUserForm] = useState({
        display_name: '',
        bio: ''
    });

    const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');

    // Sync form with profile data when it loads
    useEffect(() => {
        if (userProfile) {
            setUserForm({
                display_name: userProfile.display_name || '',
                bio: userProfile.bio || ''
            });
        }
    }, [userProfile]);

    const handleUserFormSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaveStatus('saving');

        try {
            await updateProfile({
                display_name: userForm.display_name || undefined,
                bio: userForm.bio || undefined
            });
            setSaveStatus('saved');
            setTimeout(() => setSaveStatus('idle'), 2000);
        } catch {
            setSaveStatus('error');
        }
    };

    return (
        <div className="max-w-4xl mx-auto p-6">
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
                    Profile
                </h1>
                <p className="text-gray-600 dark:text-gray-400 mt-2">
                    Manage your account settings
                </p>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
                <div className="p-6">
                    <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">
                        User Profile
                    </h2>

                    {error && (
                        <div className="mb-4 bg-red-50 dark:bg-red-900/50 border border-red-200 dark:border-red-700 rounded-lg p-4">
                            <p className="text-red-800 dark:text-red-200">{error}</p>
                            <button
                                onClick={clearError}
                                className="mt-2 text-sm text-red-600 dark:text-red-400 hover:underline"
                            >
                                Dismiss
                            </button>
                        </div>
                    )}

                    {saveStatus === 'saved' && (
                        <div className="mb-4 bg-green-50 dark:bg-green-900/50 border border-green-200 dark:border-green-700 rounded-lg p-4">
                            <p className="text-green-800 dark:text-green-200">Profile saved successfully!</p>
                        </div>
                    )}

                    {saveStatus === 'error' && (
                        <div className="mb-4 bg-red-50 dark:bg-red-900/50 border border-red-200 dark:border-red-700 rounded-lg p-4">
                            <p className="text-red-800 dark:text-red-200">Failed to save profile. Please try again.</p>
                        </div>
                    )}

                    <form onSubmit={handleUserFormSubmit} className="space-y-6">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                Email Address
                            </label>
                            <input
                                type="email"
                                value={user?.email || ''}
                                disabled
                                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white"
                            />
                            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                                Email cannot be changed after registration
                            </p>
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                Display Name
                            </label>
                            <input
                                type="text"
                                placeholder="How you want to be addressed"
                                value={userForm.display_name}
                                onChange={(e) => setUserForm({ ...userForm, display_name: e.target.value })}
                                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                Bio
                            </label>
                            <textarea
                                placeholder="Tell us a bit about yourself..."
                                rows={3}
                                value={userForm.bio}
                                onChange={(e) => setUserForm({ ...userForm, bio: e.target.value })}
                                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                            />
                        </div>

                        <div className="flex justify-end">
                            <button
                                type="submit"
                                disabled={isLoading || saveStatus === 'saving'}
                                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
                            >
                                {saveStatus === 'saving' ? 'Saving...' : 'Save Profile'}
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    );
}
