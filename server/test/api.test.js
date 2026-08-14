import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

// Use an isolated temp database for tests.
const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "healthcare-test-"));
process.env.DATABASE_PATH = path.join(tmpDir, "test.db");
process.env.JWT_SECRET = "test-secret";

const { createApp } = await import("../src/app.js");

let server;
let baseUrl;

before(async () => {
  const app = createApp();
  await new Promise((resolve) => {
    server = app.listen(0, "127.0.0.1", resolve);
  });
  const { port } = server.address();
  baseUrl = `http://127.0.0.1:${port}`;
});

after(() => {
  server?.close();
  fs.rmSync(tmpDir, { recursive: true, force: true });
});

async function api(method, url, { token, body } = {}) {
  const res = await fetch(`${baseUrl}${url}`, {
    method,
    headers: {
      "content-type": "application/json",
      ...(token ? { authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  return { status: res.status, body: text ? JSON.parse(text) : null };
}

test("health endpoint reports ok", async () => {
  const res = await api("GET", "/api/health");
  assert.equal(res.status, 200);
  assert.equal(res.body.status, "ok");
});

test("patients endpoint rejects unauthenticated access", async () => {
  const res = await api("GET", "/api/patients");
  assert.equal(res.status, 401);
});

test("register, login, and manage patients end-to-end", async () => {
  const register = await api("POST", "/api/auth/register", {
    body: { email: "clinician@healthcare.local", password: "SuperSecret1", role: "admin" },
  });
  assert.equal(register.status, 201);
  const token = register.body.token;
  assert.ok(token);

  const create = await api("POST", "/api/patients", {
    token,
    body: { fullName: "Jane Doe", dateOfBirth: "1990-05-14", medicalRecord: "Penicillin allergy" },
  });
  assert.equal(create.status, 201);
  assert.equal(create.body.patient.fullName, "Jane Doe");

  const list = await api("GET", "/api/patients", { token });
  assert.equal(list.status, 200);
  assert.equal(list.body.patients.length, 1);

  const del = await api("DELETE", `/api/patients/${create.body.patient.id}`, { token });
  assert.equal(del.status, 204);
});

test("weak passwords are rejected", async () => {
  const res = await api("POST", "/api/auth/register", {
    body: { email: "weak@healthcare.local", password: "short" },
  });
  assert.equal(res.status, 400);
});
