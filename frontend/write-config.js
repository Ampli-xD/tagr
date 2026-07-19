#!/usr/bin/env node
/**
 * Vercel build step: write config.js from environment variables.
 *
 * Production (Render backend):
 *   TAGR_API_URL=https://tagr-api.onrender.com/api/v1
 *   TAGR_WAKE_BACKEND=true
 *
 * Local dev (v1, same machine): omit TAGR_WAKE_BACKEND or set false.
 */
const fs = require('fs');
const path = require('path');

const api = (process.env.TAGR_API_URL || '').trim().replace(/\/$/, '');
const wakeRaw = (process.env.TAGR_WAKE_BACKEND || '').trim().toLowerCase();
const wakeBackend = wakeRaw === 'true' || wakeRaw === '1';
const wakeMessage = (process.env.TAGR_WAKE_MESSAGE || '').trim();

const lines = [
    `window.TAGR_API_URL = ${JSON.stringify(api)};`,
    `window.TAGR_WAKE_BACKEND = ${wakeBackend};`,
];
if (wakeMessage) {
    lines.push(`window.TAGR_WAKE_MESSAGE = ${JSON.stringify(wakeMessage)};`);
}

const out = path.join(__dirname, 'config.js');
fs.writeFileSync(out, lines.join('\n') + '\n');
console.log(
    api
        ? `Wrote config.js (API=${api}, wake=${wakeBackend})`
        : 'Wrote config.js (empty — set TAGR_API_URL on Vercel)'
);
