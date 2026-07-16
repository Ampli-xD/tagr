import { Hono } from "hono";
import { SignJWT } from "jose";
import type { AppEnv } from "../env";
import { createDb } from "../db/client";
import { requireAuth } from "../middleware/auth";
import { uploadImage, getImageUrl } from "../storage";

const auth = new Hono<AppEnv>();

async function createAccessToken(userId: string, jwtSecret: string): Promise<string> {
  const secret = new TextEncoder().encode(jwtSecret);
  return new SignJWT({ user_id: userId })
    .setProtectedHeader({ alg: "HS256" })
    .setExpirationTime("7d")
    .sign(secret);
}

function formField(body: Record<string, unknown>, key: string): string {
  const value = body[key];
  if (typeof value !== "string" || !value) {
    throw new Error(`Missing field: ${key}`);
  }
  return value;
}

auth.post("/register", async (c) => {
  const body = await c.req.parseBody();
  const mobileNumber = formField(body, "mobile_number");
  const username = formField(body, "username");

  const sql = createDb(c.env);
  try {
    const existing = await sql`
      SELECT id FROM users
      WHERE mobile_number = ${mobileNumber} OR username = ${username}
      LIMIT 1
    `;
    if (existing.length > 0) {
      return c.json({ detail: "Username or Mobile number already registered" }, 400);
    }

    const users = await sql`
      INSERT INTO users (mobile_number, username, is_verified)
      VALUES (${mobileNumber}, ${username}, false)
      RETURNING id
    `;
    const userId = users[0].id as string;

    const expiresAt = new Date(Date.now() + 5 * 60 * 1000).toISOString();
    const otpCode = "123456";

    await sql`
      INSERT INTO otp_requests (mobile_number, otp_code, expires_at)
      VALUES (${mobileNumber}, ${otpCode}, ${expiresAt}::timestamptz)
    `;

    console.log(
      `--- MOCK OTP --- Sent OTP ${otpCode} to ${mobileNumber} (expires in 5 minutes)`,
    );

    return c.json({ user_id: userId, otp_sent: true });
  } finally {
    await sql.end({ timeout: 5 });
  }
});

auth.post("/verify-otp", async (c) => {
  const body = await c.req.parseBody();
  const mobileNumber = formField(body, "mobile_number");
  const otp = formField(body, "otp");

  const sql = createDb(c.env);
  try {
    const otpRows = await sql`
      SELECT id, otp_code, verified, expires_at
      FROM otp_requests
      WHERE mobile_number = ${mobileNumber}
      ORDER BY created_at DESC
      LIMIT 1
    `;

    const otpReq = otpRows[0];
    if (
      !otpReq ||
      otpReq.otp_code !== otp ||
      otpReq.verified ||
      new Date(otpReq.expires_at as string) < new Date()
    ) {
      return c.json({ detail: "Invalid, expired or already verified OTP" }, 400);
    }

    await sql`
      UPDATE otp_requests SET verified = true WHERE id = ${otpReq.id}
    `;

    const users = await sql`
      UPDATE users SET is_verified = true
      WHERE mobile_number = ${mobileNumber}
      RETURNING id
    `;

    if (users.length === 0) {
      return c.json({ detail: "User not found" }, 404);
    }

    const token = await createAccessToken(users[0].id as string, c.env.JWT_SECRET);
    return c.json({ verified: true, token });
  } finally {
    await sql.end({ timeout: 5 });
  }
});

auth.post("/enroll-face", async (c) => {
  const body = await c.req.parseBody();
  const userId = formField(body, "user_id");
  const image = body.image;

  if (!(image instanceof File)) {
    return c.json({ detail: "image file is required" }, 400);
  }

  const sql = createDb(c.env);
  try {
    const users = await sql`SELECT id FROM users WHERE id = ${userId}::uuid`;
    if (users.length === 0) {
      return c.json({ detail: "User not found" }, 404);
    }

    const fileBytes = await image.arrayBuffer();
    const ext = image.name.includes(".") ? image.name.split(".").pop() : "jpg";
    const filename = `enrollments/${userId}.${ext}`;

    await uploadImage(c.env, fileBytes, filename, image.type || "image/jpeg");
    const storageUrl = getImageUrl(c.env, filename, true);

    const predictUrl = `${c.env.INFERENCE_URL.replace(/\/$/, "")}/predict`;
    const inferenceResponse = await fetch(predictUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        images: [{ image_id: userId, url: storageUrl }],
      }),
    });

    if (!inferenceResponse.ok) {
      const text = await inferenceResponse.text();
      return c.json({ detail: `Inference service error: ${text}` }, 500);
    }

    const inferenceData = (await inferenceResponse.json()) as {
      results?: Array<{ faces?: Array<{ embedding?: number[] }> }>;
    };
    const faces = inferenceData.results?.[0]?.faces;
    if (!faces || faces.length === 0) {
      return c.json(
        {
          detail:
            "No face detected in the enrollment image. Please try again with a clear photo of your face.",
        },
        400,
      );
    }

    const embedding = faces[0].embedding;
    if (!embedding || embedding.length !== 512) {
      return c.json({ detail: "Invalid embedding from inference service" }, 500);
    }

    const embeddingRows = await sql`
      INSERT INTO face_embeddings (user_id, embedding, source, source_photo_id)
      VALUES (
        ${userId}::uuid,
        ${JSON.stringify(embedding)}::vector,
        'enrollment',
        NULL
      )
      RETURNING id
    `;

    return c.json({
      enrolled: true,
      embedding_id: embeddingRows[0].id,
    });
  } catch (error) {
    if (error instanceof Error && error.message.startsWith("Could not reach")) {
      return c.json({ detail: `Could not reach inference service: ${error.message}` }, 503);
    }
    throw error;
  } finally {
    await sql.end({ timeout: 5 });
  }
});

auth.post("/login", async (c) => {
  const body = await c.req.parseBody();
  const mobileNumber = formField(body, "mobile_number");
  const otp = formField(body, "otp");

  const sql = createDb(c.env);
  try {
    const otpRows = await sql`
      SELECT otp_code, expires_at
      FROM otp_requests
      WHERE mobile_number = ${mobileNumber}
      ORDER BY created_at DESC
      LIMIT 1
    `;

    const otpReq = otpRows[0];
    if (
      !otpReq ||
      otpReq.otp_code !== otp ||
      new Date(otpReq.expires_at as string) < new Date()
    ) {
      return c.json({ detail: "Invalid or expired OTP" }, 400);
    }

    const users = await sql`
      SELECT id FROM users WHERE mobile_number = ${mobileNumber}
    `;
    if (users.length === 0) {
      return c.json({ detail: "User not found. Please register first." }, 404);
    }

    const userId = users[0].id as string;
    const token = await createAccessToken(userId, c.env.JWT_SECRET);
    return c.json({ token, user_id: userId });
  } finally {
    await sql.end({ timeout: 5 });
  }
});

auth.post("/request-login-otp", async (c) => {
  const body = await c.req.parseBody();
  const mobileNumber = formField(body, "mobile_number");

  const sql = createDb(c.env);
  try {
    const users = await sql`
      SELECT id, is_verified FROM users WHERE mobile_number = ${mobileNumber}
    `;
    if (users.length === 0) {
      return c.json({ detail: "User not found" }, 404);
    }
    if (!users[0].is_verified) {
      return c.json({ detail: "User not verified" }, 400);
    }

    const otpCode = "123456";
    const expiresAt = new Date(Date.now() + 5 * 60 * 1000).toISOString();
    await sql`
      INSERT INTO otp_requests (mobile_number, otp_code, expires_at)
      VALUES (${mobileNumber}, ${otpCode}, ${expiresAt}::timestamptz)
    `;

    console.log(
      `--- MOCK OTP --- Sent OTP ${otpCode} to ${mobileNumber} (expires in 5 minutes)`,
    );
    return c.json({ otp_sent: true });
  } finally {
    await sql.end({ timeout: 5 });
  }
});

auth.get("/me", requireAuth, async (c) => {
  const userId = c.get("userId");
  const sql = createDb(c.env);
  try {
    const users = await sql`
      SELECT id, username, mobile_number, created_at
      FROM users WHERE id = ${userId}::uuid
    `;
    if (users.length === 0) {
      return c.json({ detail: "User not found" }, 404);
    }
    const user = users[0];
    return c.json({
      user_id: user.id,
      username: user.username,
      mobile_number: user.mobile_number,
      created_at: user.created_at,
    });
  } finally {
    await sql.end({ timeout: 5 });
  }
});

export default auth;
