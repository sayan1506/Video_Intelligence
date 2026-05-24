import { initializeApp } from 'firebase/app';
import { getAuth, GoogleAuthProvider } from 'firebase/auth';

/**
 * Firebase project configuration.
 * All values come from Vite env vars — set them in .env.local for development
 * and in the Firebase Hosting environment for production.
 *
 * Required vars:
 *   VITE_FIREBASE_API_KEY
 *   VITE_FIREBASE_AUTH_DOMAIN
 *   VITE_FIREBASE_PROJECT_ID
 *   VITE_FIREBASE_STORAGE_BUCKET
 *   VITE_FIREBASE_MESSAGING_SENDER_ID
 *   VITE_FIREBASE_APP_ID
 */
const firebaseConfig = {
  apiKey:            import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain:        import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId:         import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket:     import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId:             import.meta.env.VITE_FIREBASE_APP_ID,
};

// Singleton Firebase app — safe to call initializeApp multiple times in dev
// because Vite HMR may re-execute this module; Firebase deduplicates by name.
const app = initializeApp(firebaseConfig);

export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();

// Request the user's profile and email scopes
googleProvider.addScope('profile');
googleProvider.addScope('email');
