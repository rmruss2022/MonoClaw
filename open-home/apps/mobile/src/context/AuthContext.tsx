import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import * as client from "@/api/client";

type Status = "loading" | "signedIn" | "signedOut" | "noHome";

interface AuthValue {
  status: Status;
  controlPlane: string;
  email: string | null;
  signIn: (email: string, password: string) => Promise<"ok" | "no_home" | "bad" | "error">;
  signOut: () => Promise<void>;
  setControlPlane: (url: string) => Promise<void>;
  /** Call when a hub request 401s and can't refresh — bounce to sign-in. */
  expire: () => void;
}

const Ctx = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<Status>("loading");
  const [controlPlane, setCP] = useState<string>(client.DEFAULT_CONTROL_PLANE);
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      await client.loadSession();
      setCP(client.getControlPlane());
      setEmail(client.getEmail());
      if (!client.hasSession()) {
        setStatus("signedOut");
        return;
      }
      // Have a control-plane session — confirm we can reach the house.
      try {
        if (await client.ensureHome()) {
          await client.api("/health"); // hub reachable with the grant
          setStatus("signedIn");
        } else {
          setStatus("noHome");
        }
      } catch {
        setStatus("signedOut");
      }
    })();
  }, []);

  const signIn = useCallback(async (mail: string, password: string) => {
    const r = await client.login(mail, password);
    if (r === "ok") {
      setEmail(client.getEmail());
      setStatus("signedIn");
    } else if (r === "no_home") {
      setEmail(client.getEmail());
      setStatus("noHome");
    }
    return r;
  }, []);

  const signOut = useCallback(async () => {
    await client.logout();
    setEmail(null);
    setStatus("signedOut");
  }, []);

  const setControlPlane = useCallback(async (url: string) => {
    await client.setControlPlane(url);
    setCP(client.getControlPlane());
  }, []);

  const expire = useCallback(() => setStatus("signedOut"), []);

  return (
    <Ctx.Provider value={{ status, controlPlane, email, signIn, signOut, setControlPlane, expire }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAuth(): AuthValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth must be used within AuthProvider");
  return v;
}
