import postgres from "postgres";
import type { Env } from "../env";

export function createDb(env: Env) {
  return postgres(env.DATABASE_URL, {
    max: 1,
    idle_timeout: 20,
    connect_timeout: 10,
  });
}

export type Sql = ReturnType<typeof createDb>;
