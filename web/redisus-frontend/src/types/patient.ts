export type Patient = {
  id: string;
  name: string;
  birthDate: string;
  phone: string;
  email: string;
  profession: string;
  maritalStatus: string;
  age?: number;
  clinicalHistory: string;
  hppItems?: string[];
  comorbidities?: string[];
  medicationsInUse?: Array<{
    name: string;
    dose: string;
  }>;
  createdAt?: unknown;
  updatedAt?: unknown;
};

export type NewPatientPayload = {
  name: string;
  birthDate: string;
  phone: string;
  email: string;
  profession: string;
  maritalStatus: string;
  age?: number;
  clinicalHistory: string;
  hppItems?: string[];
  comorbidities?: string[];
  medicationsInUse?: Array<{
    name: string;
    dose: string;
  }>;
};

export type UpdatePatientPayload = Partial<NewPatientPayload>;
