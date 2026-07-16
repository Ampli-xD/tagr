import { jwtVerify } from "jose";
import { createMiddleware } from "hono/factory";
import type { AppEnv } from "../env";

export async function getUserIdFromToken(
  token: string,
  jwtSecret: string,
): Promise<string> {
  const secret = new TextEncoder().encode(jwtSecret);
  const { payload } = await jwtVerify(token, secret, {
    algorithms: ["HS256"],
  });

  const userId = payload.user_id;
  if (typeof userId !== "string" || !userId) {
    throw new Error("Invalid token payload");
  }

  return userId;
}

export const requireAuth = createMiddleware<AppEnv>(async (c, next) => {
  const header = c.req.header("Authorization");
  if (!header?.startsWith("Bearer ")) {
    return c.json({ detail: "Could not validate credentials" }, 401);
  }

  const token = header.slice("Bearer ".length);
  try {
    const userId = await getUserIdFromToken(token, c.env.JWT_SECRET);
    c.set("userId", userId);
    await next();
  } catch {
    return c.json({ detail: "Could not validate credentials" }, 401);
  }
});

declare module "hono" {
  interface ContextVariableMap {
    userId: string;
  }
}
