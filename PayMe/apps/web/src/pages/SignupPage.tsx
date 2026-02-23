import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useApp } from "../context/AppContext";
import { apiFetch } from "../api";

const US_STATES = [
  "AL","AK","AZ","AR","CA","CO","CT","DC","DE","FL","GA","HI","ID","IL","IN",
  "IA","KS","KY","LA","MA","MD","ME","MI","MN","MO","MS","MT","NC","ND","NE",
  "NH","NJ","NM","NV","NY","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT",
  "VA","VT","WA","WI","WV","WY",
];

const STEP_LABELS = ["Account", "About You", "Gmail", "Bank", "Matches"];

function WizardSteps({ step }: { step: number }) {
  return (
    <div className="wizard-steps">
      {STEP_LABELS.map((label, i) => {
        const n = i + 1;
        const cls = n === step ? "active" : n < step ? "done" : "";
        return (
          <span key={n} style={{ display: "contents" }}>
            {i > 0 && <div className="wizard-connector" />}
            <div className={`wizard-step ${cls}`}>
              <div className="wizard-step-dot">{n}</div>
              <div className="wizard-step-label">{label}</div>
            </div>
          </span>
        );
      })}
    </div>
  );
}

export function SignupPage() {
  const [step, setStep] = useState<1 | 2 | 3 | 4 | 5>(1);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [userState, setUserState] = useState("");
  const [dob, setDob] = useState("");
  const [gender, setGender] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const { signup, refreshUser, user, initiateGmailOAuth, gmailOAuthPending, initiatePlaidLink } = useApp();

  const handleConnectPlaid = async () => {
    setError("");
    try {
      await initiatePlaidLink();
    } catch (err) {
      setError((err as Error).message);
    }
  };
  const navigate = useNavigate();

  const submitAccount = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await signup(username, email, password);
      setStep(2);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const submitOnboarding = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await apiFetch("/onboarding", {
        method: "POST",
        body: JSON.stringify({
          first_name: firstName,
          last_name: lastName,
          state: userState,
          dob,
          gender: gender || null,
          brands_purchased: [],
        }),
      });
      await refreshUser();
      setStep(3);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (step !== 5) return;
    let cancelled = false;
    apiFetch("/match/run", { method: "POST" }).then(() => {
      if (!cancelled) navigate("/");
    });
    return () => { cancelled = true; };
  }, [step, navigate]);

  return (
    <main className="auth-wrap">
      <section className="auth-panel">
        <WizardSteps step={step} />

        {step === 1 && (
          <>
            <h1>Create your account</h1>
            <p className="muted">Get ranked matches and track your claims in one place.</p>
            <form className="auth-form" onSubmit={submitAccount}>
              <input placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} />
              <input placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
              <input placeholder="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
              <button type="submit" disabled={loading}>
                {loading ? "Creating account..." : "Create account"}
              </button>
            </form>
            {error && <p className="error">{error}</p>}
            <p className="muted">
              Already have an account? <Link to="/login">Log in</Link>
            </p>
          </>
        )}

        {step === 2 && (
          <>
            <h1>About You</h1>
            <p className="muted">Help us find your best matches.</p>
            <form className="auth-form" onSubmit={submitOnboarding}>
              <input placeholder="First name" value={firstName} onChange={(e) => setFirstName(e.target.value)} />
              <input placeholder="Last name" value={lastName} onChange={(e) => setLastName(e.target.value)} />
              <select value={userState} onChange={(e) => setUserState(e.target.value)}>
                <option value="">Select state</option>
                {US_STATES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
              <input type="date" placeholder="Date of birth" value={dob} onChange={(e) => setDob(e.target.value)} />
              <select value={gender} onChange={(e) => setGender(e.target.value)}>
                <option value="">Gender (optional)</option>
                <option value="M">M</option>
                <option value="F">F</option>
                <option value="Other">Other</option>
                <option value="Prefer not to say">Prefer not to say</option>
              </select>
              <button type="submit" disabled={loading}>
                {loading ? "Saving..." : "Continue"}
              </button>
            </form>
            {error && <p className="error">{error}</p>}
          </>
        )}

        {step === 3 && (
          <>
            <h1>Connect Gmail</h1>
            <div className="integration-card">
              <div className="int-icon">✉️</div>
              <div className="int-body">
                <h3>Connect Gmail</h3>
                <p>We scan for settlement notification emails to improve your match accuracy.</p>
                {user?.gmail_oauth_connected ? (
                  <span className="connected-badge">✓ Connected</span>
                ) : (
                  <button onClick={() => initiateGmailOAuth()} disabled={gmailOAuthPending}>
                    {gmailOAuthPending ? "Connecting..." : "Connect Gmail"}
                  </button>
                )}
              </div>
            </div>
            {user?.gmail_oauth_connected ? (
              <button onClick={() => setStep(4)}>Continue →</button>
            ) : (
              <button className="link-btn" onClick={() => setStep(4)}>Skip →</button>
            )}
          </>
        )}

        {step === 4 && (
          <>
            <h1>Connect Bank</h1>
            <div className="integration-card">
              <div className="int-icon">🏦</div>
              <div className="int-body">
                <h3>Connect Bank Account</h3>
                <p>Link your bank to detect settlement-relevant transactions automatically.</p>
                {user?.plaid_linked ? (
                  <span className="connected-badge">✓ Connected</span>
                ) : (
                  <button onClick={handleConnectPlaid}>Connect Bank</button>
                )}
              </div>
            </div>
            {user?.plaid_linked ? (
              <button onClick={() => setStep(5)}>Continue →</button>
            ) : (
              <button className="link-btn" onClick={() => setStep(5)}>Skip →</button>
            )}
          </>
        )}

        {step === 5 && (
          <>
            <h1>Finding your matches</h1>
            <p className="muted">Running your first match...</p>
            <div className="spinner" />
          </>
        )}
      </section>
    </main>
  );
}
