/**
 * OpenAI Codex & API Reverse Proxy (Cloudflare Worker)
 * Бесплатный европейский шлюз для обхода ошибки 403 Forbidden в РФ.
 * 
 * Инструкция по развертыванию:
 * 1. Перейдите на https://dash.cloudflare.com -> Workers & Pages -> Create Application
 * 2. Вставьте этот код и нажмите 'Deploy'
 * 3. Скопируйте полученный адрес (например: https://my-codex.yourname.workers.dev/v1)
 * 4. Укажите этот адрес в пункте [2] утилиты ChatGPT_Patcher.exe
 */

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    url.hostname = "api.openai.com";
    
    const newHeaders = new Headers(request.headers);
    newHeaders.set("Host", "api.openai.com");
    
    const newRequest = new Request(url.toString(), {
      method: request.method,
      headers: newHeaders,
      body: request.body,
      redirect: "follow"
    });
    
    const response = await fetch(newRequest);
    const responseHeaders = new Headers(response.headers);
    responseHeaders.set("Access-Control-Allow-Origin", "*");
    responseHeaders.set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
    responseHeaders.set("Access-Control-Allow-Headers", "*");
    
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: responseHeaders });
    }
    
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders
    });
  }
};
