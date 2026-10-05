// Extension: par-naz-dashboard
// Live dashboard for tracking Noorak Search Engine (par-naz) project progress
//
// This single-file skeleton is a starting point. For more complex canvases
// (multiple actions with non-trivial logic, shared state, a custom renderer,
// etc.) prefer splitting things out: move each action handler into its own
// function, extract `open`/`onClose` into helpers, and pull large units
// (renderer assets, schema definitions, shared utilities) into sibling files
// imported from this entry point. Keep extension.mjs focused on wiring.

import { createServer } from "node:http";
import { joinSession, createCanvas } from "@github/copilot-sdk/extension";
import { execSync } from "node:child_process";
import { readFileSync, existsSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(__dirname, "..", "..", "..");

// One local HTTP server per open canvas instance. Each instance gets its own
// ephemeral port so multiple canvases (or multiple opens of the same canvas)
// don't collide. Replace this with your real renderer — point a static-file
// server, a Vite/Next dev server, or any framework you like at the same URL.
const servers = new Map();

function getGitStatus() {
    try {
        const status = execSync("git status --short", { cwd: REPO_ROOT, encoding: "utf-8" }).trim();
        const log = execSync("git log --oneline -10", { cwd: REPO_ROOT, encoding: "utf-8" }).trim();
        const branch = execSync("git branch --show-current", { cwd: REPO_ROOT, encoding: "utf-8" }).trim();
        return { status, log, branch };
    } catch {
        return { status: "Error reading git", log: "", branch: "unknown" };
    }
}

function getEngineStatus() {
    const engineDir = join(REPO_ROOT, "engine");
    const cargoToml = join(engineDir, "Cargo.toml");
    if (!existsSync(cargoToml)) return { exists: false };
    
    try {
        const cargoCheck = execSync("cargo check 2>&1", { cwd: engineDir, encoding: "utf-8", timeout: 30000 });
        return { exists: true, check: "ok", output: cargoCheck.slice(-500) };
    } catch (e) {
        return { exists: true, check: "failed", output: e.stdout?.toString().slice(-500) || e.message };
    }
}

function getLfeStatus() {
    const lfeDir = join(REPO_ROOT, "lfe");
    const mainPy = join(lfeDir, "noor_pdna.py");
    if (!existsSync(mainPy)) return { exists: false };
    
    try {
        const result = execSync("python noor_pdna.py 2>&1", { cwd: lfeDir, encoding: "utf-8", timeout: 10000 });
        return { exists: true, demo: "ok", output: result.slice(-1000) };
    } catch (e) {
        return { exists: true, demo: "failed", output: e.stdout?.toString().slice(-1000) || e.message };
    }
}

function getFileTree() {
    const dirs = ["engine", "lfe", ".github/extensions/par-naz-dashboard"];
    const tree = {};
    for (const d of dirs) {
        const full = join(REPO_ROOT, d);
        if (existsSync(full)) {
            tree[d] = getDirListing(full, 2);
        }
    }
    return tree;
}

function getDirListing(dir, depth = 2, currentDepth = 0) {
    if (currentDepth >= depth) return [];
    const files = [];
    try {
        const entries = readdirSync(dir, { withFileTypes: true });
        for (const entry of entries) {
            if (entry.name.startsWith(".") || entry.name === "node_modules" || entry.name === "target") continue;
            const full = join(dir, entry.name);
            const stat = statSync(full);
            files.push({
                name: entry.name,
                type: entry.isDirectory() ? "dir" : "file",
                size: entry.isFile() ? stat.size : undefined,
                children: entry.isDirectory() ? getDirListing(full, depth, currentDepth + 1) : undefined
            });
        }
    } catch (e) {
        console.error(`[par-naz] Failed to read directory ${dir}:`, e.message);
    }
    return files;
}

function renderHtml(instanceId, data) {
    const { git, engine, lfe, tree, timestamp } = data;
    return `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>par-naz Dashboard</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: system-ui, -apple-system, sans-serif; padding: 1rem; margin: 0; background: #0d1117; color: #e6edf3; line-height: 1.5; }
    h1 { font-size: 1.5rem; margin: 0 0 0.5rem; color: #58a6ff; }
    h2 { font-size: 1.1rem; margin: 1.5rem 0 0.5rem; color: #8b949e; border-bottom: 1px solid #30363d; padding-bottom: 0.25rem; }
    h3 { font-size: 0.95rem; margin: 1rem 0 0.5rem; color: #c9d1d9; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; }
    .card { background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 1rem; }
    .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; }
    .badge { padding: 0.125rem 0.5rem; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
    .badge-ok { background: #238636; color: #fff; }
    .badge-fail { background: #da3633; color: #fff; }
    .badge-warn { background: #9e6a03; color: #fff; }
    .badge-info { background: #1f6feb; color: #fff; }
    pre { background: #0d1117; border: 1px solid #30363d; border-radius: 4px; padding: 0.75rem; overflow: auto; font-size: 0.8rem; max-height: 300px; }
    code { font-family: 'SF Mono', 'Fira Code', monospace; }
    .file-tree { font-size: 0.85rem; }
    .file-tree ul { list-style: none; padding-left: 1.25rem; margin: 0; }
    .file-tree li { margin: 0.125rem 0; }
    .file-tree .dir { color: #58a6ff; font-weight: 500; }
    .file-tree .file { color: #8b949e; }
    .timestamp { color: #8b949e; font-size: 0.75rem; text-align: right; margin-top: 1rem; }
    .section { margin-bottom: 1rem; }
    .log-line { margin: 0.125rem 0; font-family: monospace; font-size: 0.75rem; }
    .log-error { color: #f85149; }
    .log-success { color: #3fb950; }
    .log-info { color: #58a6ff; }
  </style>
</head>
<body>
  <h1>🔍 par-naz Dashboard</h1>
  <p style="color: #8b949e;">Noorak Search Engine — Live Project Tracking</p>
  
  <div class="grid">
    <div class="card">
      <div class="card-header">
        <h2>📦 Git Status</h2>
        <span class="badge badge-info">${git.branch}</span>
      </div>
      <h3>Working Tree</h3>
      <pre>${git.status || "(clean)"}</pre>
      <h3>Recent Commits</h3>
      <pre>${git.log || "No commits"}</pre>
    </div>

    <div class="card">
      <div class="card-header">
        <h2>⚙️ Engine (Rust)</h2>
        <span class="badge ${engine.exists ? (engine.check === "ok" ? "badge-ok" : "badge-fail") : "badge-warn"}">
          ${engine.exists ? (engine.check === "ok" ? "cargo check ✓" : "cargo check ✗") : "Not found"}
        </span>
      </div>
      ${engine.exists ? `<pre>${engine.output}</pre>` : "<p>No Cargo.toml found</p>"}
    </div>

    <div class="card">
      <div class="card-header">
        <h2>🧠 LFE (Python PDNA)</h2>
        <span class="badge ${lfe.exists ? (lfe.demo === "ok" ? "badge-ok" : "badge-fail") : "badge-warn"}">
          ${lfe.exists ? (lfe.demo === "ok" ? "Demo runs ✓" : "Demo failed ✗") : "Not found"}
        </span>
      </div>
      ${lfe.exists ? `<pre>${lfe.output}</pre>` : "<p>No noor_pdna.py found</p>"}
    </div>
  </div>

  <div class="card">
    <h2>📁 Project Structure</h2>
    <div class="file-tree">
      ${renderTree(tree)}
    </div>
  </div>

  <div class="timestamp">Last updated: ${timestamp}</div>

  <script>
    // Auto-refresh every 30 seconds
    setTimeout(() => location.reload(), 30000);
  </script>
</body>
</html>`;
}

function renderTree(tree, indent = 0) {
    let html = "<ul>";
    for (const [key, value] of Object.entries(tree)) {
        html += `<li><span class="dir">📁 ${key}/</span>`;
        if (Array.isArray(value) && value.length) {
            html += renderFileList(value);
        }
        html += "</li>";
    }
    html += "</ul>";
    return html;
}

function renderFileList(files) {
    let html = "<ul>";
    for (const f of files) {
        const icon = f.type === "dir" ? "📁" : "📄";
        const cls = f.type === "dir" ? "dir" : "file";
        const size = f.size !== undefined ? ` <span style="color:#8b949e;font-size:0.75rem;">(${formatSize(f.size)})</span>` : "";
        html += `<li><span class="${cls}">${icon} ${f.name}</span>${size}`;
        if (f.children && f.children.length) {
            html += renderFileList(f.children);
        }
        html += "</li>";
    }
    html += "</ul>";
    return html;
}

function formatSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

async function startServer(instanceId) {
    const server = createServer(async (req, res) => {
        // Gather fresh data on each request
        const data = {
            git: getGitStatus(),
            engine: getEngineStatus(),
            lfe: getLfeStatus(),
            tree: getFileTree(),
            timestamp: new Date().toLocaleString()
        };
        res.setHeader("Content-Type", "text/html; charset=utf-8");
        res.end(renderHtml(instanceId, data));
    });
    // Port 0 = let the OS pick a free ephemeral port. Bind to loopback only.
    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    const address = server.address();
    const port = typeof address === "object" && address ? address.port : 0;
    return { server, url: `http://127.0.0.1:${port}/` };
}

const session = await joinSession({
    canvases: [
        createCanvas({
            id: "par-naz-dashboard",
            displayName: "par-naz Dashboard",
            description: "Live tracking dashboard for Noorak Search Engine (par-naz) project",
            actions: [
                {
                    name: "refresh",
                    description: "Force refresh the dashboard data",
                    handler: async (ctx) => {
                        return { ok: true, message: "Dashboard will auto-refresh on next poll" };
                    },
                },
                {
                    name: "run_engine_check",
                    description: "Run cargo check on engine",
                    handler: async (ctx) => {
                        try {
                            const out = execSync("cargo check 2>&1", { cwd: join(REPO_ROOT, "engine"), encoding: "utf-8", timeout: 60000 });
                            return { ok: true, output: out.slice(-2000) };
                        } catch (e) {
                            return { ok: false, output: e.stdout?.toString().slice(-2000) || e.message };
                        }
                    },
                },
                {
                    name: "run_lfe_demo",
                    description: "Run NoorPDNA demo",
                    handler: async (ctx) => {
                        try {
                            const out = execSync("python noor_pdna.py 2>&1", { cwd: join(REPO_ROOT, "lfe"), encoding: "utf-8", timeout: 15000 });
                            return { ok: true, output: out.slice(-3000) };
                        } catch (e) {
                            return { ok: false, output: e.stdout?.toString().slice(-3000) || e.message };
                        }
                    },
                },
            ],
            open: async (ctx) => {
                let entry = servers.get(ctx.instanceId);
                if (!entry) {
                    entry = await startServer(ctx.instanceId);
                    servers.set(ctx.instanceId, entry);
                }
                return {
                    title: "par-naz Dashboard",
                    url: entry.url,
                };
            },
            onClose: async (ctx) => {
                const entry = servers.get(ctx.instanceId);
                if (entry) {
                    servers.delete(ctx.instanceId);
                    await new Promise((resolve) => entry.server.close(() => resolve()));
                }
            },
        }),
    ],
});
