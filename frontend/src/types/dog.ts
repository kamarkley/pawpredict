export type DogSex = "MALE" | "FEMALE" | "UNKNOWN";

export interface Dog {
  id: string;
  name: string;
  birth_date: string;
  breed: string | null;
  sex: DogSex;
  weight_lbs: string | null;
  neutered: boolean | null;
  age_in_days: number;
  age_in_weeks: number;
}

export interface DogCreate {
  name: string;
  birth_date: string;
  breed: string | null;
  sex: DogSex;
  weight_lbs: number | null;
  neutered: boolean | null;
}

export interface DogUpdate {
  name?: string;
  birth_date?: string;
  breed?: string | null;
  sex?: DogSex;
  weight_lbs?: number | null;
  neutered?: boolean | null;
}
