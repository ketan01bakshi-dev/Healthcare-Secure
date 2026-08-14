import "./db.js";
import { createApp } from "./app.js";
import { config } from "./config.js";

const app = createApp();

app.listen(config.port, config.host, () => {
  console.log(`Healthcare-Secure API listening on http://${config.host}:${config.port}`);
  if (!config.isProduction && config.jwtSecret === "dev-only-insecure-secret-change-me") {
    console.warn("[warn] Using the built-in development JWT secret. Set JWT_SECRET in production.");
  }
});
