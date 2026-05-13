"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Building2, Eye, EyeOff, Lock, Mail, MapPin, User } from "lucide-react";
import { AuthLayout } from "../components/AuthLayout";
import { STORE_LOCATIONS, saveLocationForEmail, type StoreLocation } from "../utils/userLocation";

type RegisterResponse = {
  detail?: unknown;
};

type LocationsResponse = {
  locations?: StoreLocation[];
};

function normalizeLocationOption(location: StoreLocation): StoreLocation {
  return {
    ...location,
    label: location.label || `${location.city}, ${location.country}`,
  };
}

function passwordStrengthError(password: string) {
  if (password.length < 8) return "Use at least 8 characters.";
  if (!/[A-Z]/.test(password)) return "Use at least one uppercase letter.";
  if (!/[0-9]/.test(password)) return "Use at least one number.";
  if (!/[^A-Za-z0-9]/.test(password)) return "Use at least one special character.";
  return "";
}

function getRegisterErrorMessage(status: number, detail: unknown) {
  if (status === 409) return "This email is already registered.";
  if (Array.isArray(detail) && detail.length > 0) {
    const message = detail[0]?.msg;
    if (typeof message === "string") return message.replace(/^Value error,\s*/i, "");
  }
  if (typeof detail === "string") return detail;
  return "Could not create account. Please check your input and try again.";
}

export function Register() {
  const router = useRouter();
  const [form, setForm] = useState({ fullName: "", company: "", email: "", locationId: "", password: "", confirmPassword: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [locationOptions, setLocationOptions] = useState<StoreLocation[]>(STORE_LOCATIONS);
  const [locationsLoading, setLocationsLoading] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const update = (key: keyof typeof form, value: string) => setForm((current) => ({ ...current, [key]: value }));

  useEffect(() => {
    let isActive = true;

    async function loadLocations() {
      try {
        const response = await fetch("/api/auth/locations");
        const data = (await response.json().catch(() => ({}))) as LocationsResponse;

        if (!isActive) return;
        if (response.ok && Array.isArray(data.locations) && data.locations.length > 0) {
          setLocationOptions(data.locations.map(normalizeLocationOption));
        }
      } finally {
        if (isActive) setLocationsLoading(false);
      }
    }

    loadLocations();

    return () => {
      isActive = false;
    };
  }, []);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const nextErrors: Record<string, string> = {};

    if (!form.fullName.trim()) nextErrors.fullName = "Full name is required.";
    if (!form.company.trim()) nextErrors.company = "Company name is required.";
    if (!form.locationId.trim()) nextErrors.location = "Store location is required.";
    if (!form.email.trim()) nextErrors.email = "Email is required.";
    else if (!/^\S+@\S+\.\S+$/.test(form.email)) nextErrors.email = "Use a valid email address.";

    const passwordError = passwordStrengthError(form.password);
    if (passwordError) nextErrors.password = passwordError;
    if (form.confirmPassword !== form.password) nextErrors.confirmPassword = "Passwords do not match.";

    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    setSubmitting(true);

    try {
      const response = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: form.fullName.trim(),
          company: form.company.trim(),
          email: form.email.trim().toLowerCase(),
          password: form.password,
          location_id: form.locationId,
        }),
      });

      const data = (await response.json().catch(() => ({}))) as RegisterResponse;

      if (!response.ok) {
        setErrors({ form: getRegisterErrorMessage(response.status, data.detail) });
        return;
      }

      const selectedLocation = locationOptions.find((location) => location.location_id === form.locationId);
      saveLocationForEmail(form.email, selectedLocation?.city || selectedLocation?.label || form.locationId);
      localStorage.removeItem("auth_token");
      localStorage.removeItem("auth_user");
      router.push("/login?registered=1");
    } catch {
      setErrors({ form: "Network error. Please check that the backend is running." });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout eyebrow="Create workspace" title="Register RRParts access" subtitle="Set up a demo account for inventory monitoring and supplier planning.">
      {errors.form ? (
        <div className="mb-4 rounded-xl border border-red-300/20 bg-red-400/10 px-3 py-2 text-sm text-red-100">
          {errors.form}
        </div>
      ) : null}

      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <label className="form-field">
          <span>Full Name</span>
          <div className={`input-shell ${errors.fullName ? "input-error" : ""}`}>
            <User size={17} />
            <input value={form.fullName} onChange={(event) => update("fullName", event.target.value)} placeholder="Alex Ionescu" autoComplete="name" />
          </div>
          {errors.fullName ? <small>{errors.fullName}</small> : null}
        </label>

        <label className="form-field">
          <span>Company Name</span>
          <div className={`input-shell ${errors.company ? "input-error" : ""}`}>
            <Building2 size={17} />
            <input value={form.company} onChange={(event) => update("company", event.target.value)} placeholder="RRParts Demo Store" autoComplete="organization" />
          </div>
          {errors.company ? <small>{errors.company}</small> : null}
        </label>

        <label className="form-field">
          <span>Store Location</span>
          <div className={`input-shell ${errors.location ? "input-error" : ""}`}>
            <MapPin size={17} />
            <select value={form.locationId} onChange={(event) => update("locationId", event.target.value)} autoComplete="address-level2">
              <option value="">{locationsLoading ? "Loading locations..." : "Choose location"}</option>
              {locationOptions.map((location) => (
                <option key={location.location_id} value={location.location_id}>
                  {location.label}
                </option>
              ))}
            </select>
          </div>
          {errors.location ? <small>{errors.location}</small> : null}
        </label>

        <label className="form-field">
          <span>Email</span>
          <div className={`input-shell ${errors.email ? "input-error" : ""}`}>
            <Mail size={17} />
            <input value={form.email} onChange={(event) => update("email", event.target.value)} type="email" placeholder="manager@rrparts.com" autoComplete="email" />
          </div>
          {errors.email ? <small>{errors.email}</small> : null}
        </label>

        <label className="form-field">
          <span>Password</span>
          <div className={`input-shell ${errors.password ? "input-error" : ""}`}>
            <Lock size={17} />
            <input value={form.password} onChange={(event) => update("password", event.target.value)} type={showPassword ? "text" : "password"} placeholder="Password" autoComplete="new-password" />
            <button type="button" className="password-toggle" onClick={() => setShowPassword((current) => !current)} aria-label={showPassword ? "Hide password" : "Show password"}>
              {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
            </button>
          </div>
          {errors.password ? <small>{errors.password}</small> : null}
        </label>

        <label className="form-field">
          <span>Confirm Password</span>
          <div className={`input-shell ${errors.confirmPassword ? "input-error" : ""}`}>
            <Lock size={17} />
            <input value={form.confirmPassword} onChange={(event) => update("confirmPassword", event.target.value)} type={showConfirmPassword ? "text" : "password"} placeholder="Confirm" autoComplete="new-password" />
            <button type="button" className="password-toggle" onClick={() => setShowConfirmPassword((current) => !current)} aria-label={showConfirmPassword ? "Hide password" : "Show password"}>
              {showConfirmPassword ? <EyeOff size={17} /> : <Eye size={17} />}
            </button>
          </div>
          {errors.confirmPassword ? <small>{errors.confirmPassword}</small> : null}
        </label>

        <button className="primary-button w-full disabled:cursor-not-allowed disabled:opacity-65" type="submit" disabled={submitting}>
          {submitting ? "Creating account..." : "Create Account"}
          <ArrowRight size={17} />
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-slate-400">
        Already have an account? <Link className="font-semibold text-orange-300 transition hover:text-orange-200" href="/login">Sign in</Link>
      </p>
    </AuthLayout>
  );
}
