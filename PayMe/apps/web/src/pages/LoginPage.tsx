import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiFetch } from "../api";

export function LoginPage() {
  const [usernameOrEmail, setUsernameOrEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const res = await apiFetch<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ username_or_email: usernameOrEmail, password })
      });
      localStorage.setItem("token", res.access_token);
      navigate("/matches");
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <main>
      <h1>Log in</h1>
      <form onSubmit={submit}>
        <input placeholder="Username or email" value={usernameOrEmail} onChange={(e) => setUsernameOrEmail(e.target.value)} />
        <input placeholder="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <button type="submit">Log in</button>
      </form>
      {error && <p>{error}</p>}
      <Link to="/signup">Need an account?</Link>
    </main>
  );
}
