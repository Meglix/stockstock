export type StoreLocation = {
  location_id: string;
  city: string;
  country: string;
  country_code: string;
  label: string;
};

export const STORE_LOCATIONS: StoreLocation[] = [
  { location_id: "FI_HEL", city: "Helsinki", country: "Finland", country_code: "FI", label: "Helsinki, Finland" },
  { location_id: "SE_STO", city: "Stockholm", country: "Sweden", country_code: "SE", label: "Stockholm, Sweden" },
  { location_id: "EE_TLL", city: "Tallinn", country: "Estonia", country_code: "EE", label: "Tallinn, Estonia" },
  { location_id: "DK_CPH", city: "Copenhagen", country: "Denmark", country_code: "DK", label: "Copenhagen, Denmark" },
  { location_id: "DE_BER", city: "Berlin", country: "Germany", country_code: "DE", label: "Berlin, Germany" },
  { location_id: "PL_WAW", city: "Warsaw", country: "Poland", country_code: "PL", label: "Warsaw, Poland" },
  { location_id: "CZ_PRG", city: "Prague", country: "Czechia", country_code: "CZ", label: "Prague, Czechia" },
  { location_id: "NL_AMS", city: "Amsterdam", country: "Netherlands", country_code: "NL", label: "Amsterdam, Netherlands" },
  { location_id: "FR_PAR", city: "Paris", country: "France", country_code: "FR", label: "Paris, France" },
  { location_id: "IT_MIL", city: "Milan", country: "Italy", country_code: "IT", label: "Milan, Italy" },
  { location_id: "ES_MAD", city: "Madrid", country: "Spain", country_code: "ES", label: "Madrid, Spain" },
  { location_id: "RO_BUC", city: "Bucharest", country: "Romania", country_code: "RO", label: "Bucharest, Romania" },
];

const LOCATION_STORAGE_KEY = "rrparts_location_by_email";

type UserWithLocation = {
  email?: string | null;
  location_id?: string | null;
  location?: string | null;
  user_location_ids?: string[] | null;
  user_locations?: string[] | null;
};

function locationDisplayName(value?: string | null) {
  const normalized = value?.trim();
  if (!normalized) return undefined;

  const match = STORE_LOCATIONS.find((location) => location.location_id === normalized || location.city === normalized);
  return match?.city || normalized;
}

function readLocationMap(): Record<string, string> {
  if (typeof window === "undefined") return {};

  try {
    const raw = window.localStorage.getItem(LOCATION_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Record<string, string>) : {};
  } catch {
    return {};
  }
}

export function saveLocationForEmail(email: string, location: string) {
  if (typeof window === "undefined") return;

  const normalizedEmail = email.trim().toLowerCase();
  if (!normalizedEmail || !location.trim()) return;

  const locations = readLocationMap();
  locations[normalizedEmail] = location.trim();
  window.localStorage.setItem(LOCATION_STORAGE_KEY, JSON.stringify(locations));
}

export function readLocationForEmail(email?: string | null) {
  if (!email) return undefined;
  return readLocationMap()[email.trim().toLowerCase()];
}

export function mergeStoredLocation<T extends UserWithLocation>(user: T): T & { location?: string | null } {
  const location =
    locationDisplayName(user.location) ||
    locationDisplayName(user.location_id) ||
    locationDisplayName(user.user_locations?.find(Boolean)) ||
    locationDisplayName(user.user_location_ids?.find(Boolean)) ||
    readLocationForEmail(user.email);
  return location ? { ...user, location } : user;
}

export function readCurrentUserLocation(fallback = "My Store") {
  if (typeof window === "undefined") return fallback;

  try {
    const user = JSON.parse(window.localStorage.getItem("auth_user") || "{}") as UserWithLocation & { company?: string | null };
    return (
      locationDisplayName(user.location) ||
      locationDisplayName(user.location_id) ||
      locationDisplayName(user.user_locations?.find(Boolean)) ||
      locationDisplayName(user.user_location_ids?.find(Boolean)) ||
      user.company?.trim() ||
      fallback
    );
  } catch {
    return fallback;
  }
}
