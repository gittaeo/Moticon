import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Plus,
  FolderOpen,
  Settings,
  HelpCircle,
  ChevronRight,
  ChevronLeft,
  Upload,
  ImagePlus,
  Check,
  Lock,
  Palette,
  Sparkles,
  RefreshCw,
  Play,
  Pause,
  MessageSquare,
  Download,
  AlertTriangle,
  Coins,
  MoreHorizontal,
  X,
  Film,
  ScanFace,
  PackageCheck,
  ArrowUpRight,
  CheckCircle2,
  CircleDashed,
} from "lucide-react";
import "./styles.css";
import "./backend.css";
import "./premium.css";
const STEPS = [
  ["source", "01", "사진"],
  ["master", "02", "마스터"],
  ["plan", "03", "24개 구성"],
  ["batch", "04", "전체 생성"],
  ["edit", "05", "세트 편집"],
  ["export", "06", "결과 다운로드"],
];
const phrases = [
  "안녕!",
  "반가워",
  "잘 가",
  "고마워",
  "미안해",
  "사랑해",
  "좋아!",
  "최고야",
  "축하해",
  "화이팅",
  "대박",
  "헉!",
  "정말?",
  "왜?",
  "신난다",
  "너무 웃겨",
  "감동이야",
  "슬퍼",
  "화났어",
  "삐졌어",
  "기다려",
  "지금 가!",
  "배고파",
  "잘 자",
];
const motions = [
  "달려와 손 흔들기",
  "두 팔 벌려 웃기",
  "뒤돌아 인사하기",
  "두 손 모아 하트",
  "고개 숙여 사과",
  "볼 하트 만들기",
  "엄지척 점프",
  "두 엄지 반짝",
  "꽃가루 점프",
  "주먹 펌핑",
  "놀라며 확대",
  "뒤로 놀라기",
  "고개 갸웃",
  "양손 펼치기",
  "방방 뛰기",
  "배 잡고 웃기",
  "눈물 글썽",
  "주저앉아 울기",
  "발 구르기",
  "팔짱 끼기",
  "손 내밀며 달리기",
  "카메라로 달려오기",
  "배 만지기",
  "하품 후 잠들기",
];
const emotions = [
  "인사",
  "환영",
  "작별",
  "감사",
  "사과",
  "애정",
  "긍정",
  "칭찬",
  "축하",
  "응원",
  "놀람",
  "당황",
  "의문",
  "질문",
  "기쁨",
  "웃음",
  "감동",
  "슬픔",
  "화남",
  "토라짐",
  "요청",
  "이동",
  "일상",
  "취침",
];
async function apiJson(response) {
  const text = await response.text();
  let data = {};
  try { data = text ? JSON.parse(text) : {}; }
  catch { data = { detail: text || `서버 응답 오류 (${response.status})` }; }
  if (!response.ok) throw new Error(data.detail || `요청 실패 (${response.status})`);
  return data;
}
window.__projectId = window.__projectId || "bcc69af2e5e9";
window.__masterUrl =
  window.__masterUrl ||
  "/api/projects/bcc69af2e5e9/files/master_white.png";
function Mascot({ className = "", src }) {
  let live = className.startsWith("move") && window.__motionUrl;
  return (
    <img
      className={"mascot " + className}
      src={live || src || window.__masterUrl || ""}
      alt="업로드한 사진으로 만든 마스터 캐릭터"
    />
  );
}
function Status({ children, tone = "" }) {
  return (
    <span className={"status " + tone}>
      <i />
      {children}
    </span>
  );
}
function Shell({ step, setStep, children }) {
  return (
    <div className={"app " + (step === "home" ? "home-mode" : "studio-mode")}>
      <aside>
        <button className="brand" onClick={() => setStep("home")} aria-label="MotiCon 홈으로 이동">
          <b>m</b>
          <span>
            MotiCon<small>STUDIO</small>
          </span>
        </button>
        <button className="new" onClick={() => setStep("source")}>
          <Plus />새 프로젝트
        </button>
        <label>PRODUCTION</label>
        <nav>
          {STEPS.map(([id, n, x]) => (
            <button
              className={step === id ? "active" : ""}
              onClick={() => setStep(id)}
              key={id}
            >
              <em>{n}</em>
              {x}
              {["master", "plan"].includes(id) && <Check />}
            </button>
          ))}
        </nav>
        <div className="sidefoot">
          <button>
            <FolderOpen />
            프로젝트
          </button>
          <button>
            <Settings />
            환경 설정
          </button>
          <p>
            <i />
            LOCAL MODE<small>파일은 내 PC에 저장됩니다</small>
          </p>
        </div>
      </aside>
      <section className="workspace">
        <header>
          {step === "home" ? (
            <button className="home-wordmark" onClick={() => setStep("home")}>
              <b>m</b><span>MotiCon</span>
            </button>
          ) : (
            <div>
              <button className="project-home-link" onClick={() => setStep("home")} aria-label="MotiCon 홈으로 이동">MotiCon</button>
              <span>/</span>나의 첫 이모티콘{" "}
              <Status tone="green">자동 저장됨</Status>
            </div>
          )}
          <div className="top">
            <span>
              <Coins />
              무료 크레딧 <b>82%</b>
            </span>
            <HelpCircle />
            <button>ME</button>
          </div>
        </header>
        <main>{children}</main>
        <GrokDock />
      </section>
    </div>
  );
}
function Home({ start, openProject }) {
  const [trends, setTrends] = useState([]), [trendState, setTrendState] = useState("loading");
  useEffect(() => {
    fetch("/api/trends/emoticons").then(apiJson).then((data) => {
      setTrends(data.items || []); setTrendState("ready");
    }).catch(() => setTrendState("unavailable"));
  }, []);
  const previews = [
    ["안녕!", "/api/projects/bcc69af2e5e9/files/motion_02_ai_keyframes.webp?v=5frame-lossless-2", "WAVE"],
    ["고마워", "/api/projects/bcc69af2e5e9/files/static_04_existing.png", "BOW"],
    ["사랑해", "/api/projects/bcc69af2e5e9/files/static_06_existing.png", "HEART"],
    ["화났어", "/api/projects/bcc69af2e5e9/files/static_19_existing.png", "SHAKE"],
  ];
  return (
    <div className="landing">
      <section className="hero">
        <div className="hero-copy">
          <span className="eyebrow"><Sparkles /> ONE IMAGE, FULL EMOTION SET</span>
          <h1>한 장의 캐릭터가<br/><em>24개의 감정</em>으로 살아나요</h1>
          <p>원본 그림이나 사진만 올려주세요. 캐릭터의 정체성은 그대로 지키고, 표정과 몸짓이 살아 있는 이모티콘 세트를 만듭니다.</p>
          <div className="hero-actions">
            <button className="hero-primary" onClick={start}>무료로 새 세트 만들기 <ArrowUpRight /></button>
            <button className="hero-secondary" onClick={openProject}><Play /> 작업 중인 세트 보기</button>
          </div>
          <div className="hero-proof"><span><Check /> 원본 디자인 잠금</span><span><Check /> 24개 자동 기획</span><span><Check /> PNG·WebP 출력</span></div>
        </div>
        <div className="hero-stage" aria-label="움직이는 이모티콘 미리보기">
          <div className="orbit orbit-one"/><div className="orbit orbit-two"/>
          <span className="floating-pill pill-one">표정 변화</span>
          <span className="floating-pill pill-two">5+ KEYFRAMES</span>
          <div className="hero-card">
            <span>MOTION STYLE PREVIEW</span>
            <img className="demo-wave" src={previews[0][1]} alt="손 흔들기 동작 예시" />
            <footer><b>안녕!</b><small>동작 설계 미리보기</small></footer>
          </div>
        </div>
      </section>
      <section className="home-section">
        <header><span>MADE WITH MOTICON</span><h2>그림체는 그대로, 감정은 더 풍부하게</h2><p>밀거나 흔드는 효과가 아니라 캐릭터가 직접 연기하는 프레임을 설계합니다.</p></header>
        <div className="motion-showcase">
          {previews.map(([title, src, tag], i) => (
            <article key={title} style={{"--delay": `${i * .18}s`}}>
              <div><span>{tag}</span><img className={`demo-motion demo-${tag.toLowerCase()}`} src={src} alt={`${title} 동작 디자인 예시`} /></div>
              <footer><b>{title}</b><small>MOTION DIRECTION</small><Play /></footer>
            </article>
          ))}
        </div>
      </section>
      <section className="flow-strip">
        <div><small>01</small><b>원본 업로드</b><span>사진·그림 한 장</span></div>
        <ChevronRight />
        <div><small>02</small><b>마스터 잠금</b><span>선·색·특징 보존</span></div>
        <ChevronRight />
        <div><small>03</small><b>24개 감정 생성</b><span>표정·대사·동작</span></div>
        <ChevronRight />
        <div><small>04</small><b>한 번에 다운로드</b><span>PNG·WebP·ZIP</span></div>
      </section>
      <section className="trend-section">
        <header>
          <div><span>KAKAO SEARCH · DAILY</span><h2>오늘 새로 발견한 이모티콘</h2><p>카카오 Daum 검색 API의 최신 결과입니다. 이미지는 저장하지 않고 원문으로 연결합니다.</p></div>
          <em>{trendState === "ready" ? `매일 갱신 · ${trends.length}개` : trendState === "loading" ? "불러오는 중" : "API 연결 확인 필요"}</em>
        </header>
        {trendState === "ready" && trends.length > 0 ? (
          <div className="trend-grid">
            {trends.slice(0,8).map((item,i) => (
              <a href={item.source_url} target="_blank" rel="noreferrer" key={`${item.source_url}-${i}`}>
                <div><img src={item.image} alt={`${item.query} 검색 결과`} loading="lazy" /></div>
                <footer><span><b>{item.query.replace(" 출시","")}</b><small>{item.site} · 원문 보기</small></span><ArrowUpRight /></footer>
              </a>
            ))}
          </div>
        ) : <div className="trend-empty"><Sparkles /><b>{trendState === "loading" ? "최신 이모티콘을 찾고 있어요" : "카카오 REST API 연결 상태를 확인해 주세요"}</b></div>}
        <small className="trend-notice">검색 썸네일의 권리는 각 원저작자에게 있으며 MotiCon은 원본 이미지를 저장하거나 학습에 사용하지 않습니다.</small>
      </section>
    </div>
  );
}
function Head({ kicker, title, desc, children }) {
  return (
    <div className="head">
      <div>
        <label>{kicker}</label>
        <h1>{title}</h1>
        <p>{desc}</p>
      </div>
      {children}
    </div>
  );
}
function Source({ process, busy, error }) {
  const [file, setFile] = useState(),
    ref = useRef();
  return (
    <div className="page small">
      <Head
        kicker="SOURCE / 01"
        title="좋은 캐릭터는 좋은 사진에서 시작해요"
        desc="정면이 잘 보이는 JPG 한 장을 올려주세요. 추가 사진은 나중에도 보강할 수 있어요."
      />
      <div className="source">
        <div className="drop" onClick={() => ref.current.click()}>
          <input
            ref={ref}
            hidden
            type="file"
            accept="image/jpeg"
            onChange={(e) => setFile(e.target.files[0])}
          />
          <div>
            <Upload />
          </div>
          <h3>{file ? file.name : "JPG 사진을 놓아주세요"}</h3>
          <p>
            {file
              ? "사진이 준비됐습니다."
              : "클릭하거나 파일을 끌어다 놓기 · 긴 변 1,500px 이상 권장"}
          </p>
          <button>사진 선택</button>
        </div>
        <div className="guide">
          <h3>
            <ScanFace />
            입력 품질 체크
          </h3>
          {[
            "얼굴과 주요 특징이 선명함",
            "손과 상체가 프레임 안에 있음",
            "복잡하지 않은 배경",
            "본인이 사용 권리를 가진 사진",
          ].map((x, i) => (
            <div key={x}>
              <span>{i + 1}</span>
              <p>
                <b>{x}</b>
                <small>
                  {
                    [
                      "닮은 마스터를 만드는 핵심이에요",
                      "전신 동작 완성도가 높아져요",
                      "캐릭터 분리가 정확해져요",
                      "초상권과 저작권을 확인해 주세요",
                    ][i]
                  }
                </small>
              </p>
            </div>
          ))}
        </div>
      </div>
      <label className="rights">
        <input type="checkbox" defaultChecked />
        <span>
          <b>업로드할 사진의 사용 권리를 가지고 있습니다.</b>
          <small>외부 AI로 전송하기 전 사용 범위를 다시 확인합니다.</small>
        </span>
      </label>
      {error && (
        <div className="api-error">
          <AlertTriangle />
          {error}
        </div>
      )}
      <Foot
        text={
          busy
            ? "무료 파이프라인 실행 중입니다."
            : "원본의 위치 정보는 작업 사본에서 제거돼요."
        }
      >
        <button
          className="primary"
          disabled={!file || busy}
          onClick={() => process(file)}
        >
          {busy ? (
            <>
              <RefreshCw />
              분석·마스터 생성 중
            </>
          ) : (
            <>
              무료 AI로 제작 시작
              <ChevronRight />
            </>
          )}
        </button>
      </Foot>
    </div>
  );
}
function Master({ next, masterUrl }) {
  const [sel, setSel] = useState(0),
    keys = ["original", "white", "peach", "mint", "lilac", "butter"],
    names = [
      "원본 색감 유지",
      "깨끗한 흰색",
      "따뜻한 피치",
      "산뜻한 민트",
      "부드러운 라일락",
      "밝은 버터",
    ];
  if (masterUrl) window.__masterUrl = masterUrl;
  const choose = async () => {
    let r = await fetch(`/api/projects/${window.__projectId}/masters/select`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ variant: keys[sel] }),
    });
    let d = await r.json();
    if (r.ok) {
      window.__masterUrl = d.master_url;
      next();
    }
  };
  return (
    <div className="page">
      <Head
        kicker="MASTER CHARACTER / 02"
        title="캐릭터의 색과 분위기를 정해요"
        desc="원본 색감을 유지하거나, 종이·회색 질감을 지운 깨끗한 흰색과 브랜드용 단색 분위기를 선택하세요."
      >
        <Status>마스터 분위기 선택</Status>
      </Head>
      <div className="masters palette-grid">
        {names.map((x, i) => {
          let src = window.__projectId
            ? `/api/projects/${window.__projectId}/files/master_${keys[i]}.png`
            : masterUrl;
          return (
            <button
              className={sel === i ? "selected" : ""}
              onClick={() => setSel(i)}
              key={x}
            >
              <div className="art master-white">
                <Mascot src={src} />
              </div>
              <span>
                <small>
                  {i === 0
                    ? "ORIGINAL"
                    : i === 1
                      ? "CLEAN WHITE"
                      : "PALETTE " + String(i - 1).padStart(2, "0")}
                </small>
                <b>{x}</b>
              </span>
              {sel === i ? <CheckCircle2 /> : <CircleDashed />}
            </button>
          );
        })}
      </div>
      <div className="manifest">
        <header>
          <span>
            <Palette />
            BRAND MOOD
          </span>
          <small>확정한 선·채색을 24개 전체에 잠금</small>
        </header>
        <div>
          {[
            "원본색 또는 단색 선택",
            "종이 회색 제거",
            "어두운 선 보존",
            "흰색 화면 미리보기",
            "PNG 배경 투명",
            "선택 분위기 잠금",
          ].map((x) => (
            <span key={x}>{x}</span>
          ))}
        </div>
      </div>
      <Foot>
        <button className="back">
          <ChevronLeft />
          이전
        </button>
        <span>여기서 고른 색감이 표정·포즈·모션 전체의 기준이 됩니다.</span>
        <button className="primary" onClick={choose}>
          <Lock />이 분위기로 마스터 확정
        </button>
      </Foot>
    </div>
  );
}
function Plan({ next }) {
  const [planning, setPlanning] = useState(true),
    [filter, setFilter] = useState("전체"),
    [motionError, setMotionError] = useState(""),
    [, redraw] = useState(0);
  const apply = (pd) => {
    if (!pd.items) return;
    window.__planItems = pd.items;
    phrases.splice(0, phrases.length, ...pd.items.map((x) => x.phrase));
    motions.splice(0, motions.length, ...pd.items.map((x) => x.motion_prompt));
    emotions.splice(0, emotions.length, ...pd.items.map((x) => x.emotion));
    redraw((x) => x + 1);
  };
  const regenerate = async () => {
    if (!window.__projectId) return;
    setPlanning(true);
    try {
      let r = await fetch(
        `/api/projects/${window.__projectId}/plans/generate`,
        { method: "POST" },
      );
      let d = await r.json();
      if (r.ok) apply(d);
    } finally {
      setPlanning(false);
    }
  };
  useEffect(() => {
    regenerate();
  }, []);
  const prepare = async () => {
    setMotionError("");
    next();
  };
  const daily = new Set([
    "인사",
    "환영",
    "작별",
    "감사",
    "사과",
    "요청",
    "이동",
    "일상",
    "취침",
  ]);
  const visible = phrases
    .map((_, i) => i)
    .filter((i) => {
      let item = window.__planItems?.[i];
      if (filter === "전체") return true;
      if (filter === "고난도")
        return item?.difficulty === "높음" || [0, 14, 21].includes(i);
      if (filter === "일상") return daily.has(item?.intent || emotions[i]);
      return !daily.has(item?.intent || emotions[i]);
    });
  return (
    <div className="page wide">
      <Head
        kicker="STICKER PLAN / 03"
        title={
          planning
            ? "마스터 기준으로 장면을 준비하고 있어요"
            : "24개의 대화 장면을 설계했어요"
        }
        desc="문구와 표정, 전신 동작이 겹치지 않도록 균형 있게 구성했습니다."
      >
        <div className="actions">
          <button disabled={planning} onClick={regenerate}>
            <RefreshCw className={planning ? "spin" : ""} />
            {planning ? "재구성 중" : "전체 재구성"}
          </button>
          <button className="primary" disabled={planning} onClick={prepare}>
            {planning ? (
              <>
                <RefreshCw />
                준비 중
              </>
            ) : (
              <>
                구성 확정
                <ChevronRight />
              </>
            )}
          </button>
        </div>
      </Head>
      <div className="toolbar">
        <div>
          {["전체", "일상", "감정", "고난도"].map((x) => (
            <button
              key={x}
              className={filter === x ? "active" : ""}
              onClick={() => setFilter(x)}
            >
              {x}
            </button>
          ))}
        </div>
        <span>
          <b>{visible.length}</b>/24 표시 · 모션은 확정할 때만 생성
        </span>
      </div>
      <div className="plans">
        {visible.map((i) => {
          let p = phrases[i];
          return (
            <article
              className={[0, 14, 21].includes(i) ? "sample" : ""}
              key={`${i}-${p}`}
            >
              <header>
                <span>{String(i + 1).padStart(2, "0")}</span>
                {[0, 14, 21].includes(i) && <em>SAMPLE</em>}
                <MoreHorizontal />
              </header>
              <div className="thumb">
                <Mascot />
                <strong>{p}</strong>
              </div>
              <footer>
                <span>{emotions[i]}</span>
                <p>{motions[i]}</p>
                <small>
                  {window.__planItems?.[i]?.difficulty === "높음" || i % 3 === 0
                    ? "고난도 · 2.0초"
                    : "보통 · 1.6초"}
                </small>
              </footer>
            </article>
          );
        })}
      </div>
      {motionError && <div className="api-error"><AlertTriangle />{motionError}</div>}
    </div>
  );
}
function Samples({ next }) {
  const [ok, setOk] = useState([false, false, false]),
    [play, setPlay] = useState(true),
    [clips, setClips] = useState({}),
    data = [
      ["지금 가!", "멀리서 카메라 앞으로 달려오기", "원근·전신"],
      ["안녕!", "화면 밖에서 들어와 손 흔들기", "손·표정"],
      ["신난다", "두 팔 들고 세 번 방방 뛰기", "관절·루프"],
    ];
  useEffect(() => {
    const load = () =>
      window.__projectId &&
      fetch(`/api/projects/${window.__projectId}/motions`)
        .then((r) => r.json())
        .then((d) =>
          setClips(Object.fromEntries(d.items.map((x) => [x.slot_no, x.url]))),
        );
    load();
    window.addEventListener("motion-imported", load);
    return () => window.removeEventListener("motion-imported", load);
  }, []);
  return (
    <div className="page">
      <Head
        kicker="QUALITY GATE / 04"
        title="캐릭터가 실제로 연기하는 동작 3개를 확인해요"
        desc="그림 전체 이동은 모션으로 인정하지 않습니다. 표정·팔·다리·몸통이 장면에 맞게 변해야 승인할 수 있어요."
      >
        <button className="play" onClick={() => setPlay(!play)}>
          {play ? <Pause /> : <Play />}
          {play ? "모두 멈춤" : "동시 재생"}
        </button>
      </Head>
      <div className="samples">
        {data.map((s, i) => {
          let clip = clips[i + 1];
          return (
            <article key={s[0]}>
              <div className="preview">
                <span>0{i + 1}</span>
                {clip ? (
                  <img
                    src={clip}
                    className={!play ? "paused-motion" : ""}
                    alt={`${s[0]} 실제 모션`}
                  />
                ) : (
                  <div className="motion-empty">
                    <Sparkles />
                    <b>실제 모션 영상 필요</b>
                    <small>
                      Grok 연동에서 {i + 1}번 영상을 생성해 가져오세요
                    </small>
                  </div>
                )}
                <strong>{s[0]}</strong>
                <button>
                  <RefreshCw />
                </button>
              </div>
              <div className="sampleinfo">
                <span>
                  <small>{s[2]} 검증</small>
                  <b>{s[1]}</b>
                </span>
                <button
                  disabled={!clip}
                  className={ok[i] ? "approved" : ""}
                  onClick={() =>
                    setOk((a) => a.map((v, j) => (j === i ? !v : v)))
                  }
                >
                  {ok[i] ? (
                    <>
                      <Check />
                      승인됨
                    </>
                  ) : clip ? (
                    "승인하기"
                  ) : (
                    "영상 필요"
                  )}
                </button>
              </div>
              <div className="comment">
                <MessageSquare />
                표정·관절·몸짓 변화와 캐릭터 일관성을 확인하세요
                <ChevronRight />
              </div>
            </article>
          );
        })}
      </div>
      <div className="gate">
        <div>
          {ok.filter(Boolean).length}
          <small>/3</small>
        </div>
        <span>
          <b>실제 모션 승인 게이트</b>
          <small>
            {ok.every(Boolean)
              ? "모든 실제 모션 샘플을 승인했습니다."
              : "실제 영상이 있는 세 장면을 모두 승인해야 합니다."}
          </small>
        </span>
        <button disabled={!ok.every(Boolean)} onClick={next}>
          나머지 21개 생성
          <ChevronRight />
        </button>
      </div>
    </div>
  );
}
function Batch({ next }) {
  const [items, setItems] = useState([]),
    [running, setRunning] = useState(false),
    [current, setCurrent] = useState(0),
    [error, setError] = useState(""),
    [zip, setZip] = useState("");
  const stopAfterCurrent = useRef(false);
  const load = async () => {
    const response = await fetch(`/api/projects/${window.__projectId}/animated-set`);
    const data = await response.json();
    if (response.ok) setItems(data.items || []);
  };
  useEffect(() => { load(); }, []);
  const generate = async () => {
    setRunning(true); setError(""); stopAfterCurrent.current = false;
    const complete = new Set(items.map((item) => item.slot_no));
    for (let slot = 1; slot <= 24; slot += 1) {
      if (complete.has(slot)) continue;
      if (stopAfterCurrent.current) break;
      setCurrent(slot);
      const response = await fetch(`/api/projects/${window.__projectId}/animated-set/generate-one`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ slot_no: slot }),
      });
      const data = await response.json();
      if (!response.ok) { setError(data.detail || `#${slot} 생성이 중단됐습니다.`); break; }
      complete.add(slot); await load();
      await new Promise((resolve) => setTimeout(resolve, 1200));
    }
    setCurrent(0); setRunning(false);
  };
  const pause = () => { stopAfterCurrent.current = true; };
  const exportZip = async () => {
    setError("");
    const response = await fetch(`/api/projects/${window.__projectId}/animated-set/export`, { method: "POST" });
    const data = await response.json();
    if (response.ok) setZip(data.download_url); else setError(data.detail || "ZIP 생성 실패");
  };
  const done = items.length;
  return (
    <div className="page">
      <Head
        kicker="GENERATION QUEUE / 05"
        title="24개의 감정을 5프레임씩 만들어요"
        desc="마스터의 그림체와 캐릭터 수를 잠그고, 표정과 실제 팔다리 동작만 장면별로 바꿉니다."
      >
        <Status tone={running ? "blue" : done === 24 ? "green" : "amber"}>
          {running ? `#${current} 생성 중` : done === 24 ? "24개 완성" : "이어 만들기 가능"}
        </Status>
      </Head>
      <div className="progressbox">
        <div>
          <span>
            <small>OVERALL PROGRESS</small>
            <b>
              {done}
              <em>/24</em>
            </b>
          </span>
          <span>
            <small>예상 남은 시간</small>
            <b>{running ? "항목당 수 분" : "—"}</b>
          </span>
        </div>
        <div className="bar">
          <i style={{ width: `${(done / 24) * 100}%` }} />
        </div>
        <footer>
          <span>
            ✓ 완료 <b>{done}</b>
          </span>
          <span>
            ◌ 대기 <b>{24 - done}</b>
          </span>
          <span>
            ◉ 유료 사용 <b>₩0</b>
          </span>
          {running ? <button onClick={pause}><Pause />현재 항목 후 정지</button> : <button onClick={generate}><Play />{done ? "이어서 생성" : "24개 생성 시작"}</button>}
        </footer>
      </div>
      <div className="queue">
        <header>
          <b>작업 큐</b>
          <small>동시 작업 1개 · 무료 할당량 종료 시 자동 중지 · 완료분 저장</small>
        </header>
        {phrases.map((p, i) => {
          const slot=i+1, saved=items.find((item)=>item.slot_no===slot);
          let state = saved ? "done" : current === slot && running ? "running" : "waiting";
          return (
            <div className="job" key={p}>
              <div>
                <Mascot />
              </div>
              <span>
                <b>
                  #{String(slot).padStart(2, "0")} {saved?.phrase || p}
                </b>
                <small>
                  {state === "done"
                    ? `${saved.frames || 5}개 키프레임 WebP 저장 완료`
                    : state === "running"
                      ? "Gemini가 표정·동작 5프레임 생성 중"
                      : "무료 작업 대기 중"}
                </small>
              </span>
              <Status
                tone={
                  state === "done" ? "green" : state === "running" ? "blue" : ""
                }
              >
                {state === "done"
                  ? "완료"
                  : state === "running"
                    ? "생성 중"
                    : "대기"}
              </Status>
              <MoreHorizontal />
            </div>
          );
        })}
      </div>
      <div className="cost">
        <Coins />
        <span>
          <b>무료 우선 모드가 켜져 있어요</b>
          <small>카카오 검색은 최신 상황 키워드 참고에만 사용하고 원작 이미지는 복제·학습하지 않습니다. 무료 한도가 끝나면 자동으로 멈춥니다.</small>
        </span>
        <button onClick={exportZip}>현재 결과 ZIP</button>
      </div>
      {zip && <a className="download-btn batch-download" href={zip} download><Download /> 움직이는 세트 ZIP 다운로드</a>}
      {error && <div className="api-error"><AlertTriangle />{error}</div>}
      <Foot text="현재까지의 결과는 모두 안전하게 저장됐습니다.">
        <button className="primary" disabled={!done} onClick={next}>
          세트 편집실 열기
          <ChevronRight />
        </button>
      </Foot>
    </div>
  );
}
function Edit({ next }) {
  const [sel, setSel] = useState(0),
    [msg, setMsg] = useState("");
  return (
    <div className="page wide">
      <Head
        kicker="SET EDITOR / 06"
        title="필요한 한 장면만 대화하듯 고쳐요"
        desc="수정 범위를 분석해 필요한 단계만 다시 실행합니다."
      >
        <button className="primary" onClick={next}>
          QC 시작
          <ChevronRight />
        </button>
      </Head>
      <div className="editor">
        <div className="stickers">
          {phrases.map((p, i) => (
            <button
              className={sel === i ? "selected" : ""}
              onClick={() => setSel(i)}
              key={p}
            >
              <span>{i + 1}</span>
              <Mascot />
              <b>{p}</b>
              {i % 7 === 0 && <em>수정 1</em>}
            </button>
          ))}
        </div>
        <section className="chatpanel">
          <header>
            <span>
              <small>#{String(sel + 1).padStart(2, "0")}</small>
              <b>{phrases[sel]}</b>
            </span>
            <X />
          </header>
          <div className="large">
            <Mascot />
            <strong>{phrases[sel]}</strong>
          </div>
          <div className="revision">
            <span>V2 · 현재 적용</span>
            <button>버전 비교</button>
          </div>
          <div className="chat">
            <p>
              <Sparkles />
              어떤 부분을 바꿀까요? 잠긴 외형은 유지할게요.
            </p>
            {sel % 7 === 0 && (
              <div>손가락은 자연스럽게, 표정은 더 신나게 해줘.</div>
            )}
          </div>
          <div className="composer">
            <textarea
              value={msg}
              onChange={(e) => setMsg(e.target.value)}
              placeholder="수정할 내용을 자연스럽게 적어주세요"
            />
            <button disabled={!msg}>
              <ArrowUpRight />
            </button>
            <small>예: 마지막 프레임이 튀지 않게 이어줘</small>
          </div>
        </section>
      </div>
    </div>
  );
}
function StaticStudio() {
  const [items, setItems] = useState([]);
  const [running, setRunning] = useState(false);
  const [current, setCurrent] = useState(0);
  const [error, setError] = useState("");
  const [zip, setZip] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [keyStatus, setKeyStatus] = useState("");
  const [savingKey, setSavingKey] = useState(false);
  const load = () =>
    fetch(`/api/projects/${window.__projectId}/static-set`)
      .then((r) => r.json())
      .then((d) => setItems(d.items || []));
  useEffect(() => {
    load();
  }, []);
  const generate = async () => {
    setRunning(true);
    setError("");
    const done = new Set(items.map((x) => x.slot_no));
    for (let slot = 1; slot <= 24; slot += 1) {
      if (done.has(slot)) continue;
      setCurrent(slot);
      const r = await fetch(
        `/api/projects/${window.__projectId}/static-set/generate-one`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ slot_no: slot }),
        },
      );
      const d = await r.json();
      if (!r.ok) {
        setError(d.detail || "이미지 생성이 중단됐습니다.");
        break;
      }
      await load();
    }
    setCurrent(0);
    setRunning(false);
  };
  const exportZip = async () => {
    const r = await fetch(
      `/api/projects/${window.__projectId}/static-set/export`,
      { method: "POST" },
    );
    const d = await r.json();
    if (r.ok) setZip(d.download_url);
    else setError(d.detail || "ZIP 생성 실패");
  };
  const connectKey = async () => {
    if (!apiKey.trim()) return;
    setSavingKey(true);
    setKeyStatus("");
    const r = await fetch("/api/providers/gemini/key", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: apiKey.trim() }),
    });
    const d = await r.json();
    if (r.ok) {
      setApiKey("");
      setError("");
      setKeyStatus(
        d.image_models?.length
          ? `연결 완료 · 이미지 모델 ${d.image_models.length}개 확인`
          : "키는 연결됐지만 이미지 생성 모델이 확인되지 않았습니다.",
      );
    } else setKeyStatus(d.detail || "API 키 연결 실패");
    setSavingKey(false);
  };
  return (
    <section className="static-studio">
      <div className="static-master">
        <img src={window.__masterUrl} alt="잠긴 마스터 캐릭터" />
        <span>
          <small>MASTER IDENTITY · LOCKED</small>
          <b>이 캐릭터 그대로 24장을 만듭니다</b>
          <em>귀·얼굴·선·흰색 몸·딸기·두 캐릭터 구성을 매 요청에 고정</em>
        </span>
        <Lock />
      </div>
      <div className="static-runner">
        <div>
          <small>GEMINI STATIC SET</small>
          <b>{items.length}<em>/24</em></b>
          <p>
            {running
              ? `#${String(current).padStart(2, "0")} 표정과 자세 생성 중`
              : "정지 이미지 24장 · 유료 대체 호출 차단"}
          </p>
        </div>
        <div className="static-actions">
          <button className="primary" disabled={running} onClick={generate}>
            {running ? <RefreshCw className="spin" /> : <Sparkles />}
            {items.length ? "남은 이미지 이어서 생성" : "마스터 잠금하고 24장 생성"}
          </button>
          <button disabled={!items.length} onClick={exportZip}>
            <PackageCheck /> 현재 결과 ZIP 만들기
          </button>
          {zip && (
            <a className="download-btn" href={zip} download>
              <Download /> ZIP 다운로드
            </a>
          )}
        </div>
      </div>
      <div className="gemini-key-box">
        <span>
          <small>GOOGLE AI STUDIO</small>
          <b>Gemini API 키 연결</b>
          <em>키는 이 PC의 서버 설정에만 저장되며 화면에 다시 표시되지 않습니다.</em>
        </span>
        <input
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder="AIza... API 키 붙여넣기"
          autoComplete="off"
        />
        <button disabled={!apiKey.trim() || savingKey} onClick={connectKey}>
          {savingKey ? <RefreshCw className="spin" /> : <Lock />}
          {savingKey ? "확인 중" : "안전하게 연결"}
        </button>
        {keyStatus && <strong>{keyStatus}</strong>}
      </div>
      {error && (
        <div className="api-error">
          <AlertTriangle /> {error}
        </div>
      )}
      {!!items.length && (
        <div className="static-grid">
          {items.map((x) => (
            <article key={x.slot_no}>
              <img src={x.url} alt={`정적 이모티콘 ${x.slot_no}`} />
              <footer>
                <b>#{String(x.slot_no).padStart(2, "0")}</b>
                <a href={x.url} download={`moticon_${x.slot_no}.png`}>
                  <Download /> PNG
                </a>
              </footer>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function Results() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    fetch(`/api/projects/${window.__projectId}/animated-set`)
      .then((r) => r.json())
      .then((d) => setItems(d.items || []))
      .finally(() => setLoading(false));
  }, []);
  return (
    <div className="page">
      <Head
        kicker="ANIMATED SET / 06"
        title="완성된 움직이는 이모티콘을 받아보세요"
        desc="각 항목은 마스터를 기준으로 생성한 5개 동작 프레임의 무손실 WebP입니다."
      >
        <Status tone="green">{items.length}개 완성</Status>
      </Head>
      {loading ? (
        <div className="result-empty">
          <RefreshCw className="spin" /> 결과를 불러오는 중
        </div>
      ) : (
        <div className="result-grid">
          {items.map((x) => (
            <article key={x.slot_no}>
              <div className="result-preview">
                <img
                  src={x.url}
                  alt={`${x.phrase || x.slot_no} 움직이는 이모티콘`}
                />
              </div>
              <div className="result-info">
                <span>
                  <small>
                    #{String(x.slot_no).padStart(2, "0")} · ANIMATED WEBP
                  </small>
                  <b>{x.phrase || `이모티콘 ${x.slot_no}`}</b>
                  <em>{x.emotion || "감정"} · {x.frames || 5}개 키프레임</em>
                </span>
                <a
                  className="download-btn"
                  href={x.url}
                  download={`moticon_${String(x.slot_no).padStart(2, "0")}.webp`}
                >
                  <Download /> WebP 다운로드
                </a>
              </div>
            </article>
          ))}
        </div>
      )}
      <div className="download-note">
        <Film />
        <span>
          <b>{items.length}/24개가 안전하게 저장되어 있습니다.</b>
          <small>무료 할당량이 끝나도 전체 생성 화면에서 남은 항목부터 이어 만들 수 있습니다.</small>
        </span>
      </div>
    </div>
  );
}

function Export() {
  let checks = [
    ["캔버스", "740 × 640 px", "24/24", 1],
    ["파일 용량", "GIF당 1MB 이하", "23/24", 0],
    ["프레임", "100프레임 이하", "24/24", 1],
    ["자연스러운 루프", "첫·마지막 프레임 일치", "23/24", 0],
    ["투명 배경", "알파 채널 검사", "24/24", 1],
    ["한글 문구", "오탈자·잘림 검사", "24/24", 1],
  ];
  return (
    <div className="page">
      <Head
        kicker="QUALITY CONTROL / 07"
        title="제출 파일을 마지막으로 점검해요"
        desc="파일 규격 통과와 플랫폼 심사 통과는 서로 다릅니다."
      >
        <Status tone="amber">검사 2개 남음</Status>
      </Head>
      <div className="exports">
        <section>
          <div className="score">
            <b>
              92<small>/100</small>
            </b>
            <span>
              <strong>세트 품질이 좋아요</strong>
              <small>24개 중 22개가 모든 자동 검사를 통과했습니다.</small>
            </span>
          </div>
          <div className="checks">
            {checks.map((x) => (
              <div key={x[0]}>
                <i className={x[3] ? "pass" : "warn"}>
                  {x[3] ? <Check /> : <AlertTriangle />}
                </i>
                <span>
                  <b>{x[0]}</b>
                  <small>{x[1]}</small>
                </span>
                <em>{x[2]}</em>
                <ChevronRight />
              </div>
            ))}
          </div>
        </section>
        <aside className="package">
          <div>
            <PackageCheck />
          </div>
          <h2>OGQ 제출 패키지</h2>
          <p>움직이는 스티커 24개와 대표·탭 이미지를 한 번에 정리합니다.</p>
          <section>
            <span>
              <Film />
              animated <b>24 GIF</b>
            </span>
            <span>
              <ImagePlus />
              main.png <b>240×240</b>
            </span>
            <span>
              <ImagePlus />
              tab.png <b>96×74</b>
            </span>
          </section>
          <button disabled>
            <Download />
            문제 2개 수정 후 ZIP 만들기
          </button>
          <article>
            <AlertTriangle />
            <p>
              <b>심사 정책 안내</b>
              <small>
                규격을 충족해도 생성형 AI 콘텐츠는 OGQ 정책에 따라 반려될 수
                있습니다. 승인이나 판매를 보장하지 않습니다.
              </small>
            </p>
          </article>
        </aside>
      </div>
    </div>
  );
}
function GrokDock() {
  const [open, setOpen] = useState(false),
    [data, setData] = useState(),
    [tab, setTab] = useState("master"),
    [file, setFile] = useState(),
    [msg, setMsg] = useState("");
  const show = async () => {
    if (!window.__projectId) {
      setMsg("먼저 JPG 사진으로 프로젝트를 시작하세요.");
      setOpen(true);
      return;
    }
    let r = await fetch(`/api/projects/${window.__projectId}/handoffs/grok`);
    setData(await r.json());
    setOpen(true);
  };
  const copy = async (text) => {
    await navigator.clipboard.writeText(text);
    setMsg("프롬프트를 복사했습니다. Grok Imagine에 붙여넣으세요.");
  };
  const upload = async () => {
    if (!file) return;
    let f = new FormData();
    f.append("file", file);
    let r = await fetch(
      `/api/projects/${window.__projectId}/handoffs/grok/import?kind=${tab}`,
      { method: "POST", body: f },
    );
    let d = await r.json();
    if (!r.ok) {
      setMsg(d.detail || "가져오기 실패");
      return;
    }
    if (tab === "master") window.location.reload();
    else window.__motionUrl = d.url;
    setMsg("프로젝트에 가져왔습니다. API 비용은 0원입니다.");
  };
  return (
    <>
      <button className="grok-fab" onClick={show}>
        <Sparkles />
        Grok 무료 웹 연동
      </button>
      {open && (
        <div className="grok-overlay" onClick={() => setOpen(false)}>
          <section className="grok-modal" onClick={(e) => e.stopPropagation()}>
            <header>
              <div>
                <small>MANUAL HANDOFF · API ₩0</small>
                <h2>Grok Imagine에서 만들기</h2>
              </div>
              <button onClick={() => setOpen(false)}>
                <X />
              </button>
            </header>
            <p className="grok-note">
              웹 무료 사용량으로 직접 생성한 뒤 결과만 다시 가져옵니다. xAI
              API는 호출하지 않아요.
            </p>
            <nav>
              <button
                className={tab === "master" ? "active" : ""}
                onClick={() => setTab("master")}
              >
                1. 마스터 이미지
              </button>
              <button
                className={tab === "motion" ? "active" : ""}
                onClick={() => setTab("motion")}
              >
                2. 모션 영상
              </button>
            </nav>
            {data && (
              <>
                <div className="prompt-box">
                  <label>
                    {tab === "master"
                      ? "Grok 이미지 프롬프트"
                      : "Grok 영상 프롬프트"}
                  </label>
                  <textarea
                    readOnly
                    value={
                      tab === "master"
                        ? data.master_prompt
                        : data.motion_prompts[0]?.prompt || ""
                    }
                  />
                  <button
                    onClick={() =>
                      copy(
                        tab === "master"
                          ? data.master_prompt
                          : data.motion_prompts[0]?.prompt || "",
                      )
                    }
                  >
                    프롬프트 복사
                  </button>
                </div>
                <div className="grok-steps">
                  <b>사용 순서</b>
                  <ol>
                    {data.instructions.map((x) => (
                      <li key={x}>{x}</li>
                    ))}
                  </ol>
                </div>
                <div className="import-box">
                  <label>
                    {tab === "master"
                      ? "완성 이미지 가져오기"
                      : "완성 영상 가져오기"}
                  </label>
                  <input
                    type="file"
                    accept={
                      tab === "master"
                        ? "image/jpeg,image/png,image/webp"
                        : "video/mp4,video/webm,video/quicktime"
                    }
                    onChange={(e) => setFile(e.target.files[0])}
                  />
                  <button disabled={!file} onClick={upload}>
                    프로젝트에 적용
                  </button>
                </div>
              </>
            )}
            {msg && <div className="grok-message">{msg}</div>}
          </section>
        </div>
      )}
    </>
  );
}
function Foot({ text, children }) {
  return (
    <div className="foot">
      <span>{text}</span>
      {children}
    </div>
  );
}
function App() {
  const [step, setStep] = useState("home"),
    [masterUrl, setMasterUrl] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    idx = STEPS.findIndex((x) => x[0] === step),
    next = () => setStep(STEPS[Math.min(idx + 1, STEPS.length - 1)][0]);
  const process = async (file) => {
    setBusy(true);
    setError("");
    try {
      let p = await apiJson(await fetch("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: file.name.replace(/\.[^.]+$/, "") }),
      }));
      window.__projectId = p.id;
      let form = new FormData();
      form.append("file", file);
      let up = await fetch(`/api/projects/${p.id}/assets`, {
        method: "POST",
        body: form,
      });
      await apiJson(up);
      let ma = await fetch(`/api/projects/${p.id}/masters/generate`, {
        method: "POST",
      });
      let data = await apiJson(ma);
      window.__masterUrl = data.master_url;
      setMasterUrl(data.master_url);
      setStep("master");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  const Page = {
    home: Home,
    source: Source,
    master: Master,
    plan: Plan,
    samples: Samples,
    batch: Batch,
    edit: Edit,
    export: Results,
  }[step];
  return (
    <Shell step={step} setStep={setStep}>
      <Page
        next={next}
        start={() => setStep("source")}
        openProject={() => setStep("batch")}
        process={process}
        busy={busy}
        error={error}
        masterUrl={masterUrl}
      />
    </Shell>
  );
}
createRoot(document.getElementById("root")).render(<App />);
