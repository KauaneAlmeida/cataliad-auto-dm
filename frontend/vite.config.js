import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Em desenvolvimento, o frontend roda em :5173 e o backend em :8000.
// O proxy faz /api e /webhook apontarem para o backend, evitando CORS no dev.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
