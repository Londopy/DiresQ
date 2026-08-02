import { defineConfig } from "astro/config";

// GitHub Pages serves a project site from /<repo>/, so every absolute link
// has to carry that prefix. Set it here once and use Astro's import.meta.env
// .BASE_URL everywhere else. Getting this wrong is why project sites deploy
// with no CSS.
export default defineConfig({
  // The repo lives under Skythe7, so Pages serves it from her subdomain, not
  // whoever pushed last.
  site: "https://skythe7.github.io",
  base: "/DiresQ",
  trailingSlash: "ignore",
});
