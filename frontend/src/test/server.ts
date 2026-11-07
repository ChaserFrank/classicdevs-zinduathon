import { setupServer } from "msw/node";

/** One MSW server for all unit tests; each test adds the handlers it needs with server.use(). */
export const server = setupServer();
export const API = "http://localhost:8000/api/v1";
