"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

export interface ProbabilityFactor {
  name: string;
  impact: number;
  description: string;
  met: boolean;
}

interface ProbabilityGaugeProps {
  probability: number;
  confidence?: "low" | "medium" | "high";
  factors?: ProbabilityFactor[];
  recommendation?: string;
  size?: "sm" | "md" | "lg";
  expandable?: boolean;
}

const sizeConfig = {
  sm: { width: 80, stroke: 6, fontSize: "text-sm", radius: 32, labelSize: "text-[10px]" },
  md: { width: 120, stroke: 8, fontSize: "text-xl", radius: 48, labelSize: "text-xs" },
  lg: { width: 160, stroke: 10, fontSize: "text-2xl", radius: 64, labelSize: "text-sm" },
};

const confidenceLabels: Record<string, { label: string; color: string }> = {
  high: { label: "High confidence", color: "text-green-600" },
  medium: { label: "Medium confidence", color: "text-yellow-600" },
  low: { label: "Low confidence", color: "text-red-500" },
};

function getColor(probability: number): { stroke: string; text: string; bg: string } {
  if (probability < 50) return { stroke: "#ef4444", text: "text-red-600", bg: "bg-red-50" };
  if (probability <= 70) return { stroke: "#eab308", text: "text-yellow-600", bg: "bg-yellow-50" };
  return { stroke: "#22c55e", text: "text-green-600", bg: "bg-green-50" };
}

export default function ProbabilityGauge({
  probability,
  confidence,
  factors,
  recommendation,
  size = "md",
  expandable = true,
}: ProbabilityGaugeProps) {
  const [expanded, setExpanded] = useState(false);
  const config = sizeConfig[size];
  const color = getColor(probability);
  const circumference = Math.PI * config.radius;
  const filled = (probability / 100) * circumference;
  const center = config.width / 2;
  const viewBox = `0 0 ${config.width} ${config.width * 0.65}`;

  const confInfo = confidence ? confidenceLabels[confidence] : null;

  // Separate factors into positive/negative (skip the base rate factor for display)
  const displayFactors = (factors || []).filter(f => !f.name.startsWith("Base approval"));
  const positiveFactors = displayFactors.filter(f => f.impact > 0 && f.met);
  const negativeFactors = displayFactors.filter(f => f.impact < 0);

  const hasDetails = displayFactors.length > 0 || recommendation;

  return (
    <div className="flex flex-col items-center">
      {/* Gauge SVG */}
      <svg
        width={config.width}
        height={config.width * 0.65}
        viewBox={viewBox}
        className="overflow-visible"
      >
        {/* Background arc */}
        <path
          d={`M ${center - config.radius} ${center} A ${config.radius} ${config.radius} 0 0 1 ${center + config.radius} ${center}`}
          fill="none"
          stroke="#e2e8f0"
          strokeWidth={config.stroke}
          strokeLinecap="round"
        />
        {/* Filled arc */}
        <path
          d={`M ${center - config.radius} ${center} A ${config.radius} ${config.radius} 0 0 1 ${center + config.radius} ${center}`}
          fill="none"
          stroke={color.stroke}
          strokeWidth={config.stroke}
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circumference}`}
          className="transition-all duration-700 ease-out"
        />
        {/* Center text */}
        <text
          x={center}
          y={center - 4}
          textAnchor="middle"
          className={`${config.fontSize} font-bold`}
          fill={color.stroke}
        >
          {probability}%
        </text>
      </svg>

      {/* Labels */}
      <p className={`mt-1 ${config.labelSize} text-slate-500`}>Approval Probability</p>
      {confInfo && (
        <p className={`${config.labelSize} font-medium ${confInfo.color}`}>
          {confInfo.label}
        </p>
      )}

      {/* Expandable details */}
      {expandable && hasDetails && (
        <div className="mt-3 w-full max-w-md">
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex w-full items-center justify-center gap-1 text-xs text-slate-500 hover:text-slate-700 transition-colors"
          >
            {expanded ? "Hide" : "Show"} risk factors
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>

          {expanded && (
            <div className="mt-3 space-y-3 text-sm">
              {/* Positive factors */}
              {positiveFactors.length > 0 && (
                <div className="space-y-1.5">
                  {positiveFactors.map((f, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2 rounded-md bg-green-50 px-3 py-2"
                    >
                      <span className="mt-0.5 shrink-0">✅</span>
                      <div>
                        <span className="font-medium text-green-800">
                          {f.name}{" "}
                          <span className="text-green-600">(+{f.impact}%)</span>
                        </span>
                        <p className="text-xs text-green-700 mt-0.5">{f.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Negative factors */}
              {negativeFactors.length > 0 && (
                <div className="space-y-1.5">
                  {negativeFactors.map((f, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2 rounded-md bg-amber-50 px-3 py-2"
                    >
                      <span className="mt-0.5 shrink-0">⚠️</span>
                      <div>
                        <span className="font-medium text-amber-800">
                          {f.name}{" "}
                          <span className="text-amber-600">({f.impact}%)</span>
                        </span>
                        <p className="text-xs text-amber-700 mt-0.5">{f.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Recommendation */}
              {recommendation && (
                <div className={`rounded-md ${color.bg} px-3 py-2 border border-slate-200`}>
                  <p className="text-xs font-medium text-slate-600 uppercase tracking-wide mb-1">
                    Recommendation
                  </p>
                  <p className="text-sm text-slate-800">{recommendation}</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
