export default {
  async fetch(request) {
    const url = new URL(request.url);

    if (url.pathname === "/resolve" && request.method === "POST") {
      return await handleResolve(request);
    } else if (url.pathname === "/status") {
      return await handleStatus();
    }

    return new Response("Not Found", { status: 404 });
  },
};

const COOKIE = "ipb_member_id=xxx; ipb_pass_hash=yyy; ..."; // 替换为你的 Cookie
const enable_GP_cost = true; // 是否允许消耗 GP
const USER_AGENT =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/135.0.0.0 Safari/537.36";
const BASE_URL = "https://exhentai.org";

const HEADERS = {
  "User-Agent": USER_AGENT,
  Cookie: COOKIE,
};

async function handleResolve(request) {
  try {
    const data = await request.json();
    const { gid, token, username } = data;

    let msg = null;
    let requireGP = null;
    let d_url = null;

    try {
      requireGP = await getGPCost(gid, token);

      if (requireGP > 0 && !enable_GP_cost) {
        msg = "Rejected";
      } else {
        d_url = await getDownloadUrl(gid, token);
        msg = "Success";
        await fetchWithTimeout(`${BASE_URL}/archiver.php?gid=${gid}&token=${token}`, {
          method: "POST",
          headers: {
            ...HEADERS,
            "Content-Type": "application/x-www-form-urlencoded",
          },
          body: new URLSearchParams({ invalidate_sessions: "1" }),
        });
      }

    } catch (e) {
      console.error("[解析失败]", e.stack || e.message || e);
      msg = "解析失败";
    }

    const status = await getStatus();
    console.log(`[resolve] ${username} - ${gid} 需要GP: ${requireGP} 状态: ${msg}`);

    return jsonResponse({
      msg,
      d_url,
      require_GP: requireGP,
      status,
    });
  } catch (e) {
    console.error("[handleResolve Error]", e.stack || e);
    const status = await getStatus();
    return jsonResponse({
      msg: "Failed",
      status,
    });
  }
}


async function handleStatus() {
  const status = await getStatus();
  return jsonResponse({ status });
}

function jsonResponse(obj) {
  return new Response(JSON.stringify(obj), {
    headers: { "Content-Type": "application/json" },
  });
}

async function fetchWithTimeout(url, options = {}, timeout = 60000) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(id);
  }
}

async function getGPCost(gid, token) {
  const url = `${BASE_URL}/archiver.php?gid=${gid}&token=${token}`;
  const res = await fetchWithTimeout(url, { headers: HEADERS });
  const text = await res.text();
  const match = text.match(/<strong>(.*?)<\/strong>/);
  if (!match) throw new Error("未能匹配 GP 成本，可能是权限错误或被跳转");
  const result = match[1];
  if (result === "Free!") return 0;
  const gp = parseInt(result.replace(/[^0-9]/g, ''));
  if (isNaN(gp)) throw new Error("GP 解析失败");
  return gp;
}

async function getDownloadUrl(gid, token) {
  const url = `${BASE_URL}/archiver.php?gid=${gid}&token=${token}`;
  const form = new URLSearchParams({
    dltype: "org",
    dlcheck: "Download+Original+Archive",
  });
  const res = await fetchWithTimeout(url, {
    method: "POST",
    headers: {
      ...HEADERS,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: form,
  });
  const text = await res.text();
  const match = text.match(/document\.location = "(.*?)";/);
  return match ? `${match[1]}?start=1` : null;
}

async function getStatus() {
  try {
    const testGid = "3325056";
    const testToken = "928605fbbd";
    const requireGP = await getGPCost(testGid, testToken);
    return {
      msg: requireGP === 0 ? "正常" : "无免费额度",
      enable_GP_cost: enable_GP_cost,
    };
  } catch (e) {
    console.error("[getStatus Error]", e.stack || e);
    return { msg: "解析功能异常", enable_GP_cost: enable_GP_cost };
  }
}
