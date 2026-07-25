import http from "node:http";

const upstream = "http://postgrest:3000";

http.createServer(async (request, response) => {
  if (request.url === "/health") {
    response.writeHead(200, { "content-type": "text/plain" });
    response.end("ok\n");
    return;
  }

  if (!request.url?.startsWith("/rest/v1/")) {
    response.writeHead(404);
    response.end();
    return;
  }

  const headers = { ...request.headers };
  delete headers.authorization;
  delete headers.apikey;
  delete headers.host;

  try {
    const upstreamResponse = await fetch(
      `${upstream}/${request.url.slice("/rest/v1/".length)}`,
      {
        method: request.method,
        headers,
        body: ["GET", "HEAD"].includes(request.method ?? "GET")
          ? undefined
          : request,
        duplex: "half",
      },
    );
    response.writeHead(
      upstreamResponse.status,
      Object.fromEntries(upstreamResponse.headers.entries()),
    );
    if (upstreamResponse.body) {
      for await (const chunk of upstreamResponse.body) response.write(chunk);
    }
    response.end();
  } catch {
    response.writeHead(502, { "content-type": "application/json" });
    response.end('{"message":"database API unavailable"}');
  }
}).listen(8000, "0.0.0.0");
