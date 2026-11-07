import { useQuery } from "@tanstack/react-query";

import { api, unwrap } from "./client";
import { qk } from "./query-keys";

export function useHealth() {
  return useQuery({
    queryKey: qk.health,
    queryFn: () => unwrap(api.GET("/api/v1/health")),
    retry: false,
    staleTime: 15_000,
  });
}
