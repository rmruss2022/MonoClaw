import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { apiFetch } from "../api";

type Detail = {
  id: string;
  title: string;
  summary_text: string;
  eligibility_text: string;
  status: string;
  claim_url: string;
};

export function SettlementDetailPage() {
  const { id } = useParams();
  const [detail, setDetail] = useState<Detail | null>(null);

  useEffect(() => {
    apiFetch<Detail>(`/settlements/${id}`).then(setDetail);
  }, [id]);

  if (!detail) return <main>Loading settlement...</main>;
  return (
    <main>
      <h1>{detail.title}</h1>
      <p>{detail.summary_text}</p>
      <p>{detail.eligibility_text}</p>
      <a href={detail.claim_url} target="_blank">Claim</a>
    </main>
  );
}
