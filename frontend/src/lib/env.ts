/** Build-time configuration (frontend .env.example). Read once here, not inline in JSX. */
export const env = {
  apiBaseUrl: (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1").replace(/\/$/, ""),
  appUrl: import.meta.env.VITE_APP_URL ?? "http://localhost:5173",
  djangoAdminUrl: import.meta.env.VITE_DJANGO_ADMIN_URL ?? "http://localhost:8000/django-admin/",
  apiDocsUrl: import.meta.env.VITE_API_DOCS_URL ?? "http://localhost:8000/api/v1/docs/",
  isDev: import.meta.env.DEV,
  includeDevRoutes: import.meta.env.DEV || import.meta.env.MODE === "test",
};
