import { FormEvent, useEffect, useState } from "react";
import { Save } from "lucide-react";
import type { Clinic, ClinicUpdate } from "../types";

type ClinicUpdateFormProps = {
  clinic: Clinic;
  onSubmit: (update: ClinicUpdate) => Promise<void>;
};

export function ClinicUpdateForm({ clinic, onSubmit }: ClinicUpdateFormProps) {
  const [values, setValues] = useState({
    test_kits_available: clinic.test_kits_available,
    people_waiting: clinic.people_waiting,
    nurses_available: clinic.nurses_available,
    threshold_min_kits: clinic.threshold_min_kits,
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setValues({
      test_kits_available: clinic.test_kits_available,
      people_waiting: clinic.people_waiting,
      nurses_available: clinic.nurses_available,
      threshold_min_kits: clinic.threshold_min_kits,
    });
  }, [clinic]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    try {
      await onSubmit(values);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <label className="field-label">
          Kits
          <input
            className="number-input"
            min={0}
            type="number"
            value={values.test_kits_available}
            onChange={(event) =>
              setValues((current) => ({
                ...current,
                test_kits_available: Number(event.target.value),
              }))
            }
          />
        </label>
        <label className="field-label">
          Waiting
          <input
            className="number-input"
            min={0}
            type="number"
            value={values.people_waiting}
            onChange={(event) =>
              setValues((current) => ({
                ...current,
                people_waiting: Number(event.target.value),
              }))
            }
          />
        </label>
        <label className="field-label">
          Nurses
          <input
            className="number-input"
            min={0}
            type="number"
            value={values.nurses_available}
            onChange={(event) =>
              setValues((current) => ({
                ...current,
                nurses_available: Number(event.target.value),
              }))
            }
          />
        </label>
        <label className="field-label">
          Threshold
          <input
            className="number-input"
            min={0}
            type="number"
            value={values.threshold_min_kits}
            onChange={(event) =>
              setValues((current) => ({
                ...current,
                threshold_min_kits: Number(event.target.value),
              }))
            }
          />
        </label>
      </div>
      <button className="primary-button w-full" disabled={saving} type="submit">
        <Save size={16} />
        {saving ? "Saving" : "Save update"}
      </button>
    </form>
  );
}
