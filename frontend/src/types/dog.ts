export interface Dog {
  id: string;
  name: string;
  birth_date: string;
  breed: string | null;
  sex: "MALE" | "FEMALE" | "UNKNOWN";
  weight_lbs: string | null;
  neutered: boolean | null;
  age_in_days: number;
  age_in_weeks: number;
}

export interface DogUpdate {
  name?: string;
  birth_date?: string;
  breed?: string | null;
  sex?: "MALE" | "FEMALE" | "UNKNOWN";
  weight_lbs?: number | null;
  neutered?: boolean | null;
}
