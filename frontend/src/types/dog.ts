export interface Dog {
  id: string;
  name: string;
  birth_date: string;
  breed: string | null;
  sex: string;
  weight_lbs: string | null;
  neutered: boolean | null;
  age_in_days: number;
  age_in_weeks: number;
}