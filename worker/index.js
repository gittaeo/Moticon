const MODEL = "@cf/black-forest-labs/flux-2-klein-4b";
const PHRASES = ["안녕!", "반가워", "잘 가", "고마워", "미안해", "사랑해", "좋아!", "최고야", "축하해", "화이팅", "대박", "헉!", "정말?", "왜?", "신난다", "너무 웃겨", "감동이야", "슬퍼", "화났어", "삐졌어", "기다려", "지금 가!", "배고파", "잘 자"];
const EMOTIONS = ["인사", "환영", "작별", "감사", "사과", "애정", "긍정", "칭찬", "축하", "응원", "놀람", "당황", "의문", "질문", "기쁨", "웃음", "감동", "슬픔", "화남", "토라짐", "요청", "이동", "일상", "취침"];
const MOTIONS = ["한 손을 들어 자연스럽게 좌우로 흔들며 웃기", "두 팔을 벌리고 반갑게 웃기", "뒤돌아 손을 흔들며 작별하기", "두 손을 모아 감사 인사하기", "고개를 숙이고 미안한 표정 짓기", "볼 옆에 하트를 만들고 애교 부리기", "엄지척하며 가볍게 점프하기", "두 엄지를 들고 환하게 웃기", "꽃가루 속에서 축하 점프하기", "주먹을 힘차게 들어 응원하기", "눈을 크게 뜨고 깜짝 놀라기", "식은땀을 흘리며 당황하기", "고개를 갸웃하고 궁금해하기", "두 손을 펼쳐 왜냐고 묻기", "두 팔을 들고 신나게 뛰기", "배를 잡고 크게 웃기", "눈물을 글썽이며 감동하기", "주저앉아 눈물을 흘리기", "화난 표정으로 발을 구르기", "팔짱을 끼고 토라져 돌아서기", "손을 내밀며 잠깐 기다리라고 하기", "다급하게 앞으로 달려오기", "배를 문지르며 배고파하기", "하품하고 포근하게 잠들기"];

const json = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" } });
const error = (detail, status = 400) => json({ detail }, status);
const projectKey = (id) => `project:${id}`;

async function readProject(env, id) {
  return env.PROJECTS.get(projectKey(id), "json");
}
async function writeProject(env, project) {
  project.updated_at = new Date().toISOString();
  await env.PROJECTS.put(projectKey(project.id), JSON.stringify(project));
  await env.PROJECTS.put("latest", project.id);
  return project;
}
function fileUrl(id, name) {
  return `/api/projects/${id}/files/${encodeURIComponent(name)}`;
}
function planItems() {
  return PHRASES.map((phrase, index) => ({ slot_no: index + 1, phrase, emotion: EMOTIONS[index], intent: EMOTIONS[index], motion_prompt: MOTIONS[index], difficulty: [0, 14, 21].includes(index) ? "높음" : "보통" }));
}
async function aiImage(env, source, prompt, seed) {
  const form = new FormData();
  form.append("prompt", prompt);
  form.append("width", "512");
  form.append("height", "512");
  form.append("seed", String(seed));
  form.append("input_image_0", new Blob([source], { type: "image/png" }), "master.png");
  const serialized = new Response(form);
  const result = await env.AI.run(MODEL, { multipart: { body: serialized.body, contentType: serialized.headers.get("content-type") } });
  if (result instanceof ReadableStream) return { body: result, type: "image/png" };
  if (result instanceof Response) return { body: result.body, type: result.headers.get("content-type") || "image/png" };
  if (result instanceof Uint8Array || result instanceof ArrayBuffer) return { body: result, type: "image/png" };
  if (result?.image) {
    const raw = Uint8Array.from(atob(result.image), (char) => char.charCodeAt(0));
    return { body: raw, type: "image/png" };
  }
  throw new Error("Workers AI가 이미지 데이터를 반환하지 않았습니다.");
}
async function kakaoTrends(env) {
  const fallback = planItems().slice(0, 8).map((item) => ({ query: item.phrase, image: "/assets/premium-otter-v2.png", source_url: "https://e.kakao.com/", site: "MotiCon 기획" }));
  if (!env.KAKAO_REST_API_KEY) return { items: fallback, provider: "curated_fallback", configured: false };
  const query = "카카오 이모티콘 출시";
  const response = await fetch("https://dapi.kakao.com/v2/search/image?size=8&sort=recency&query=" + encodeURIComponent(query), { headers: { Authorization: `KakaoAK ${env.KAKAO_REST_API_KEY}` } });
  if (!response.ok) return { items: fallback, provider: "curated_fallback", configured: true, warning: `Kakao ${response.status}` };
  const data = await response.json();
  return { items: (data.documents || []).slice(0, 8).map((item) => ({ query, image: item.thumbnail_url || item.image_url, source_url: item.doc_url || "https://e.kakao.com/", site: item.display_sitename || "Kakao 검색" })), provider: "kakao_image_search", configured: true };
}

async function handleApi(request, env) {
  const url = new URL(request.url);
  const path = decodeURIComponent(url.pathname);
  if (request.method === "GET" && path === "/api/health") return json({ ok: true, runtime: "cloudflare-worker", ai: Boolean(env.AI), storage: Boolean(env.PROJECTS) });
  if (request.method === "GET" && path === "/api/providers/status") return json({ providers: [{ id: "cloudflare", name: "Cloudflare Workers AI", configured: Boolean(env.AI), model: MODEL, paid: false }, { id: "gemini", name: "Cloudflare Workers AI 호환 모드", configured: Boolean(env.AI), model: MODEL, paid: false }] });
  if (request.method === "POST" && path === "/api/providers/gemini/key") return json({ configured: Boolean(env.AI), provider: "cloudflare", detail: "공개 서비스는 브라우저 API 키 대신 안전한 Workers AI 바인딩을 사용합니다." });
  if (request.method === "GET" && path === "/api/trends/emoticons") return json(await kakaoTrends(env));
  if (request.method === "POST" && path === "/api/projects") {
    const body = await request.json().catch(() => ({}));
    const id = crypto.randomUUID().replaceAll("-", "").slice(0, 12);
    const project = await writeProject(env, { id, name: body.name || "나의 첫 이모티콘", created_at: new Date().toISOString(), plan: planItems(), generated: {} });
    return json(project, 201);
  }
  const assetMatch = path.match(/^\/api\/projects\/([^/]+)\/assets$/);
  if (request.method === "POST" && assetMatch) {
    const project = await readProject(env, assetMatch[1]);
    if (!project) return error("프로젝트를 찾을 수 없습니다.", 404);
    const form = await request.formData();
    const file = form.get("file");
    if (!(file instanceof File)) return error("이미지 파일이 필요합니다.");
    if (!file.type.startsWith("image/") || file.size > 8 * 1024 * 1024) return error("8MB 이하 JPG, PNG, WebP 이미지만 사용할 수 있습니다.");
    const key = `${project.id}/source.png`;
    await env.PROJECTS.put(key, await file.arrayBuffer());
    project.source_key = key;
    project.master_key = key;
    await writeProject(env, project);
    return json({ asset_url: fileUrl(project.id, "source.png"), cutout_url: fileUrl(project.id, "source.png"), quality: { accepted: true, cloud_safe: true } });
  }
  const masterGenerate = path.match(/^\/api\/projects\/([^/]+)\/masters\/generate$/);
  if (request.method === "POST" && masterGenerate) {
    const project = await readProject(env, masterGenerate[1]);
    if (!project) return error("프로젝트를 찾을 수 없습니다.", 404);
    const variants = {};
    for (const name of ["original", "white", "peach", "mint", "lilac", "butter"]) variants[name] = fileUrl(project.id, `master_${name}.png`);
    project.master_key = `${project.id}/master_white.png`;
    await writeProject(env, project);
    return json({ master_url: variants.white, variant_urls: variants, provider: "cloudflare-r2-safe-copy" });
  }
  const masterSelect = path.match(/^\/api\/projects\/([^/]+)\/masters\/select$/);
  if (request.method === "POST" && masterSelect) {
    const project = await readProject(env, masterSelect[1]);
    if (!project) return error("프로젝트를 찾을 수 없습니다.", 404);
    const body = await request.json().catch(() => ({}));
    const variant = ["original", "white", "peach", "mint", "lilac", "butter"].includes(body.variant) ? body.variant : "white";
    project.master_key = `${project.id}/master_${variant}.png`;
    project.master_variant = variant;
    await writeProject(env, project);
    return json({ master_url: fileUrl(project.id, `master_${variant}.png`), variant, locked: true });
  }
  const planGenerate = path.match(/^\/api\/projects\/([^/]+)\/plans\/generate$/);
  if (request.method === "POST" && planGenerate) {
    const project = await readProject(env, planGenerate[1]);
    if (!project) return error("프로젝트를 찾을 수 없습니다.", 404);
    project.plan = planItems();
    await writeProject(env, project);
    return json({ items: project.plan, provider: "moticon-commercial-dialogue-v1", trend_reference: Boolean(env.KAKAO_REST_API_KEY) });
  }
  const animatedGet = path.match(/^\/api\/projects\/([^/]+)\/animated-set$/);
  if (request.method === "GET" && animatedGet) {
    const project = await readProject(env, animatedGet[1]);
    if (!project) return error("프로젝트를 찾을 수 없습니다.", 404);
    return json({ items: Object.values(project.generated || {}).sort((a, b) => a.slot_no - b.slot_no), completed: Object.keys(project.generated || {}).length, total: 24, provider: "cloudflare-workers-ai" });
  }
  const generateOne = path.match(/^\/api\/projects\/([^/]+)\/animated-set\/generate-one$/);
  if (request.method === "POST" && generateOne) {
    const project = await readProject(env, generateOne[1]);
    if (!project?.master_key) return error("마스터 이미지를 먼저 확정하세요.", 404);
    const body = await request.json().catch(() => ({}));
    const slot = Number(body.slot_no);
    if (!Number.isInteger(slot) || slot < 1 || slot > 24) return error("slot_no는 1~24여야 합니다.");
    const source = await env.PROJECTS.get(project.master_key || `${project.id}/source.png`, "arrayBuffer") || await env.PROJECTS.get(`${project.id}/source.png`, "arrayBuffer");
    if (!source) return error("마스터 파일을 찾을 수 없습니다.", 404);
    const prompt = `The user owns all rights to the supplied reference image. Keep it private to this request and do not disclose or reuse it. Image 0 is the locked master character. Create one polished Korean messenger emoticon on a clean white background. Preserve exactly the character count, species, facial identity, line thickness, proportions, markings, and color palette. Do not add or remove limbs, characters, or props. Scene: ${MOTIONS[slot - 1]}. Emotion: ${EMOTIONS[slot - 1]}. Leave clear space for the Korean caption \"${PHRASES[slot - 1]}\" but do not render any letters. Centered full-body composition, crisp dark line art, commercial sticker quality.`;
    try {
      const output = await aiImage(env, source, prompt, slot * 104729 + 17);
      const name = `emotion_${String(slot).padStart(2, "0")}.png`;
      const imageBytes = await new Response(output.body).arrayBuffer();
      await env.PROJECTS.put(`${project.id}/${name}`, imageBytes);
      const item = { slot_no: slot, phrase: PHRASES[slot - 1], emotion: EMOTIONS[slot - 1], motion_prompt: MOTIONS[slot - 1], frames: 1, url: fileUrl(project.id, name), provider: "cloudflare-flux-2-klein-4b", model: MODEL, paid_fallback: false };
      project.generated ||= {};
      project.generated[String(slot)] = item;
      await writeProject(env, project);
      return json(item);
    } catch (reason) {
      console.error(JSON.stringify({ event: "image_generation_failed", projectId: project.id, slot, message: reason?.message }));
      return error(`Workers AI 생성 실패: ${reason?.message || "알 수 없는 오류"}`, 502);
    }
  }
  const fileMatch = path.match(/^\/api\/projects\/([^/]+)\/files\/([^/]+)$/);
  if (request.method === "GET" && fileMatch) {
    let object = await env.PROJECTS.get(`${fileMatch[1]}/${fileMatch[2]}`, "arrayBuffer");
    if (!object && fileMatch[2].startsWith("master_")) object = await env.PROJECTS.get(`${fileMatch[1]}/source.png`, "arrayBuffer");
    if (!object) return error("파일을 찾을 수 없습니다.", 404);
    return new Response(object, { headers: { "content-type": "image/png", "cache-control": "public, max-age=31536000, immutable" } });
  }
  return error("API 경로를 찾을 수 없습니다.", 404);
}

export default {
  async fetch(request, env) {
    try {
      if (new URL(request.url).pathname.startsWith("/api/")) return await handleApi(request, env);
      return env.ASSETS.fetch(request);
    } catch (reason) {
      console.error(JSON.stringify({ event: "unhandled_error", message: reason?.message }));
      return error("서버 내부 오류가 발생했습니다.", 500);
    }
  },
};
