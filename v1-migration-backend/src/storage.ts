import { AwsClient } from "aws4fetch";
import type { Env } from "./env";

let bucketReady = false;

function s3Client(env: Env) {
  return new AwsClient({
    accessKeyId: env.STORAGE_ACCESS_KEY,
    secretAccessKey: env.STORAGE_SECRET_KEY,
    service: "s3",
    region: "us-east-1",
  });
}

async function ensureBucket(env: Env): Promise<void> {
  if (bucketReady) return;

  const client = s3Client(env);
  const url = `${env.STORAGE_ENDPOINT}/${env.STORAGE_BUCKET}`;

  const response = await client.fetch(url, { method: "PUT" });
  if (response.ok || response.status === 409) {
    bucketReady = true;
    return;
  }

  const listResponse = await client.fetch(`${env.STORAGE_ENDPOINT}/`, {
    method: "GET",
  });
  if (listResponse.ok) {
    const text = await listResponse.text();
    if (text.includes(`<Name>${env.STORAGE_BUCKET}</Name>`)) {
      bucketReady = true;
    }
  }
}

export async function uploadImage(
  env: Env,
  fileBytes: ArrayBuffer,
  filename: string,
  contentType: string,
): Promise<string> {
  await ensureBucket(env);

  const client = s3Client(env);
  const url = `${env.STORAGE_ENDPOINT}/${env.STORAGE_BUCKET}/${filename}`;

  const response = await client.fetch(url, {
    method: "PUT",
    body: fileBytes,
    headers: {
      "Content-Type": contentType || "application/octet-stream",
    },
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Failed to upload image: ${response.status} ${body}`);
  }

  return filename;
}

export function getImageUrl(
  env: Env,
  filename: string,
  internal = true,
): string {
  const endpoint = internal
    ? env.STORAGE_ENDPOINT
    : env.STORAGE_PUBLIC_ENDPOINT;
  return `${endpoint}/${env.STORAGE_BUCKET}/${filename}`;
}
