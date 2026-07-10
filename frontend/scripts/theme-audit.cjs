const routes = [
  "/",
  "/live",
  "/integrations",
  "/peers",
  "/wallet",
  "/regtest",
  "/blocks",
  "/transactions",
  "/tx-control",
  "/mempool",
  "/fees",
  "/address",
  "/keys",
  "/multisig",
  "/psbt",
  "/timelocks",
  "/descriptors",
  "/taproot",
  "/indexer",
  "/script",
  "/script-lab",
  "/data-tx",
  "/rpc",
  "/learn"
];

let nextId = 1;
const cdpPort = process.env.CDP_PORT || "9223";

async function main() {
  const target = await fetch(`http://localhost:${cdpPort}/json/new?about:blank`, { method: "PUT" }).then((response) => response.json());
  const socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });

  const pending = new Map();
  socket.addEventListener("message", async (event) => {
    const text = typeof event.data === "string" ? event.data : await event.data.text();
    const message = JSON.parse(text);
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) {
        reject(new Error(message.error.message));
      } else {
        resolve(message.result);
      }
    }
  });

  function send(method, params = {}) {
    const id = nextId++;
    const promise = new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error(`CDP timeout: ${method}`));
      }, 8000);
      pending.set(id, {
        resolve: (value) => {
          clearTimeout(timer);
          resolve(value);
        },
        reject: (error) => {
          clearTimeout(timer);
          reject(error);
        }
      });
    });
    socket.send(JSON.stringify({ id, method, params }));
    return promise;
  }

  await send("Page.enable");
  await send("Runtime.enable");
  await send("Page.addScriptToEvaluateOnNewDocument", {
    source: `
      try {
        localStorage.setItem("bitscope-theme", "dark");
      } catch {}
      document.documentElement.classList.add("dark");
      document.documentElement.dataset.theme = "dark";
    `
  });
  await send("Emulation.setDeviceMetricsOverride", {
    width: 1440,
    height: 1000,
    deviceScaleFactor: 1,
    mobile: false
  });

  const results = [];
  for (const route of routes) {
    console.error(`auditing ${route}`);
    const url = `http://localhost:3000${route}`;
    try {
      await send("Page.navigate", { url });
    } catch (error) {
      console.error(String(error.message || error));
      try {
        await send("Page.stopLoading");
      } catch {
        // Continue with whatever rendered.
      }
    }
    await wait(1200);
    await safeSend(send, "Runtime.evaluate", {
      expression: `localStorage.setItem("bitscope-theme","dark"); document.documentElement.classList.add("dark"); document.documentElement.dataset.theme="dark";`
    });
    await wait(150);
    const before = await inspect(send).catch(() => null);
    await hoverFirst(send, ".app-sidebar a").catch(() => undefined);
    const navHover = await styleOf(send, ".app-sidebar a").catch(() => null);
    await hoverFirst(send, "main button").catch(() => undefined);
    const buttonHover = await styleOf(send, "main button").catch(() => null);
    const sample = before || {};
    results.push({
      route,
      dark: sample.dark,
      body: sample.body,
      sidebar: sample.sidebar,
      firstPanel: sample.firstPanel,
      firstButton: sample.firstButton,
      firstPre: sample.firstPre,
      firstCode: sample.firstCode,
      navHover,
      buttonHover,
      issues: issues(sample, navHover, buttonHover)
    });
  }

  socket.close();
  console.log(JSON.stringify(results.map(({ route, issues }) => ({ route, issues })).filter((item) => item.issues.length), null, 2));
}

async function safeSend(send, method, params = {}) {
  try {
    return await send(method, params);
  } catch {
    return null;
  }
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function inspect(send) {
  const result = await send("Runtime.evaluate", {
    returnByValue: true,
    expression: `(() => {
      const pick = (selector) => {
        const element = document.querySelector(selector);
        if (!element) return null;
        const style = getComputedStyle(element);
        return {
          selector,
          backgroundColor: style.backgroundColor,
          color: style.color,
          borderColor: style.borderColor
        };
      };
      return {
        dark: document.documentElement.classList.contains("dark"),
        body: pick("body"),
        sidebar: pick(".app-sidebar"),
        firstPanel: pick(".bg-panel, section, form"),
        firstButton: pick("main button"),
        firstPre: pick("pre"),
        firstCode: pick("code")
      };
    })()`
  });
  return result.result?.value || null;
}

async function styleOf(send, selector) {
  const result = await send("Runtime.evaluate", {
    returnByValue: true,
    expression: `(() => {
      const element = document.querySelector(${JSON.stringify(selector)});
      if (!element) return null;
      const style = getComputedStyle(element);
      return {
        selector: ${JSON.stringify(selector)},
        backgroundColor: style.backgroundColor,
        color: style.color,
        borderColor: style.borderColor
      };
    })()`
  });
  return result.result?.value || null;
}

async function hoverFirst(send, selector) {
  const result = await send("Runtime.evaluate", {
    returnByValue: true,
    expression: `(() => {
      const element = document.querySelector(${JSON.stringify(selector)});
      if (!element) return null;
      const rect = element.getBoundingClientRect();
      return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
    })()`
  });
  const point = result.result.value;
  if (!point) return;
  await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: point.x, y: point.y, button: "none" });
  await wait(80);
}

function issues(before, navHover, buttonHover) {
  const found = [];
  if (!before.dark) found.push("html is not dark");
  if (isLight(before.body?.backgroundColor)) found.push("body background is light");
  if (isLight(before.sidebar?.backgroundColor)) found.push("sidebar background is light");
  if (isLight(before.firstPanel?.backgroundColor)) found.push("first panel background is light");
  if (isLight(before.firstPre?.backgroundColor)) found.push("pre background is light");
  if (isLight(before.firstCode?.backgroundColor)) found.push("code background is light");
  if (isLight(navHover?.backgroundColor)) found.push("nav hover background is light");
  if (isLight(buttonHover?.backgroundColor) && !isDarkText(buttonHover?.color)) found.push("button hover contrast is suspect");
  return found;
}

function isLight(value) {
  const rgb = parseRgb(value);
  if (!rgb) return false;
  if (rgb[3] < 0.75) return false;
  return (rgb[0] * 299 + rgb[1] * 587 + rgb[2] * 114) / 1000 > 170;
}

function isDarkText(value) {
  const rgb = parseRgb(value);
  if (!rgb) return false;
  return (rgb[0] * 299 + rgb[1] * 587 + rgb[2] * 114) / 1000 < 95;
}

function parseRgb(value) {
  const match = String(value || "").match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?/);
  return match ? [Number(match[1]), Number(match[2]), Number(match[3]), match[4] === undefined ? 1 : Number(match[4])] : null;
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
