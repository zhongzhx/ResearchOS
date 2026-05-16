const { app, BrowserWindow, dialog, nativeTheme } = require("electron");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "..");
const WEB_ROOT = path.join(ROOT, "web_client");
const CANONICAL_API_SCRIPT = path.join(
  ROOT,
  "backend",
  "research_agent_runtime",
  "scripts",
  "research_agent_api.py",
);
const API_SCRIPT = CANONICAL_API_SCRIPT;
const AGENT_ROOT = process.env.RESEARCHOS_AGENT_ROOT || path.join(ROOT, "agent_data");
const API_HOST = process.env.RESEARCHOS_HOST || "127.0.0.1";
const API_PORT = Number(process.env.RESEARCHOS_PORT || "8765");
const API_BASE_URL = `http://${API_HOST}:${API_PORT}`;
const BACKEND_REQUIRED_BEFORE_WINDOW = true;

let apiProcess = null;
let webServer = null;
let mainWindow = null;

function requestBackend(pathname, options = {}) {
  return new Promise((resolve, reject) => {
    const request = http.request(`${API_BASE_URL}${pathname}`, options, (response) => {
      response.resume();
      response.on("end", () => resolve(response.statusCode || 0));
    });
    request.on("error", reject);
    request.setTimeout(2000, () => {
      request.destroy(new Error("backend timeout"));
    });
    request.end();
  });
}

function requestBackendJson(pathname, options = {}) {
  return new Promise((resolve, reject) => {
    const request = http.request(`${API_BASE_URL}${pathname}`, options, (response) => {
      const chunks = [];
      response.on("data", (chunk) => chunks.push(chunk));
      response.on("end", () => {
        try {
          const body = Buffer.concat(chunks).toString("utf8");
          resolve({ statusCode: response.statusCode || 0, data: body ? JSON.parse(body) : {} });
        } catch (error) {
          reject(error);
        }
      });
    });
    request.on("error", reject);
    request.setTimeout(2000, () => {
      request.destroy(new Error("backend timeout"));
    });
    request.end();
  });
}

function normalizePathForCompare(value) {
  return path.resolve(String(value || "")).toLowerCase();
}

async function backendHealth() {
  try {
    const health = await requestBackendJson("/health", { method: "GET" });
    if (health.statusCode !== 200 || health.data?.status !== "ok") {
      return null;
    }
    return health.data;
  } catch {
    return null;
  }
}

async function backendReady() {
  return Boolean(await backendHealth());
}

function backendMatchesThisClient(health) {
  return normalizePathForCompare(health?.api_script) === normalizePathForCompare(API_SCRIPT);
}

function execCommand(command, args) {
  return new Promise((resolve) => {
    const child = spawn(command, args, { windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
    const chunks = [];
    child.stdout.on("data", (chunk) => chunks.push(chunk));
    child.on("error", () => resolve(""));
    child.on("close", () => resolve(Buffer.concat(chunks).toString("utf8")));
  });
}

async function portOwnerPids() {
  if (process.platform === "win32") {
    const script = `Get-NetTCPConnection -LocalPort ${API_PORT} -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess`;
    const output = await execCommand("powershell.exe", ["-NoProfile", "-Command", script]);
    return output
      .split(/\r?\n/)
      .map((line) => Number(line.trim()))
      .filter(Boolean);
  }
  const output = await execCommand("sh", ["-lc", `lsof -ti tcp:${API_PORT} -sTCP:LISTEN 2>/dev/null || true`]);
  return output
    .split(/\r?\n/)
    .map((line) => Number(line.trim()))
    .filter(Boolean);
}

async function stopBackendOnConfiguredPort() {
  const pids = await portOwnerPids();
  for (const pid of pids) {
    if (apiProcess && apiProcess.pid === pid) {
      continue;
    }
    if (process.platform === "win32") {
      await execCommand("taskkill.exe", ["/PID", String(pid), "/T", "/F"]);
    } else {
      try {
        process.kill(pid);
      } catch {
        // The process may already have exited.
      }
    }
  }
  const deadline = Date.now() + 5000;
  while (Date.now() < deadline) {
    if (!(await backendHealth())) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
}

function pythonCommand() {
  if (process.env.RESEARCHOS_API_PYTHON) {
    return { command: process.env.RESEARCHOS_API_PYTHON, prefixArgs: ["-u"] };
  }
  if (process.platform === "win32") {
    return { command: "py", prefixArgs: ["-u"] };
  }
  return { command: "python3", prefixArgs: ["-u"] };
}

async function startBackend() {
  const existingHealth = await backendHealth();
  if (existingHealth) {
    if (backendMatchesThisClient(existingHealth)) {
      return;
    }
    await stopBackendOnConfiguredPort();
  }
  fs.mkdirSync(AGENT_ROOT, { recursive: true });
  const logRoot = path.join(AGENT_ROOT, "logs");
  fs.mkdirSync(logRoot, { recursive: true });
  const logStream = fs.createWriteStream(path.join(logRoot, "researchos_api.log"), { flags: "a" });
  const env = {
    ...process.env,
    RESEARCHOS_AGENT_ROOT: AGENT_ROOT,
    RESEARCHOS_HOST: API_HOST,
    RESEARCHOS_PORT: String(API_PORT),
    RESEARCHOS_DUAL_AGENT_API_ENABLED: process.env.RESEARCHOS_DUAL_AGENT_API_ENABLED || "true",
  };
  const envFile = path.join(ROOT, ".env");
  if (fs.existsSync(envFile)) {
    env.RESEARCHOS_ENV_FILE = envFile;
  }
  const python = pythonCommand();
  apiProcess = spawn(
    python.command,
    [
      ...python.prefixArgs,
      API_SCRIPT,
      "--agent-root",
      AGENT_ROOT,
      "--host",
      API_HOST,
      "--port",
      String(API_PORT),
    ],
    {
      cwd: path.dirname(API_SCRIPT),
      env,
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  apiProcess.stdout.pipe(logStream);
  apiProcess.stderr.pipe(logStream);
  const deadline = Date.now() + 30000;
  while (Date.now() < deadline) {
    if (await backendReady()) {
      return;
    }
    if (apiProcess.exitCode !== null) {
      throw new Error("ResearchOS API exited before startup completed");
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error("ResearchOS API startup timed out");
}

async function ensureBackendStartedForClient() {
  if (!BACKEND_REQUIRED_BEFORE_WINDOW) {
    return;
  }
  await startBackend();
  if (!(await backendReady())) {
    throw new Error(`ResearchOS API is not healthy at ${API_BASE_URL}`);
  }
}

function contentTypeFor(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  if (ext === ".html") return "text/html; charset=utf-8";
  if (ext === ".css") return "text/css; charset=utf-8";
  if (ext === ".js") return "application/javascript; charset=utf-8";
  if (ext === ".svg") return "image/svg+xml";
  return "application/octet-stream";
}

function serveStatic(requestPath, response) {
  const parsed = new URL(requestPath, "http://127.0.0.1");
  let route = decodeURIComponent(parsed.pathname.replace(/^\/+/, "")) || "index.html";
  let target = path.resolve(WEB_ROOT, route);
  if (!target.startsWith(path.resolve(WEB_ROOT)) || !fs.existsSync(target) || !fs.statSync(target).isFile()) {
    target = path.join(WEB_ROOT, "index.html");
  }
  const body = fs.readFileSync(target);
  response.writeHead(200, {
    "Content-Type": contentTypeFor(target),
    "Cache-Control": "no-store",
    "Content-Length": body.length,
  });
  response.end(body);
}

function proxyBackend(request, response) {
  const parsed = new URL(request.url, "http://127.0.0.1");
  const suffix = parsed.pathname.replace(/^\/api\/backend/, "") || "/";
  const targetPath = `${suffix}${parsed.search}`;
  const chunks = [];
  let bodySize = 0;
  const failProxy = (error, statusCode = 502) => {
    const body = Buffer.from(JSON.stringify({ error: error.message, backend: API_BASE_URL }, null, 2));
    response.writeHead(statusCode, {
      "Content-Type": "application/json; charset=utf-8",
      "Content-Length": body.length,
    });
    response.end(body);
  };

  request.on("data", (chunk) => {
    bodySize += chunk.length;
    if (bodySize > 1024 * 1024) {
      request.destroy(new Error("request body too large"));
      return;
    }
    chunks.push(chunk);
  });
  request.on("error", (error) => failProxy(error, 400));
  request.on("end", () => {
    const body = Buffer.concat(chunks);
    const headers = {
      Accept: request.headers.accept || "application/json",
      "Content-Type": request.headers["content-type"] || "application/json",
      "Content-Length": body.length,
    };
    const proxy = http.request(
      `${API_BASE_URL}${targetPath}`,
      {
        method: request.method,
        headers,
      },
      (backendResponse) => {
        response.writeHead(backendResponse.statusCode || 502, {
          "Content-Type": backendResponse.headers["content-type"] || "application/json; charset=utf-8",
          "Cache-Control": "no-store",
        });
        backendResponse.pipe(response);
      },
    );
    proxy.on("error", (error) => failProxy(error));
    if (body.length) {
      proxy.write(body);
    }
    proxy.end();
  });
}

function startWebServer() {
  return new Promise((resolve) => {
    webServer = http.createServer((request, response) => {
      if (request.url.startsWith("/api/backend")) {
        proxyBackend(request, response);
        return;
      }
      serveStatic(request.url, response);
    });
    webServer.listen(0, "127.0.0.1", () => {
      resolve(webServer.address().port);
    });
  });
}

async function createWindow() {
  nativeTheme.themeSource = "light";
  await ensureBackendStartedForClient();
  const webPort = await startWebServer();
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 980,
    minHeight: 680,
    backgroundColor: "#f7f8fa",
    title: "AURA Research",
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  await mainWindow.loadURL(`http://127.0.0.1:${webPort}/`);
}

async function runSmokeTest() {
  await ensureBackendStartedForClient();
  const webPort = await startWebServer();
  const backendStatus = await requestBackend("/health", { method: "GET" });
  console.log(JSON.stringify({ ok: true, webPort, backendStatus }));
  if (webServer) {
    webServer.close();
  }
  if (apiProcess && apiProcess.exitCode === null) {
    apiProcess.kill();
  }
  app.quit();
}

if (process.argv.includes("--smoke-test")) {
  app.whenReady().then(runSmokeTest).catch((error) => {
    console.error(error);
    app.exit(1);
  });
} else {
  app.whenReady().then(createWindow).catch((error) => {
    console.error(error);
    dialog.showErrorBox("AURA Research 后端启动失败", `${error.message}\n\n日志位置：${path.join(AGENT_ROOT, "logs", "researchos_api.log")}`);
    app.exit(1);
  });
}

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on("before-quit", () => {
  if (webServer) {
    webServer.close();
  }
  if (apiProcess && apiProcess.exitCode === null) {
    apiProcess.kill();
  }
});
