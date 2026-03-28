"use client";

import Link from "next/link";
import StatusBadge from "./StatusBadge";
import { Calendar, FileText } from "lucide-react";

interface PACardProps {
  id: string;
  patientId: string;
  cptCode: string;
  payerName: string;
  status: "draft" | "submitted" | "approved" | "denied" | "appealed" | "closed";
  approvalProbability: number;
  createdAt: string;
}

function getProbabilityColor(p: number): string {
  if (p < 40) return "text-red-600";
  if (p <= 70) return "text-yellow-600";
  return "text-green-600";
}

export default function PACard({
  id,
  patientId,
  cptCode,
  payerName,
  status,
  approvalProbability,
  createdAt,
}: PACardProps) {
  return (
    <Link
      href={`/pa/${id}`}
      className="card block transition-shadow hover:shadow-md"
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-semibold text-slate-900">
            Patient: {patientId}
          </p>
          <div className="mt-1 flex items-center gap-2 text-sm text-slate-500">
            <FileText size={14} />
            <span>CPT {cptCode}</span>
            <span className="text-slate-300">|</span>
            <span>{payerName}</span>
          </div>
        </div>
        <StatusBadge status={status} />
      </div>

      <div className="mt-4 flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-xs text-slate-400">
          <Calendar size={12} />
          <span>{new Date(createdAt).toLocaleDateString()}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-slate-500">Probability:</span>
          <span
            className={`text-sm font-bold ${getProbabilityColor(approvalProbability)}`}
          >
            {approvalProbability}%
          </span>
        </div>
      </div>
    </Link>
  );
}
