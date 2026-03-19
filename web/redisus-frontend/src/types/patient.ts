export type Patient = {
  id: string;
  name: string;
  age: number;
  clinicalHistory: string;
  createdAt?: unknown;
  updatedAt?: unknown;
};

export type NewPatientPayload = {
  name: string;
  age: number;
  clinicalHistory: string;
};

export type UpdatePatientPayload = Partial<NewPatientPayload>;
