import { useState } from "react";

import { signIn, signUp, type AuthSession } from "../services/auth";

interface Props {
  onAuthenticated: (session: AuthSession) => void;
}

export function AuthScreen({ onAuthenticated }: Props) {
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!email.trim() || password.length < 6) return;
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      if (mode === "signin") {
        const session = await signIn(email.trim(), password);
        onAuthenticated(session);
      } else {
        const result = await signUp(email.trim(), password);
        if (result.session) onAuthenticated(result.session);
        else setMessage("Account created. Check your email to confirm it, then sign in.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-card">
        <div className="auth-brand"><span>🐾</span><div><h1>PawPredict</h1><p>Personalized routine tracking + potty prediction</p></div></div>
        <div className="auth-tabs">
          <button className={mode === "signin" ? "active" : ""} type="button" onClick={() => { setMode("signin"); setError(null); setMessage(null); }}>Sign in</button>
          <button className={mode === "signup" ? "active" : ""} type="button" onClick={() => { setMode("signup"); setError(null); setMessage(null); }}>Create account</button>
        </div>
        <form onSubmit={(event) => void submit(event)}>
          {message && <p className="success-message">{message}</p>}
          {error && <p className="event-error">{error}</p>}
          <label className="field-label">Email<input type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
          <label className="field-label">Password<input type="password" autoComplete={mode === "signin" ? "current-password" : "new-password"} minLength={6} value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
          <button className="save-button auth-submit" disabled={busy || !email.trim() || password.length < 6} type="submit">
            {busy ? "Working…" : mode === "signin" ? "Sign in" : "Create account"}
          </button>
        </form>
        <p className="auth-footnote">Each account only sees dogs and tracking data it owns.</p>
      </section>
    </main>
  );
}
