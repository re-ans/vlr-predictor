"use client";

const REGIONS = [
  { value: "", label: "All Regions" },
  { value: "NA", label: "NA" },
  { value: "WEU", label: "EMEA" },
  { value: "EEU", label: "EEU" },
  { value: "SA", label: "SA" },
  { value: "ASIA", label: "ASIA" },
  { value: "OCE", label: "OCE" },
];

interface Props {
  value: string;
  onChange: (value: string) => void;
}

export default function RegionFilter({ value, onChange }: Props) {
  return (
    <div className="flex gap-1.5 flex-wrap">
      {REGIONS.map((r) => (
        <button
          key={r.value}
          onClick={() => onChange(r.value)}
          className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
            value === r.value
              ? "bg-accent text-white"
              : "bg-card border border-border text-muted hover:text-foreground hover:bg-card-hover"
          }`}
        >
          {r.label}
        </button>
      ))}
    </div>
  );
}
