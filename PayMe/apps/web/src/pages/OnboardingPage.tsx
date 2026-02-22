import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../api";

const BRANDS = ["Amazon", "Uber", "AT&T", "Paramount", "Meta", "Coca-Cola", "TikTok", "Poppy", "Walmart"];

export function OnboardingPage() {
  const navigate = useNavigate();
  const [stage, setStage] = useState<"profile" | "sync">("profile");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [state, setState] = useState("NY");
  const [dob, setDob] = useState("1990-01-01");
  const [brands, setBrands] = useState<string[]>([]);
  const [payoutType, setPayoutType] = useState("venmo");
  const [payoutValue, setPayoutValue] = useState("");
  const [frequency, setFrequency] = useState("weekly");
  const [gmailSynced, setGmailSynced] = useState(false);
  const [bankSynced, setBankSynced] = useState(false);
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
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSyncing(null);
    }
  };

  const continueToMatches = async () => {
    setError("");
    await apiFetch("/match/run", { method: "POST" });
    navigate("/matches");
  };

  return (
    <main>
      <h1>Onboarding</h1>
      {stage === "profile" ? (
        <form onSubmit={submit}>
          <input placeholder="First name" value={firstName} onChange={(e) => setFirstName(e.target.value)} />
          <input placeholder="Last name" value={lastName} onChange={(e) => setLastName(e.target.value)} />
          <input placeholder="State" value={state} onChange={(e) => setState(e.target.value)} />
          <input type="date" value={dob} onChange={(e) => setDob(e.target.value)} />
          <div>
            {BRANDS.map((brand) => (
              <label key={brand} style={{ marginRight: 12 }}>
                <input type="checkbox" checked={brands.includes(brand)} onChange={() => toggleBrand(brand)} />
                {brand}
              </label>
            ))}
          </div>
          <input placeholder="Payout type" value={payoutType} onChange={(e) => setPayoutType(e.target.value)} />
          <input placeholder="Payout value" value={payoutValue} onChange={(e) => setPayoutValue(e.target.value)} />
          <input placeholder="Finance check frequency" value={frequency} onChange={(e) => setFrequency(e.target.value)} />
          <button type="submit">Finish onboarding</button>
        </form>
      ) : (
        <section>
          <p>Connect Gmail and bank before first matching, or skip with lower confidence.</p>
          <button onClick={runGmailSync} disabled={syncing !== null || gmailSynced}>
            {gmailSynced ? "Gmail Connected" : syncing === "gmail" ? "Connecting Gmail..." : "Connect Gmail"}
          </button>
          <button onClick={runBankSync} disabled={syncing !== null || bankSynced} style={{ marginLeft: 8 }}>
            {bankSynced ? "Bank Connected" : syncing === "bank" ? "Connecting Bank..." : "Connect Bank"}
          </button>
          <button onClick={() => setSkipped(true)} style={{ marginLeft: 8 }}>Skip for now</button>
          <div style={{ marginTop: 12 }}>
            <button onClick={continueToMatches} disabled={!(skipped || (gmailSynced && bankSynced))}>
              Run first match
            </button>
          </div>
        </section>
      )}
      {error && <p>{error}</p>}
    </main>
  );
}
