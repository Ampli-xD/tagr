#!/usr/bin/env node
/**
 * Vercel build step: write config.js from TAGR_API_URL env var.
 * Example: https://your-api.example.com/api/v1
 */
const fs = require('fs');
const path = require('path');

const api = (process.env.TAGR_API_URL || '').trim().replace(/\/$/, '');
const out = path.join(__dirname, 'config.js');
fs.writeFileSync(out, `window.TAGR_API_URL = ${JSON.stringify(api)};\n`);
console.log(api ? `Wrote config.js with TAGR_API_URL=${api}` : 'Wrote config.js (empty — set TAGR_API_URL on Vercel)');
