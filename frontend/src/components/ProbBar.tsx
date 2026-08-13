"use client";

interface Props {
  probA: number;
  probB: number;
  nameA: string;
  nameB: string;
}

export default function ProbBar({ probA, probB, nameA, nameB }: Props) {
  const pctA = Math.round(probA * 100);
  const pctB = Math.round(probB * 100);
  const aWins = probA >= probB;

  return (
    <div className="space-y-2">
      <div className="flex justify-between text-sm font-medium">
        <span className={aWins ? "text-accent" : "text-muted"}>
          {nameA}
        </span>
        <span className={!aWins ? "text-accent" : "text-muted"}>
          {nameB}
        </span>
      </div>
      <div className="flex h-3 rounded-full overflow-hidden bg-card border border-border">
        <div
          className="prob-bar bg-accent/80 transition-all"
          style={{ width: `${pctA}%` }}
        />
        <div
          className="prob-bar bg-foreground/20 transition-all"
          style={{ width: `${pctB}%` }}
        />
      </div>
      <div className="flex justify-between text-xs text-muted">
        <span>{pctA}%</span>
        <span>{pctB}%</span>
      </div>
    </div>
  );
}
