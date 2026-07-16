import { Hono } from "hono";
import { cors } from "hono/cors";
import type { AppEnv } from "./env";
import { createDb } from "./db/client";
import auth from "./routes/auth";
import photos from "./routes/photos";
import social from "./routes/social";
import internal from "./routes/internal";

const app = new Hono<AppEnv>();

app.use("*", cors({
  origin: "*",
  allowMethods: ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
  allowHeaders: ["*"],
  credentials: true,
}));

const apiV1 = new Hono<AppEnv>();
apiV1.use("*", cors({
  origin: "*",
  allowMethods: ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
  allowHeaders: ["*"],
  credentials: true,
}));

apiV1.get("/health", async (c) => {
  const sql = createDb(c.env);
  try {
    await sql`SELECT 1`;
    return c.json({ status: "ok", service: "tagr-api-worker" });
  } catch (error) {
    return c.json({
      status: "degraded",
      service: "tagr-api-worker",
      database: error instanceof Error ? error.message : "unknown error",
    }, 503);
  } finally {
    await sql.end({ timeout: 5 });
  }
});

apiV1.route("/auth", auth);
apiV1.route("/photos", photos);
apiV1.route("/internal", internal);
apiV1.route("/", social);

app.route("/api/v1", apiV1);

app.get("/api/v1/docs", (c) => {
  return c.redirect("/api/v1/health");
});

app.all("*", async (c) => {
  if (c.req.path.startsWith("/api/")) {
    return c.json({ detail: "Not found" }, 404);
  }
  return c.env.ASSETS.fetch(c.req.raw);
});

export default app;
export { PhotoBatcher } from "./batcher";
