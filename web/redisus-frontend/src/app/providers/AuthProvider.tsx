import { onAuthStateChanged, type User } from 'firebase/auth';
import { createContext, useContext, useEffect, useMemo, useState } from 'react';

import { auth, isFirebaseConfigured } from '../../lib/firebase';
import { supabase } from '../../lib/supabase';
import type { UserProfile } from '../../lib/types';
import { ensureUserProfile } from '../../features/auth/authService';

interface AuthContextValue {
  user: User | null;
  profile: UserProfile | null;
  loading: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loadingAuth, setLoadingAuth] = useState(true);
  const [loadingProfile, setLoadingProfile] = useState(false);

  useEffect(() => {
    if (!isFirebaseConfigured) {
      setLoadingAuth(false);
      return undefined;
    }

    return onAuthStateChanged(auth, nextUser => {
      setUser(nextUser);
      if (nextUser) void ensureUserProfile(nextUser);
      setLoadingAuth(false);
    });
  }, []);

  useEffect(() => {
    if (!user) {
      setProfile(null);
      setLoadingProfile(false);
      return undefined;
    }

    setLoadingProfile(true);

    const fetchProfile = async () => {
      const { data, error } = await supabase
        .from('users')
        .select('*')
        .eq('uid', user.uid)
        .maybeSingle();

      if (error) {
        setLoadingProfile(false);
        return;
      }

      if (data) {
        setProfile({
          uid: data.uid,
          displayName: data.display_name,
          email: data.email,
          photoURL: data.photo_url || null,
          providerIds: data.provider_ids || [],
          role: (data.role as UserProfile['role']) || 'professional',
          settings: data.settings || {},
          professionalArea: data.professional_area || '',
          clinicName: data.clinic_name || '',
          phone: data.phone || '',
          onboardingCompleted: data.onboarding_completed || false,
          createdAt: data.created_at,
          updatedAt: data.updated_at
        });
      }
      setLoadingProfile(false);
    };

    void fetchProfile();

    const channel = supabase
      .channel(`user-profile-changes-${user.uid}`)
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'users', filter: `uid=eq.${user.uid}` },
        () => {
          void fetchProfile();
        }
      )
      .subscribe();

    return () => {
      void supabase.removeChannel(channel);
    };
  }, [user]);

  const value = useMemo(
    () => ({ user, profile, loading: loadingAuth || loadingProfile }),
    [loadingAuth, loadingProfile, profile, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth deve ser usado dentro de AuthProvider');
  return context;
}
