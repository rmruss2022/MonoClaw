import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../api";
import { AppShell } from "../components/AppShell";
import { useApp } from "../context/AppContext";

const BRANDS = ["Amazon", "Uber", "AT&T", "Paramount", "Meta", "Coca-Cola", "TikTok", "Poppy", "Walmart"];

export function OnboardingPage() {
  const navigate = useNavigate();
  const { user, refreshUser } = useApp();
  const [stage, setStage] = useState<"profile" | "sync">("profile");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [state, setState] = useState("NY");
  const [dob, setDob] = useState("1990-01-01");
  const [brands, setBrands] = useState<string[]>([]);
  const [payoutType, setPayoutType] = useState("venmo");
  const [payoutValue, setPayoutValue] = useState("");
  const [frequency, setFrequency] = useState("weekly");
  const [gmailSynced, setGmailSynced] = useState(Boolean(user?.gmail_synced_at));
  const [bankSynced, setBankSynced] = useState(Boolean(user?.plaid_synced_at));
  const [skipped, setSkipped] = useState(false);
  const [syncing, setSyncing] = useState<null | "gmail" | "bank">(null);
  const [error, setError] = useState("");

  const toggleBrand = (brand: string) => {
    setBrands((curr) => (curr.includes(brand) ? curr.filter((b) => b !== brand) : [...curr, brand]));
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    await apiFetch("/onboarding", {
      method: "POST",
      body: JSON.stringify({
        first_name: firstName,
        last_name: lastName,
        state,
        dob,
        brands_purchased: brands,
        payout_preference_type: payoutType,
        payout_preference_value: payoutValue,
        finance_check_frequency: frequency
      })
    });
    setStage("sync");
  };

  const runGmailSync = async () => {
    setError("");
    setSyncing("gmail");
    try {
      await apiFetch("/integrations/gmail/sync", { method: "POST" });
      setGmailSynced(true);
      await refreshUser();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSyncing(null);
    }
  };

  const runBankSync = async () => {
    setError("");
    setSyncing("bank");
    try {
      await apiFetch("/integrations/plaid/sync", { method: "POST" });
      setBankSynced(true);
      await refreshUser();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSyncing(null);
    }
  };

  const continueToMatches = async () => {
    setError("");
    try {
      await apiFetch("/match/run", { method: "POST" });
      navigate("/matches");
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <AppShell
      title="Personalize your eligibility graph"
      subtitle="We use onboarding and sync evidence to produce fast, explainable match ranking."
    >
      <section className="panel stack">
        {stage === "profile" ? (
          <form className="stack" onSubmit={submit}>
            <div className="form-grid">
              <input placeholder="First name" value={firstName} onChange={(e) => setFirstName(e.target.value)} />
              <input placeholder="Last name" value={lastName} onChange={(e) => setLastName(e.target.value)} />
              <input placeholder="State" value={state} onChange={(e) => setState(e.target.value)} />
              <input type="date" value={dob} onChange={(e) => setDob(e.target.value)} />
              <input placeholder="Payout type" value={payoutType} onChange={(e) => setPayoutType(e.target.value)} />
              <input
                placeholder="Payout value"
                value={payoutValue}
                onChange={(e) => setPayoutValue(e.target.value)}
              />
              <input
                placeholder="Finance check frequency"
                value={frequency}
                onChange={(e) => setFrequency(e.target.value)}
              />
            </div>
            <div>
              <p className="muted">Brands purchased</p>
              <div className="chips">
                {BRANDS.map((brand) => (
                  <button
                    key={brand}
                    type="button"
                    className={`chip ${brands.includes(brand) ? "active" : ""}`}
                    onClick={() => toggleBrand(brand)}
                  >
                    {brand}
                  </button>
                ))}
              </div>
            </div>
            <button type="submit">Finish onboarding</button>
          </form>
        ) : (
          <section className="stack">
            <p className="muted">
              Connect Gmail and bank for stronger confidence signals before your first matching run.
            </p>
            <div className="toolbar">
              {!gmailSynced ? (
                <button onClick={runGmailSync} disabled={syncing !== null}>
                  {syncing === "gmail" ? "Connecting Gmail..." : "Connect Gmail"}
                </button>
              ) : null}
              {!bankSynced ? (
                <button onClick={runBankSync} disabled={syncing !== null}>
                  {syncing === "bank" ? "Connecting Bank..." : "Connect Bank"}
                </button>
              ) : null}
              <button className="ghost-btn" onClick={() => setSkipped(true)}>
                Skip for now
              </button>
            </div>
            <button onClick={continueToMatches} disabled={!(skipped || (gmailSynced && bankSynced))}>
              Run first match
            </button>
          </section>
        )}
        {error ? <p className="error">{error}</p> : null}
      </section>
    </AppShell>
  );
}
