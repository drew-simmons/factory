import { defineConfig } from "blume";

export default defineConfig({
  title: "factory",
  description:
    "A Claude Code plugin that runs a software factory loop for coding agents.",
  content: {
    root: "content",
  },
  github: {
    owner: "drew-simmons",
    repo: "factory",
    branch: "main",
    dir: "docs",
  },
  lastModified: "git",
  deployment: {
    site: "https://drew-simmons.github.io",
    base: "/factory",
  },
});
