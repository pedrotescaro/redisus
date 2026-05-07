export const userPath = (uid: string) => `users/${uid}`;
export const patientsPath = (uid: string) => `${userPath(uid)}/patients`;
export const patientPath = (uid: string, patientId: string) => `${patientsPath(uid)}/${patientId}`;
export const evaluationsPath = (uid: string, patientId: string) => `${patientPath(uid, patientId)}/evaluations`;
export const evaluationPath = (uid: string, patientId: string, evaluationId: string) =>
  `${evaluationsPath(uid, patientId)}/${evaluationId}`;
export const analysisResultsPath = (uid: string, patientId: string, evaluationId: string) =>
  `${evaluationPath(uid, patientId, evaluationId)}/analysisResults`;
export const analysisResultPath = (uid: string, patientId: string, evaluationId: string, analysisId: string) =>
  `${analysisResultsPath(uid, patientId, evaluationId)}/${analysisId}`;
export const standaloneAnalysisResultsPath = (uid: string) => `${userPath(uid)}/analysisResults`;
export const appointmentsPath = (uid: string) => `${userPath(uid)}/appointments`;
export const appointmentPath = (uid: string, appointmentId: string) => `${appointmentsPath(uid)}/${appointmentId}`;
