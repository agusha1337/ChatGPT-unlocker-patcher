/**
 * OpenAI Codex & ChatGPT Universal Reverse Proxy (Cloudflare Worker)
 * 100% бесплатный европейский/американский шлюз:
 * - Полный обход ошибки 403 Forbidden в РФ без установки каких-либо программ
 * - Поддержка REST API (api.openai.com) для VS Code, Cursor, Codex CLI
 * - Поддержка WebSockets (wss://chatgpt.com) для десктопного ChatGPT и стриминга
 * 
 * Инструкция по развертыванию (без скачивания ПО, прямо в браузере):
 * 1. Откройте в браузере https://dash.cloudflare.com (регистрация бесплатная, карта НЕ нужна).
 * 2. Перейдите в меню слева: "Workers & Pages" -> "Create Application" -> "Create Worker".
 * 3. Нажмите "Deploy".
 * 4. Нажмите "Edit code", сотрите весь код в окне и вставьте этот файл целиком.
 * 5. Нажмите "Deploy" (сохранить).
 * 6. Скопируйте ссылку на ваш воркер (например: https://my-codex.yourname.workers.dev).
 * 7. В утилите ChatGPT_Patcher.exe нажмите [2] и вставьте эту ссылку. Готово!
 */

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Определяем целевой хост (api.openai.com или chatgpt.com)
    const isChatGPTWeb = url.pathname.startsWith("/backend-api") || 
                         url.pathname.startsWith("/backend") || 
                         url.pathname.includes("/codex/responses");
    const targetHost = isChatGPTWeb ? "chatgpt.com" : "api.openai.com";
    
    url.hostname = targetHost;
    url.protocol = "https:";

    // Поддержка WebSockets (для интерактивного стриминга Codex и ChatGPT)
    const upgradeHeader = request.headers.get("Upgrade");
    if (upgradeHeader && upgradeHeader.toLowerCase() === "websocket") {
      const wsHeaders = new Headers(request.headers);
      wsHeaders.set("Host", targetHost);
      const wsRequest = new Request(url.toString(), {
        method: request.method,
        headers: wsHeaders,
        redirect: "follow"
      });
      return fetch(wsRequest);
    }

    // Поддержка CORS для браузеров и веб-запросов
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
          "Access-Control-Allow-Headers": "*",
          "Access-Control-Max-Age": "86400"
        }
      });
    }

    // Формируем проксируемый запрос
    const newHeaders = new Headers(request.headers);
    newHeaders.set("Host", targetHost);
    
    // Удаляем заголовки Cloudflare, чтобы избежать конфликтов
    newHeaders.delete("cf-connecting-ip");
    newHeaders.delete("cf-ray");
    newHeaders.delete("cf-ipcountry");
    newHeaders.delete("cf-visitor");

    const newRequest = new Request(url.toString(), {
      method: request.method,
      headers: newHeaders,
      body: request.body,
      redirect: "follow"
    });

    try {
      const response = await fetch(newRequest);
      const responseHeaders = new Headers(response.headers);
      responseHeaders.set("Access-Control-Allow-Origin", "*");
      responseHeaders.set("Access-Control-Allow-Headers", "*");
      
      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: responseHeaders
      });
    } catch (err) {
      return new Response(JSON.stringify({ error: "Proxy upstream error", details: err.message }), {
        status: 502,
        headers: { "Content-Type": "application/json" }
      });
    }
  }
};
