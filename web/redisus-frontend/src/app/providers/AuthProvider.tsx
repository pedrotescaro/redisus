import { onAuthStateChanged, type User } from 'firebase/auth';
import { doc, onSnapshot } from 'firebase/firestore';
import { createContext, useContext, useEffect, useMemo, useState } from 'react';

import { auth, db } from '../../lib/firebase';
import { userPath } from '../../lib/firestorePaths';
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

  useEffect(
    () =>
      onAuthStateChanged(auth, nextUser => {
        setUser(nextUser);
        if (nextUser) void ensureUserProfile(nextUser);
        setLoadingAuth(false);
      }),
    []
  );

  useEffect(() => {
    if (!user) {
      setProfile(null);
      setLoadingProfile(false);
      return undefined;
    }

    setLoadingProfile(true);
    return onSnapshot(
      doc(db, userPath(user.uid)),
      snapshot => {
        setProfile(snapshot.exists() ? (snapshot.data() as UserProfile) : null);
        setLoadingProfile(false);
      },
      () => setLoadingProfile(false)
    );
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
