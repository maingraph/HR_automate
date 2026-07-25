import http from "node:http";
import net from "node:net";
import crypto from "node:crypto";

const port = Number(process.env.PORT || 8080);
const viewerToken = process.env.BROWSER_VIEWER_TOKEN || "";
const viewerCookie = "sourcer_viewer";
const routes = [
  { prefix: "/api", host: "api", port: 8000 },
  { prefix: "/browser", host: "browser-agent", port: 6080 },
];
const fallback = { prefix: "", host: "frontend", port: 3000 };

function targetFor(pathname) {
  return routes.find((route) => pathname === route.prefix || pathname.startsWith(`${route.prefix}/`)) || fallback;
}

function targetPath(url, route) {
  if (!route.prefix) return url;
  const stripped = url.slice(route.prefix.length);
  return stripped.startsWith("/") ? stripped : `/${stripped}`;
}

function constantTimeEqual(left, right) {
  const leftBuffer = Buffer.from(left || "");
  const rightBuffer = Buffer.from(right || "");
  return leftBuffer.length === rightBuffer.length && crypto.timingSafeEqual(leftBuffer, rightBuffer);
}

function viewerAccess(request) {
  if (!viewerToken) return { allowed: false, seedCookie: false };
  const parsed = new URL(request.url || "/", "http://gateway.local");
  const queryToken = parsed.searchParams.get("viewer_token") || "";
  const cookies = Object.fromEntries(
    String(request.headers.cookie || "")
      .split(";")
      .map(value => value.trim().split("=", 2))
      .filter(parts => parts.length === 2),
  );
  return {
    allowed: constantTimeEqual(queryToken, viewerToken) || constantTimeEqual(cookies[viewerCookie], viewerToken),
    seedCookie: constantTimeEqual(queryToken, viewerToken),
  };
}

const server = http.createServer((request, response) => {
  const route = targetFor(request.url || "/");
  const access = route.prefix === "/browser" ? viewerAccess(request) : { allowed: true, seedCookie: false };
  if (!access.allowed) {
    response.writeHead(401, { "content-type": "text/plain", "cache-control": "no-store" });
    response.end("Browser viewer authorization required");
    return;
  }
  const upstream = http.request(
    {
      host: route.host,
      port: route.port,
      method: request.method,
      path: targetPath(request.url || "/", route),
      headers: { ...request.headers, host: `${route.host}:${route.port}` },
    },
    (upstreamResponse) => {
      const headers = { ...upstreamResponse.headers };
      if (access.seedCookie) {
        headers["set-cookie"] = `${viewerCookie}=${viewerToken}; Path=/browser; HttpOnly; SameSite=Strict`;
      }
      response.writeHead(upstreamResponse.statusCode || 502, headers);
      upstreamResponse.pipe(response);
    },
  );
  upstream.on("error", (error) => {
    if (!response.headersSent) response.writeHead(502, { "content-type": "text/plain" });
    response.end(`Upstream unavailable: ${error.message}`);
  });
  request.pipe(upstream);
});

server.on("upgrade", (request, socket, head) => {
  const route = targetFor(request.url || "/");
  if (route.prefix === "/browser" && !viewerAccess(request).allowed) {
    socket.end("HTTP/1.1 401 Unauthorized\r\nConnection: close\r\n\r\n");
    return;
  }
  const upstream = net.connect(route.port, route.host, () => {
    const headers = Object.entries(request.headers)
      .map(([name, value]) => `${name}: ${Array.isArray(value) ? value.join(", ") : value}`)
      .join("\r\n");
    upstream.write(
      `${request.method} ${targetPath(request.url || "/", route)} HTTP/${request.httpVersion}\r\n${headers}\r\n\r\n`,
    );
    if (head.length) upstream.write(head);
    socket.pipe(upstream).pipe(socket);
  });
  upstream.on("error", () => socket.destroy());
  socket.on("error", () => upstream.destroy());
});

server.listen(port, "0.0.0.0", () => {
  console.log(`Sourcer web gateway listening on ${port}`);
});
