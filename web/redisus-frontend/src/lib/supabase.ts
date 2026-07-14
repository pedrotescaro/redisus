import { createClient } from '@supabase/supabase-js';

const configuredSupabaseUrl = import.meta.env.VITE_SUPABASE_URL?.trim();
const configuredSupabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY?.trim();

export const isSupabaseConfigured = Boolean(configuredSupabaseUrl && configuredSupabaseAnonKey);

// Keep public routes renderable in local development. Data-backed routes are
// already protected by the Firebase configuration check in App.tsx.
const supabaseUrl = configuredSupabaseUrl || 'http://127.0.0.1:54321';
const supabaseAnonKey = configuredSupabaseAnonKey || 'local-development-anon-key';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
