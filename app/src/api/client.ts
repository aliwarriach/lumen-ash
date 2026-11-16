import createClient, { type Middleware } from "openapi-fetch";

import { apiFetch } from "@/api/fetch";
import type { paths } from "@/api/schema";
import { env } from "@/lib/env";
import { supabase } from "@/lib/supabase";

// Attaches the current Supabase access token to every backend request.
const authMiddleware: Middleware = {
  async onRequest({ request }) {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (token) {
      request.headers.set("Authorization", `Bearer ${token}`);
    }
    return request;
  },
};

// Typed client generated from the backend's OpenAPI schema (`npm run gen:api`).
export const api = createClient<paths>({ baseUrl: env.apiUrl, fetch: (request) => apiFetch(request) });
api.use(authMiddleware);
