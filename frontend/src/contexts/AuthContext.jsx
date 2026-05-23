import { createContext, useContext, useEffect, useState } from 'react';
import {
  onAuthStateChanged,
  signInWithPopup,
  signOut as firebaseSignOut,
} from 'firebase/auth';
import { auth, googleProvider } from '../lib/firebase';

/**
 * AuthContext — global authentication state for VidIQ.
 *
 * Provides:
 *   user        — Firebase User object, or null when signed out
 *   loading     — true while the initial auth state is being resolved
 *   signIn()    — triggers Google Sign-In popup
 *   signOut()   — signs the user out
 *   getToken()  — returns a fresh Firebase ID token (auto-refreshed)
 */
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // onAuthStateChanged fires immediately with the current user (or null),
    // then again whenever the auth state changes. The unsubscribe function
    // is returned for cleanup on unmount.
    const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
      setUser(firebaseUser);
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  const signIn = async () => {
    try {
      await signInWithPopup(auth, googleProvider);
      // onAuthStateChanged will update `user` automatically
    } catch (err) {
      // USER_CANCELLED (popup closed) is not an error worth surfacing
      if (err.code !== 'auth/popup-closed-by-user' && err.code !== 'auth/cancelled-popup-request') {
        console.error('Sign-in failed:', err);
        throw err;
      }
    }
  };

  const signOut = async () => {
    await firebaseSignOut(auth);
  };

  /**
   * Returns a fresh Firebase ID token for the current user.
   * Automatically refreshes if the token is within 5 minutes of expiry.
   * Returns null if no user is signed in.
   */
  const getToken = async () => {
    if (!user) return null;
    return user.getIdToken(/* forceRefresh */ false);
  };

  return (
    <AuthContext.Provider value={{ user, loading, signIn, signOut, getToken }}>
      {children}
    </AuthContext.Provider>
  );
}

/**
 * useAuth — convenience hook for consuming AuthContext.
 *
 * Usage:
 *   const { user, signIn, signOut, getToken } = useAuth();
 */
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used inside <AuthProvider>');
  }
  return ctx;
}
