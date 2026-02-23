import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../api";
import { AppShell } from "../components/AppShell";
import { useApp } from "../context/AppContext";

const BRANDS = ["Amazon", "Uber", "AT&T", "Paramount", "Meta", "Coca-Cola", "TikTok", "Poppy", "Walmart"];

export function OnboardingPage() {
  const navigate = useNavigate();
  const { user } = useApp();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [state, setState] = useState("NY");
  const [dob, setDob] = useState("1990-01-01");
  const [brands, setBrands] = useState<string[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (user?.first_name) navigate("/");
  }, [user]);

  const toggleBrand = (brand: string) => {
    setBrands((curr) => (curr.includes(brand) ? curr.filter((b) => b !== brand) : [...curr, brand]));
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await apiFetch("/onboarding", {
        method: "POST",
        body: JSON.stringify({
          first_name: firstName,
          last_name: lastName,
          state,
          dob,
          brands_purchased: brands,
        }),
      });
      await apiFetch("/match/run", { method: "POST" });
      navigate("/");
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
        <form className="stack" onSubmit={submit}>
          <div className="form-grid">
            <input placeholder="First name" value={firstName} onChange={(e) => setFirstName(e.target.value)} />
            <input placeholder="Last name" value={lastName} onChange={(e) => setLastName(e.target.value)} />
            <input placeholder="State" value={state} onChange={(e) => setState(e.target.value)} />
            <input type="date" value={dob} onChange={(e) => setDob(e.target.value)} />
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
        {error ? <p className="error">{error}</p> : null}
      </section>
    </AppShell>
  );
}
