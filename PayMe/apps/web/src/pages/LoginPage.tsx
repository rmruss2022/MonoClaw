import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useApp } from "../context/AppContext";

export function LoginPage() {
  const [usernameOrEmail, setUsernameOrEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useApp();
  const navigate = useNavigate();

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(usernameOrEmail, password);
      navigate("/matches");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="auth-wrap">
      <section className="auth-panel">
        <h1>Welcome back</h1>
        <p className="muted">Sign in to continue reviewing and pinning your settlement matches.</p>
        <form className="auth-form" onSubmit={submit}>
          <input
            placeholder="Username or email"
            value={usernameOrEmail}
            onChange={(e) => setUsernameOrEmail(e.target.value)}
          />
          <input
            placeholder="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <button type="submit" disabled={loading}>
            {loading ? "Signing in..." : "Log in"}
          </button>
        </form>
        {error ? <p className="error">{error}</p> : null}
        <p className="muted">
          No account yet? <Link to="/signup">Create one</Link>
        </p>
      </section>
    </main>
  );
}
