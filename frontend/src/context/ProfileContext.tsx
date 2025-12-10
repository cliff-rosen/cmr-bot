import { createContext, useContext, useState, useCallback, ReactNode } from 'react';

interface UserProfile {
    user_id: number;
    email: string;
    full_name: string | null;
    display_name: string | null;
    bio: string | null;
    preferences: Record<string, any>;
}

interface ProfileContextType {
    userProfile: UserProfile | null;
    isLoading: boolean;
    error: string | null;
    setUserProfile: (profile: UserProfile) => void;
    clearError: () => void;
}

const ProfileContext = createContext<ProfileContextType | undefined>(undefined);

interface ProfileProviderProps {
    children: ReactNode;
}

export function ProfileProvider({ children }: ProfileProviderProps) {
    const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const clearError = useCallback(() => {
        setError(null);
    }, []);

    const value: ProfileContextType = {
        userProfile,
        isLoading,
        error,
        setUserProfile,
        clearError,
    };

    return (
        <ProfileContext.Provider value={value}>
            {children}
        </ProfileContext.Provider>
    );
}

export function useProfile(): ProfileContextType {
    const context = useContext(ProfileContext);
    if (context === undefined) {
        throw new Error('useProfile must be used within a ProfileProvider');
    }
    return context;
}
