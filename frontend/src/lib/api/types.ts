/** Domain types, all derived from the generated schema (never hand-written duplicates). */
import type { components } from "./schema";

type S = components["schemas"];
export type Me = S["Me"];
export type AuthResponse = S["AuthResponse"];
export type Role = NonNullable<Me["role"]>;
export type ApprovalStatus = NonNullable<S["RecruiterProfile"]["approvalStatus"]>;
export type RegisterRequest = S["RegisterRequest"];
