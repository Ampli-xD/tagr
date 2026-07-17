export interface Env {
  DATABASE_URL: string;
  JWT_SECRET: string;
  STORAGE_ENDPOINT: string;
  STORAGE_PUBLIC_ENDPOINT: string;
  STORAGE_ACCESS_KEY: string;
  STORAGE_SECRET_KEY: string;
  STORAGE_BUCKET: string;
  INFERENCE_URL: string;
  API_CALLBACK_URL: string;
  BATCH_SIZE: string;
  BATCH_TIMEOUT_MS: string;
  SIMILARITY_THRESHOLD: string;
  BATCHER: DurableObjectNamespace;
  ASSETS: Fetcher;
}

export type AppEnv = { Bindings: Env };
