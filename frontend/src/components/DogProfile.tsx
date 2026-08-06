import type { Dog } from "../types/dog";

interface DogProfileProps {
  dog: Dog;
}

function formatSex(sex: string): string {
  return sex.charAt(0) + sex.slice(1).toLowerCase();
}

export function DogProfile({ dog }: DogProfileProps) {
  return (
    <section className="profile-card">
      <div className="profile-heading">
        <div className="profile-avatar" aria-hidden="true">
          🐶
        </div>

        <div>
          <p className="eyebrow">Dog profile</p>
          <h1>{dog.name}</h1>
          <p className="profile-subtitle">
            {dog.breed ?? "Breed not entered"}
          </p>
        </div>
      </div>

      <dl className="profile-grid">
        <div>
          <dt>Age</dt>
          <dd>
            {dog.age_in_weeks} weeks
            <span>{dog.age_in_days} days</span>
          </dd>
        </div>

        <div>
          <dt>Birthday</dt>
          <dd>
            {new Date(`${dog.birth_date}T00:00:00`).toLocaleDateString(
              "en-US",
              {
                month: "long",
                day: "numeric",
                year: "numeric",
              },
            )}
          </dd>
        </div>

        <div>
          <dt>Sex</dt>
          <dd>{formatSex(dog.sex)}</dd>
        </div>

        <div>
          <dt>Weight</dt>
          <dd>
            {dog.weight_lbs ? `${dog.weight_lbs} lbs` : "Not entered"}
          </dd>
        </div>

        <div>
          <dt>Neutered</dt>
          <dd>
            {dog.neutered === null
              ? "Not entered"
              : dog.neutered
                ? "Yes"
                : "No"}
          </dd>
        </div>
      </dl>
    </section>
  );
}