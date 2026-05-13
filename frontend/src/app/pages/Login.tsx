"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Eye, EyeOff, Lock, Mail } from "lucide-react";
import { AuthLayout } from "../components/AuthLayout";
import { mergeStoredLocation } from "../utils/userLocation";

type AuthResponse = {
  access_token?: string;
  token_type?: string;
  user?: {
    id: number;
    username: string;
    full_name?: string | null;
    company?: string | null;
    location?: string | null;
    email: string;
    role: string;
  };
  detail?: unknown;
};

function getLoginErrorMessage(status: number, detail: unknown) {
  if (status === 401) return "Email or password is incorrect.";
  if (status === 403) return "This account is inactive.";
  if (typeof detail === "string") return detail;
  return "Could not sign in. Please try again.";
}

export function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("registered") === "1") {
      setNotice("Account created successfully. Please sign in.");
    }
  }, []);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const nextErrors: Record<string, string> = {};

    if (!email.trim()) nextErrors.email = "Email is required.";
    else if (!/^\S+@\S+\.\S+$/.test(email)) nextErrors.email = "Use a valid email address.";
    if (!password) nextErrors.password = "Password is required.";

    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    setSubmitting(true);
    setNotice("");

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          password,
        }),
      });

      const data = (await response.json().catch(() => ({}))) as AuthResponse;

      if (!response.ok || !data.access_token || !data.user) {
        setErrors({ form: getLoginErrorMessage(response.status, data.detail) });
        return;
      }

      const user = mergeStoredLocation(data.user);
      localStorage.setItem("auth_token", data.access_token);
      localStorage.setItem("auth_user", JSON.stringify(user));
      router.push("/dashboard");
    } catch {
      setErrors({ form: "Network error. Please check that the backend is running." });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout eyebrow="Secure access" title="Welcome back" subtitle="Sign in to continue to the RRParts inventory command center.">
      {notice ? (
        <div className="mb-4 rounded-xl border border-emerald-300/20 bg-emerald-400/10 px-3 py-2 text-sm text-emerald-100">
          {notice}
        </div>
      ) : null}

      {errors.form ? (
        <div className="mb-4 rounded-xl border border-red-300/20 bg-red-400/10 px-3 py-2 text-sm text-red-100">
          {errors.form}
        </div>
      ) : null}

      <form onSubmit={handleSubmit} className="space-y-5" noValidate>
        <label className="form-field">
          <span>Email</span>
          <div className={`input-shell ${errors.email ? "input-error" : ""}`}>
            <Mail size={17} />
            <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" placeholder="manager@rrparts.com" autoComplete="email" />
          </div>
          {errors.email ? <small>{errors.email}</small> : null}
        </label>

        <label className="form-field">
          <span>Password</span>
          <div className={`input-shell ${errors.password ? "input-error" : ""}`}>
            <Lock size={17} />
            <input value={password} onChange={(event) => setPassword(event.target.value)} type={showPassword ? "text" : "password"} placeholder="Enter password" autoComplete="current-password" />
            <button type="button" className="password-toggle" onClick={() => setShowPassword((current) => !current)} aria-label={showPassword ? "Hide password" : "Show password"}>
              {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
            </button>
          </div>
          {errors.password ? <small>{errors.password}</small> : null}
        </label>

        <button className="primary-button w-full disabled:cursor-not-allowed disabled:opacity-65" type="submit" disabled={submitting}>
          {submitting ? "Signing in..." : "Sign In"}
          <ArrowRight size={17} />
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-slate-400">
        New to RRParts? <Link className="font-semibold text-orange-300 transition hover:text-orange-200" href="/register">Create an account</Link>
      </p>
    </AuthLayout>
  );
}
