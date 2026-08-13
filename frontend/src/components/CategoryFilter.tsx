"use client";

import { useEffect, useState } from "react";
import { getCategories, type Category } from "@/lib/api";

interface Props {
  value: string;
  onChange: (value: string) => void;
}

export default function CategoryFilter({ value, onChange }: Props) {
  const [categories, setCategories] = useState<Category[]>([]);

  useEffect(() => {
    getCategories().then((r) => setCategories(r.categories));
  }, []);

  return (
    <div className="flex gap-1.5 flex-wrap">
      <button
        onClick={() => onChange("")}
        className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
          value === ""
            ? "bg-accent text-white"
            : "bg-card border border-border text-muted hover:text-foreground hover:bg-card-hover"
        }`}
      >
        All
      </button>
      {categories.map((c) => (
        <button
          key={c.value}
          onClick={() => onChange(c.value)}
          className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
            value === c.value
              ? "bg-accent text-white"
              : "bg-card border border-border text-muted hover:text-foreground hover:bg-card-hover"
          }`}
        >
          {c.label}
        </button>
      ))}
    </div>
  );
}
