import { doc, getDoc, setDoc } from "firebase/firestore";
import { db } from "@/lib/firebase";

export type NotificationPreferences = {
  appointmentReminders: boolean;
  evaluationAlerts: boolean;
  weeklySummary: boolean;
};

export type AccessibilityPreferences = {
  largeText: boolean;
  highContrast: boolean;
  reducedMotion: boolean;
};

export type UserSettings = {
  notifications: NotificationPreferences;
  accessibility: AccessibilityPreferences;
};

const DEFAULT_SETTINGS: UserSettings = {
  notifications: {
    appointmentReminders: true,
    evaluationAlerts: true,
    weeklySummary: false,
  },
  accessibility: {
    largeText: false,
    highContrast: false,
    reducedMotion: false,
  },
};

function settingsDocRef(uid: string) {
  return doc(db, "users", uid, "settings", "preferences");
}

export async function getUserSettings(uid: string): Promise<UserSettings> {
  const snapshot = await getDoc(settingsDocRef(uid));

  if (!snapshot.exists()) {
    return DEFAULT_SETTINGS;
  }

  const data = snapshot.data() as Partial<UserSettings>;

  return {
    notifications: {
      ...DEFAULT_SETTINGS.notifications,
      ...(data.notifications ?? {}),
    },
    accessibility: {
      ...DEFAULT_SETTINGS.accessibility,
      ...(data.accessibility ?? {}),
    },
  };
}

export async function saveUserSettings(
  uid: string,
  settings: Partial<UserSettings>,
): Promise<void> {
  await setDoc(settingsDocRef(uid), settings, { merge: true });
}
