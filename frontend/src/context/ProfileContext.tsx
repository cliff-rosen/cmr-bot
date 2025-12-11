import { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react';
import { profileApi, Profile, ProfileUpdate } from '../lib/api/profileApi';
import { useAuth } from './AuthContext';

interface ProfileContextType {
    userProfile: Profile | null;
    isLoading: boolean;
    error: string | null;
    refreshProfile: () => Promise<void>;
    updateProfile: (data: ProfileUpdate) => Promise<Profile>;
    clearError: () => void;
}

const ProfileContext = createContext<ProfileContextType | undefined>(undefined);

interface ProfileProviderProps {
    children: ReactNode;
}

export function ProfileProvider({ children }: ProfileProviderProps) {
    const { user } = useAuth();
    const [userProfile, setUserProfile] = useState<Profile | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const clearError = useCallback(() => {
        setError(null);
    }, []);

    const refreshProfile = useCallback(async () => {
        if (!user) {
            setUserProfile(null);
            return;
        }

        setIsLoading(true);
        setError(null);
        try {
            const profile = await profileApi.get();
            setUserProfile(profile);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to load profile');
        } finally {
            setIsLoading(false);
        }
    }, [user]);

    const updateProfile = useCallback(async (data: ProfileUpdate): Promise<Profile> => {
        setIsLoading(true);
        setError(null);
        try {
            const updatedProfile = await profileApi.update(data);
            setUserProfile(updatedProfile);
            return updatedProfile;
        } catch (err: any) {
            const errorMessage = err.response?.data?.detail || 'Failed to update profile';
            setError(errorMessage);
            throw new Error(errorMessage);
        } finally {
            setIsLoading(false);
        }
    }, []);

    // Fetch profile when user changes
    useEffect(() => {
        refreshProfile();
    }, [refreshProfile]);

    const value: ProfileContextType = {
        userProfile,
        isLoading,
        error,
        refreshProfile,
        updateProfile,
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
