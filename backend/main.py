from __future__ import annotations
import base64, hashlib, hmac, io, json, os, secrets, sqlite3, uuid, zipfile, subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageDraw, ImageFont, ImageChops, ImageColor

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
DATA = (ROOT / os.getenv("PROJECTS_DIR", "data/projects")).resolve()
DATA.mkdir(parents=True, exist_ok=True)
DB = DATA.parent / "moticon.db"
FREE_ONLY = os.getenv("FREE_ONLY", "true").lower() == "true"
ALLOW_PAID = os.getenv("ALLOW_PAID_MODELS", "false").lower() == "true"
if not FREE_ONLY or ALLOW_PAID or int(os.getenv("PROJECT_PAID_BUDGET_KRW", "0")) != 0:
    raise RuntimeError("안전 정책 위반: FREE_ONLY=true, ALLOW_PAID_MODELS=false, PROJECT_PAID_BUDGET_KRW=0 이어야 합니다.")

app = FastAPI(title="MotiCon Studio API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

def db():
    con=sqlite3.connect(DB);con.row_factory=sqlite3.Row
    con.execute("CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,name TEXT,status TEXT,created_at TEXT,manifest TEXT,source_path TEXT,master_path TEXT,motion_path TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS sticker_items(id TEXT PRIMARY KEY,project_id TEXT,slot_no INTEGER,phrase TEXT,intent TEXT,emotion TEXT,facial_expression TEXT,body_pose TEXT,motion_source TEXT,motion_prompt TEXT,camera TEXT,duration REAL,speed TEXT,loop_strategy TEXT,text_style TEXT,difficulty TEXT,status TEXT,UNIQUE(project_id,slot_no))")
    con.execute("CREATE TABLE IF NOT EXISTS project_brand(project_id TEXT PRIMARY KEY,brand_name TEXT,character_name TEXT,creator_alias TEXT,human_contribution TEXT,source_rights_confirmed INTEGER DEFAULT 0,commercial_use_confirmed INTEGER DEFAULT 0,updated_at TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS provenance_events(id TEXT PRIMARY KEY,project_id TEXT,event_type TEXT,asset_name TEXT,asset_sha256 TEXT,provider TEXT,model TEXT,external_transfer INTEGER DEFAULT 0,details TEXT,created_at TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS motion_assets(project_id TEXT,slot_no INTEGER,path TEXT,provider TEXT,created_at TEXT,PRIMARY KEY(project_id,slot_no))")
    con.execute("CREATE TABLE IF NOT EXISTS static_assets(project_id TEXT,slot_no INTEGER,path TEXT,provider TEXT,model TEXT,created_at TEXT,PRIMARY KEY(project_id,slot_no))")
    return con

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()

def record_event(pid:str,event_type:str,path:Path|None=None,provider="local",model="",external=False,details:dict|None=None):
    now=datetime.now(timezone.utc).isoformat()
    with db() as con:con.execute("INSERT INTO provenance_events VALUES(?,?,?,?,?,?,?,?,?,?)",(
      uuid.uuid4().hex,pid,event_type,path.name if path else None,sha256_file(path) if path and path.exists() else None,
      provider,model,1 if external else 0,json.dumps(details or {},ensure_ascii=False),now))

def signing_key() -> bytes:
    path=DATA.parent/".moticon_provenance_key"
    if not path.exists():
        path.write_text(secrets.token_hex(32),encoding="ascii")
        try:path.chmod(0o600)
        except OSError:pass
    return path.read_text(encoding="ascii").strip().encode()

def provenance_document(pid:str):
    p=project(pid)
    with db() as con:
        brand=con.execute("SELECT * FROM project_brand WHERE project_id=?",(pid,)).fetchone()
        rows=con.execute("SELECT * FROM provenance_events WHERE project_id=? ORDER BY created_at",(pid,)).fetchall()
    events=[]
    for row in rows:
        item=dict(row);item["external_transfer"]=bool(item["external_transfer"]);item["details"]=json.loads(item["details"] or "{}")
        events.append(item)
    doc={"schema":"moticon.provenance.v1","project":{"id":pid,"name":p["name"],"created_at":p["created_at"]},
      "brand":dict(brand) if brand else None,"events":events,
      "notice":"제작 과정과 파일 무결성을 확인하는 보조 기록이며 저작권·상표권 등록 또는 법적 소유권을 자동 보장하지 않습니다."}
    payload=json.dumps(doc,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    return {"document":doc,"signature":{"algorithm":"HMAC-SHA256","value":hmac.new(signing_key(),payload,hashlib.sha256).hexdigest(),"scope":"this local MotiCon installation"}}

def project(pid: str):
    with db() as con:r=con.execute("SELECT * FROM projects WHERE id=?",(pid,)).fetchone()
    if not r: raise HTTPException(404,"프로젝트를 찾을 수 없습니다.")
    return dict(r)

def safe_dir(pid: str):
    p=(DATA/pid).resolve()
    if DATA not in p.parents: raise HTTPException(400,"잘못된 프로젝트 경로입니다.")
    p.mkdir(parents=True,exist_ok=True);return p

_REMBG_SESSION=None
def automatic_cutout(im:Image.Image)->Image.Image:
    """Local AI subject cutout. The model is downloaded once and never sends the image off-device."""
    global _REMBG_SESSION
    try:
        from rembg import new_session, remove
        if _REMBG_SESSION is None:_REMBG_SESSION=new_session(os.getenv("REMBG_MODEL","u2net"))
        original_size=im.size;work=im.convert("RGB");work.thumbnail((1024,1024),Image.Resampling.LANCZOS)
        cut=remove(work,session=_REMBG_SESSION,alpha_matting=False).convert("RGBA")
        return cut.resize(original_size,Image.Resampling.LANCZOS) if cut.size!=original_size else cut
    except Exception:
        rgba=im.convert("RGBA");rgba.putalpha(_subject_alpha(rgba));return rgba

def sticker_master(cut:Image.Image,size=(740,640))->Image.Image:
    alpha=cut.getchannel("A")
    try:
        import numpy as np
        from skimage.measure import label
        arr=np.asarray(alpha)>24;labels=label(arr,connectivity=2)
        counts=np.bincount(labels.ravel());counts[0]=0;winner=int(counts.argmax())
        if winner:alpha=Image.fromarray(np.where(labels==winner,np.asarray(alpha),0).astype("uint8"),"L");cut=cut.copy();cut.putalpha(alpha)
    except Exception:pass
    bbox=alpha.getbbox()
    if not bbox:raise HTTPException(422,"사진에서 캐릭터를 분리하지 못했습니다.")
    subject=cut.crop(bbox);subject.thumbnail((int(size[0]*.76),int(size[1]*.82)),Image.Resampling.LANCZOS)
    canvas=Image.new("RGBA",size,(0,0,0,0));x=(size[0]-subject.width)//2;y=(size[1]-subject.height)//2
    # Sticker-safe white border makes the silhouette readable without baking a background.
    a=subject.getchannel("A");outline=a.filter(ImageFilter.MaxFilter(17)).filter(ImageFilter.GaussianBlur(1.2))
    border=Image.new("RGBA",subject.size,(255,255,255,0));border.putalpha(outline);canvas.alpha_composite(border,(x,y));canvas.alpha_composite(subject,(x,y))
    return canvas

def flat_ink_variant(master:Image.Image,fill:str,ink="#383633"):
    """Remove paper/scan color, retain dark drawing strokes, and refill the character cleanly."""
    import numpy as np
    rgba=np.asarray(master.convert("RGBA")).copy();rgb=rgba[:,:,:3].astype("float32")
    gray=(rgb[:,:,0]*.299+rgb[:,:,1]*.587+rgb[:,:,2]*.114)
    # Only genuinely dark pixels become ink; mid-gray paper/body texture is discarded.
    strength=np.clip((158-gray)/92,0,1)**1.45
    fill_rgb=np.array(ImageColor.getrgb(fill),dtype="float32");ink_rgb=np.array(ImageColor.getrgb(ink),dtype="float32")
    rgba[:,:,:3]=(fill_rgb[None,None,:]*(1-strength[:,:,None])+ink_rgb[None,None,:]*strength[:,:,None]).astype("uint8")
    return Image.fromarray(rgba,"RGBA")

@app.get("/api/health")
def health(): return {"ok":True,"mode":"free_only","paid_calls_blocked":True}

@app.get("/api/providers/kakao/status")
def kakao_status():
    return {"configured":bool(os.getenv("KAKAO_REST_API_KEY")),"provider":"Kakao Daum Search","paid":False,"daily_refresh":True}

@app.get("/api/trends/emoticons")
async def emoticon_trends(refresh:bool=False):
    """Daily Daum image-search digest. Images remain remote and always link to their source page."""
    key=os.getenv("KAKAO_REST_API_KEY")
    if not key:raise HTTPException(409,"KAKAO_REST_API_KEY가 설정되지 않았습니다.")
    cache=DATA.parent/"kakao_emoticon_trends.json";today=datetime.now(timezone.utc).astimezone().date().isoformat()
    if cache.exists() and not refresh:
        try:
            saved=json.loads(cache.read_text(encoding="utf-8"))
            if saved.get("date")==today:return saved
        except Exception:pass
    queries=["신규 카카오 이모티콘","움직이는 이모티콘 출시"]
    found=[];seen=set();headers={"Authorization":f"KakaoAK {key}"}
    async with httpx.AsyncClient(timeout=25,follow_redirects=True) as client:
        for query in queries:
            response=await client.get("https://dapi.kakao.com/v2/search/image",headers=headers,params={"query":query,"sort":"recency","size":12})
            if response.status_code==401:raise HTTPException(401,"카카오 REST API 키가 올바르지 않습니다.")
            if response.status_code==429:raise HTTPException(429,"카카오 검색 API의 오늘 무료 쿼터를 모두 사용했습니다.")
            if response.status_code>=400:raise HTTPException(response.status_code,"카카오 검색 API 오류: "+response.text[:300])
            for item in response.json().get("documents",[]):
                source=item.get("doc_url") or item.get("image_url")
                thumb=item.get("thumbnail_url") or item.get("image_url")
                if not source or not thumb or source in seen:continue
                seen.add(source);found.append({
                  "image":thumb,"source_url":source,"site":item.get("display_sitename") or "웹 검색",
                  "published_at":item.get("datetime") or "","query":query,
                  "width":item.get("width"),"height":item.get("height")})
    payload={"date":today,"items":found[:12],"count":min(12,len(found)),"provider":"Kakao Daum Search API","cached":False,"notice":"검색 썸네일이며, 권리는 각 원저작자에게 있습니다."}
    cache.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    return payload

@app.get("/api/providers/status")
def providers():
    return {"free_only":True,"auto_paid_fallback":False,"paid_budget_krw":0,
      "providers":[
        {"id":"gemini","configured":bool(os.getenv("GEMINI_API_KEY")),"use":"사진 분석·문구·24개 기획","tier":"free only"},
        {"id":"cloudflare","configured":bool(os.getenv("CLOUDFLARE_ACCOUNT_ID") and os.getenv("CLOUDFLARE_API_TOKEN")),"use":"선택형 마스터 이미지 편집","tier":"Workers Free only"},
        {"id":"local","configured":True,"use":"마스터·WebP·QC","tier":"offline free"},
        {"id":"veo","configured":False,"blocked":True,"reason":"Google Gemini API 영상 생성은 유료 티어이므로 차단됨"}]}

@app.get("/api/providers/gemini/models")
async def gemini_models():
    key=os.getenv("GEMINI_API_KEY")
    if not key: raise HTTPException(409,"GEMINI_API_KEY가 설정되지 않았습니다.")
    async with httpx.AsyncClient(timeout=30) as c:r=await c.get("https://generativelanguage.googleapis.com/v1beta/models",headers={"x-goog-api-key":key})
    if r.status_code>=400: raise HTTPException(r.status_code,"Gemini 모델 목록 조회 실패: "+r.text[:400])
    models=[]
    for m in r.json().get("models",[]):
        methods=m.get("supportedGenerationMethods",[])
        if "generateContent" in methods and "veo" not in m.get("name","").lower(): models.append({"name":m.get("name"),"display_name":m.get("displayName"),"methods":methods})
    return {"models":models,"paid_models_blocked":True}

@app.post("/api/providers/gemini/key")
async def save_gemini_key(body:dict[str,Any]):
    key=str(body.get("api_key","")).strip()
    if not key or len(key)<20:raise HTTPException(400,"올바른 Google AI Studio API 키를 입력하세요.")
    async with httpx.AsyncClient(timeout=30) as c:
        r=await c.get("https://generativelanguage.googleapis.com/v1beta/models",headers={"x-goog-api-key":key})
    if r.status_code>=400:raise HTTPException(401,"API 키 확인에 실패했습니다. Google AI Studio에서 키 상태를 확인하세요.")
    env_path=ROOT/".env";lines=env_path.read_text("utf-8").splitlines() if env_path.exists() else []
    lines=[line for line in lines if not line.startswith("GEMINI_API_KEY=")]
    lines.append(f"GEMINI_API_KEY={key}")
    env_path.write_text("\n".join(lines)+"\n",encoding="utf-8")
    os.environ["GEMINI_API_KEY"]=key
    image_models=[]
    for m in r.json().get("models",[]):
        name=m.get("name","")
        if "image" in name.lower() and "generateContent" in m.get("supportedGenerationMethods",[]):image_models.append(name.replace("models/",""))
    return {"configured":True,"valid":True,"image_models":image_models,"key_stored_locally":True,"key_returned":False}

@app.post("/api/projects")
def create_project(body:dict[str,Any]|None=None):
    pid=uuid.uuid4().hex[:12];name=(body or {}).get("name") or f"MotiCon {datetime.now().strftime('%m%d-%H%M')}";now=datetime.now(timezone.utc).isoformat();safe_dir(pid)
    with db() as con:con.execute("INSERT INTO projects(id,name,status,created_at) VALUES(?,?,?,?)",(pid,name,"DRAFT",now))
    return project(pid)

@app.get("/api/projects/latest")
def latest_project():
    with db() as con:
        row=con.execute("SELECT id FROM projects WHERE master_path IS NOT NULL ORDER BY created_at DESC LIMIT 1").fetchone()
    if not row: raise HTTPException(404,"저장된 프로젝트가 없습니다.")
    return get_project(row["id"])

@app.get("/api/projects/{pid}")
def get_project(pid:str):
    p=project(pid)
    for key in ("source_path","master_path","motion_path"):
        if p.get(key):p[key.replace("_path","_url")]=f"/api/projects/{pid}/files/{Path(p[key]).name}"
    p["manifest"]=json.loads(p["manifest"]) if p.get("manifest") else None
    return p

@app.post("/api/projects/{pid}/assets")
async def upload_asset(pid:str,file:UploadFile=File(...)):
    project(pid);raw=await file.read()
    if len(raw)>15*1024*1024:raise HTTPException(413,"15MB 이하 JPG만 사용할 수 있습니다.")
    try:
        im=Image.open(io.BytesIO(raw));im.verify();im=Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:raise HTTPException(415,"정상적인 JPG 이미지를 확인할 수 없습니다.")
    if file.content_type not in ("image/jpeg","image/jpg") and (im.format or "").upper()!="JPEG":raise HTTPException(415,"MVP 입력은 JPG/JPEG만 지원합니다.")
    folder=safe_dir(pid);out=folder/"source_sanitized.jpg";clean=ImageOps.exif_transpose(im);clean.save(out,"JPEG",quality=94,optimize=True)
    cutout_path=folder/"source_cutout.png";automatic_cutout(clean).save(cutout_path,"PNG",optimize=True)
    report={"width":im.width,"height":im.height,"long_edge":max(im.size),"recommended_resolution":max(im.size)>=1500,"size_bytes":len(raw),"exif_removed":True}
    with db() as con:con.execute("UPDATE projects SET source_path=?,status=? WHERE id=?",(str(out),"ASSETS_READY",pid))
    record_event(pid,"SOURCE_UPLOADED",out,details={"exif_removed":True,"original_filename_stored":False,"mime":"image/jpeg"})
    record_event(pid,"BACKGROUND_REMOVED",cutout_path,provider="local_rembg_u2net",details={"external_transfer":False,"transparent_png":True})
    return {"asset_url":f"/api/projects/{pid}/files/{out.name}","cutout_url":f"/api/projects/{pid}/files/{cutout_path.name}","quality":report,"sha256":sha256_file(out)}

async def gemini_manifest(image_path:Path):
    key=os.getenv("GEMINI_API_KEY")
    if not key:return None
    data=base64.b64encode(image_path.read_bytes()).decode()
    schema={"type":"object","properties":{"subject_type":{"type":"string"},"core_features":{"type":"array","items":{"type":"string"}},"palette":{"type":"array","items":{"type":"string"}},"personality":{"type":"array","items":{"type":"string"}},"tone":{"type":"string"},"locked_traits":{"type":"array","items":{"type":"string"}},"style_prompt":{"type":"string"}},"required":["subject_type","core_features","palette","personality","tone","locked_traits","style_prompt"]}
    body={"contents":[{"parts":[{"text":"이 사진을 상업용 메신저 이모티콘 마스터 캐릭터로 만들기 위한 Identity Manifest를 한국어 JSON으로 작성해. 관찰 가능한 특징만 사용하고 민감한 속성은 추론하지 마."},{"inline_data":{"mime_type":"image/jpeg","data":data}}]}],"generationConfig":{"responseMimeType":"application/json","responseJsonSchema":schema}}
    model=os.getenv("GEMINI_MODEL","gemini-3.5-flash-lite")
    async with httpx.AsyncClient(timeout=60) as c:r=await c.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",headers={"x-goog-api-key":key},json=body)
    if r.status_code==429:raise HTTPException(429,"Gemini 무료 할당량이 소진되어 작업을 중지했습니다. 결제 호출은 하지 않았습니다.")
    if r.status_code>=400:raise HTTPException(r.status_code,"Gemini 요청 실패: "+r.text[:500])
    try:return json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
    except (KeyError,IndexError,json.JSONDecodeError) as e:raise HTTPException(502,"Gemini 응답을 JSON으로 해석하지 못했습니다.") from e

@app.post("/api/projects/{pid}/analyze")
async def analyze(pid:str):
    p=project(pid)
    if not p.get("source_path"):raise HTTPException(409,"먼저 JPG 사진을 업로드하세요.")
    warning=None
    try:manifest=await gemini_manifest(Path(p["source_path"]))
    except HTTPException as e:
        if e.status_code==429:raise
        manifest=None;warning=e.detail
    if manifest is None:manifest={"subject_type":"사진 속 대상","core_features":["원본 윤곽 유지","표정 가독성 우선"],"palette":["원본 대표색"],"personality":["다정함","유쾌함","친근함"],"tone":"짧고 자연스러운 말투","locked_traits":["얼굴","헤어/털","의상","대표색"],"style_prompt":"굵고 깨끗한 외곽선의 고품질 2D 이모티콘"}
    with db() as con:con.execute("UPDATE projects SET manifest=?,status=? WHERE id=?",(json.dumps(manifest,ensure_ascii=False),"MASTER_REVIEW",pid))
    used_gemini=bool(os.getenv("GEMINI_API_KEY")) and not warning
    record_event(pid,"IDENTITY_ANALYZED",provider="gemini_free" if used_gemini else "local_fallback",model=os.getenv("GEMINI_MODEL","") if used_gemini else "",external=used_gemini,details={"original_image_transferred":used_gemini,"sensitive_attribute_inference_forbidden":True})
    return {"manifest":manifest,"provider":"gemini_free" if os.getenv("GEMINI_API_KEY") and not warning else "local_fallback","paid":False,"warning":warning}

def rounded_mask(size):
    mask=Image.new("L",size,0);ImageDraw.Draw(mask).rounded_rectangle((0,0,*size),radius=max(size)//7,fill=255);return mask

def ui_font(size=24):
    for path in (Path("C:/Windows/Fonts/malgun.ttf"),Path("C:/Windows/Fonts/arial.ttf")):
        if path.exists(): return ImageFont.truetype(str(path),size)
    return ImageFont.load_default()

@app.post("/api/projects/{pid}/masters/generate")
def generate_master(pid:str):
    p=project(pid)
    if not p.get("source_path"):raise HTTPException(409,"먼저 사진을 업로드하세요.")
    cutout=safe_dir(pid)/"source_cutout.png"
    src=Image.open(cutout if cutout.exists() else p["source_path"]).convert("RGBA")
    canvas=sticker_master(src)
    folder=safe_dir(pid);variants={
      "original":canvas,
      "white":flat_ink_variant(canvas,"#fffdf8"),
      "peach":flat_ink_variant(canvas,"#ffd9c7","#563e38"),
      "mint":flat_ink_variant(canvas,"#d8f1e4","#334840"),
      "lilac":flat_ink_variant(canvas,"#eadcf4","#473d51"),
      "butter":flat_ink_variant(canvas,"#ffe9a8","#51442f")}
    variant_urls={}
    for key,image in variants.items():
        path=folder/f"master_{key}.png";image.save(path,"PNG",optimize=True);variant_urls[key]=f"/api/projects/{pid}/files/{path.name}"
    out=folder/"master_original.png"
    with db() as con:con.execute("UPDATE projects SET master_path=?,status=? WHERE id=?",(str(out),"MASTER_APPROVED",pid))
    record_event(pid,"MASTER_GENERATED",out,provider="local_cutout_and_sticker_preprocess",details={"method":"AI cutout, subject centering, transparent background, sticker outline"})
    return {"master_url":variant_urls["original"],"variants":variant_urls,"provider":"local_cutout_and_sticker_preprocess","paid":False,"transparent":True,"rig_ready":True,"note":"원본 색감과 깨끗한 단색 캐릭터 5종을 만들었습니다. 흰색은 미리보기 배경이고 실제 PNG 배경은 투명합니다."}

@app.post("/api/projects/{pid}/masters/select")
def select_master(pid:str,body:dict[str,Any]):
    key=str(body.get("variant","original"));allowed={"original","white","peach","mint","lilac","butter"}
    if key not in allowed:raise HTTPException(400,"지원 색상은 original, white, peach, mint, lilac, butter입니다.")
    path=safe_dir(pid)/f"master_{key}.png"
    if not path.exists():raise HTTPException(409,"먼저 마스터 시안을 생성하세요.")
    with db() as con:con.execute("UPDATE projects SET master_path=?,status=? WHERE id=?",(str(path),"MASTER_APPROVED",pid))
    record_event(pid,"MASTER_VARIANT_SELECTED",path,details={"variant":key})
    return {"master_url":f"/api/projects/{pid}/files/{path.name}","variant":key,"locked":True}

@app.post("/api/projects/{pid}/masters/generate-cloudflare")
async def generate_master_cloudflare(pid:str):
    p=project(pid);account=os.getenv("CLOUDFLARE_ACCOUNT_ID");token=os.getenv("CLOUDFLARE_API_TOKEN")
    if not account or not token:raise HTTPException(409,"Cloudflare Account ID와 API Token이 필요합니다.")
    if os.getenv("CLOUDFLARE_FREE_PLAN_CONFIRMED","false").lower()!="true":raise HTTPException(403,"결제 방지를 위해 Cloudflare Free 플랜 확인이 필요합니다.")
    if not p.get("source_path"):raise HTTPException(409,"먼저 사진을 업로드하세요.")
    src=Image.open(p["source_path"]).convert("RGB");src.thumbnail((512,512));buf=io.BytesIO();src.save(buf,"JPEG",quality=90)
    manifest=json.loads(p["manifest"]) if p.get("manifest") else {}
    prompt=("Transform the subject in input image 0 into one premium Korean messenger sticker master character. "
      "Preserve identity, face, hair or fur, clothing and representative colors. Full body, centered, clear thick dark outline, "
      "professional 2D digital illustration, expressive friendly neutral pose, clean plain light background, no text, no watermark. Character manifest: "+json.dumps(manifest,ensure_ascii=False))
    model=os.getenv("CLOUDFLARE_IMAGE_MODEL","@cf/black-forest-labs/flux-2-klein-4b")
    if model!="@cf/black-forest-labs/flux-2-klein-4b":raise HTTPException(403,"무료 MVP에서 허용되지 않은 Cloudflare 모델입니다.")
    url=f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"
    files={"input_image_0":("source.jpg",buf.getvalue(),"image/jpeg")};data={"prompt":prompt,"width":"1024","height":"1024","guidance":"3.5"}
    async with httpx.AsyncClient(timeout=120) as c:r=await c.post(url,headers={"Authorization":f"Bearer {token}"},files=files,data=data)
    if r.status_code in (402,403,429):raise HTTPException(r.status_code,"Cloudflare 무료 할당량 또는 Free 플랜에서 실행할 수 없어 중지했습니다. 유료 호출은 하지 않았습니다.")
    if r.status_code>=400:raise HTTPException(r.status_code,"Cloudflare 이미지 생성 실패: "+r.text[:400])
    try:
        payload=r.json();encoded=payload["result"]["image"];raw=base64.b64decode(encoded);generated=Image.open(io.BytesIO(raw)).convert("RGBA")
    except Exception as e:raise HTTPException(502,"Cloudflare 이미지 응답을 해석하지 못했습니다.") from e
    generated=ImageOps.fit(generated,(740,640),method=Image.Resampling.LANCZOS);out=safe_dir(pid)/"master_cloudflare_v1.png";generated.save(out)
    with db() as con:con.execute("UPDATE projects SET master_path=?,status=? WHERE id=?",(str(out),"MASTER_REVIEW",pid))
    return {"master_url":f"/api/projects/{pid}/files/{out.name}","provider":"cloudflare_workers_ai_free","paid":False,"cost_krw":0,"model":model}

FALLBACK_PHRASES=["안녕!","반가워","잘 가","고마워","미안해","사랑해","좋아!","최고야","축하해","화이팅","대박","헉!","정말?","왜?","신난다","너무 웃겨","감동이야","슬퍼","화났어","삐졌어","기다려","지금 가!","배고파","잘 자"]
FALLBACK_MOTIONS=["화면 밖에서 들어와 손 흔들기","두 팔 벌리고 활짝 웃기","뒤돌아 걸으며 크게 인사하기","두 손 모아 인사하고 하트 띄우기","어깨를 움츠리고 고개 숙이기","볼 하트 후 큰 하트 안기","엄지척하며 앞으로 튀어나오기","두 엄지와 반짝이 강조","점프하며 꽃가루 터뜨리기","주먹을 쥐고 힘차게 펌핑하기","눈이 커지고 입을 벌리며 확대","뒤로 놀라며 작아지기","고개를 갸웃하고 눈썹 올리기","양손을 펼치고 좌우 살피기","좋아서 방방 뛰기","배를 잡고 크게 웃기","눈물이 맺히고 가슴에 손 얹기","주저앉아 눈물 닦기","볼을 부풀리고 발 구르기","팔짱 끼고 등을 돌리기","손바닥을 내밀고 숨 가쁘게 달려오기","멀리서 카메라 앞으로 달려오기","배를 만지고 힘없이 흔들리기","하품 후 이불 속으로 작아지기"]
FALLBACK_INTENTS=["인사","환영","작별","감사","사과","애정","긍정","칭찬","축하","응원","놀람","당황","의문","질문","기쁨","웃음","감동","슬픔","화남","토라짐","요청","이동","일상","취침"]

def fallback_plan():
    return [{"slot_no":i+1,"phrase":p,"intent":FALLBACK_INTENTS[i],"emotion":FALLBACK_INTENTS[i],"facial_expression":f"{FALLBACK_INTENTS[i]} 감정이 명확한 눈과 입","body_pose":m,"motion_source":"preset","motion_prompt":m+". 시작, 강조, 자연스러운 복귀 순서.","camera":"고정" if i not in (10,21) else "원근 변화","duration":2.0 if i in (0,14,21) else 1.6,"speed":"보통","loop_strategy":"첫 프레임 복귀","text_style":"굵고 읽기 쉬운 한글, 캐릭터와 분리","difficulty":"높음" if i in (0,14,21) else "중간"} for i,(p,m) in enumerate(zip(FALLBACK_PHRASES,FALLBACK_MOTIONS))]

async def gemini_plan(manifest:dict):
    key=os.getenv("GEMINI_API_KEY")
    if not key:return None
    schema={"type":"array","items":{"type":"object","properties":{"slot_no":{"type":"integer"},"phrase":{"type":"string"},"intent":{"type":"string"},"emotion":{"type":"string"},"facial_expression":{"type":"string"},"body_pose":{"type":"string"},"motion_source":{"type":"string"},"motion_prompt":{"type":"string"},"camera":{"type":"string"},"duration":{"type":"number"},"speed":{"type":"string"},"loop_strategy":{"type":"string"},"text_style":{"type":"string"},"difficulty":{"type":"string"}},"required":["slot_no","phrase","intent","emotion","facial_expression","body_pose","motion_source","motion_prompt","camera","duration","speed","loop_strategy","text_style","difficulty"]}}
    prompt="정확히 24개의 한국어 메신저 이모티콘 세트를 기획해. 의사소통 목적이 중복되지 않게 하고 인사·긍정·감사·사과·놀람·웃음·기쁨·슬픔·화남·일상을 균형 있게 포함해. 문구는 짧게, 모션은 시작-중간-끝의 표정과 전신 자세가 드러나게 작성해. 문구는 이미지에 굽지 않고 별도 레이어로 처리한다. 캐릭터 명세: "+json.dumps(manifest,ensure_ascii=False)
    body={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"responseMimeType":"application/json","responseJsonSchema":schema}}
    model=os.getenv("GEMINI_MODEL","gemini-3.5-flash-lite")
    async with httpx.AsyncClient(timeout=90) as c:r=await c.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",headers={"x-goog-api-key":key},json=body)
    if r.status_code==429:raise HTTPException(429,"Gemini 무료 할당량이 소진되어 24개 기획을 중지했습니다. 결제 호출은 하지 않았습니다.")
    if r.status_code>=400:raise HTTPException(r.status_code,"Gemini 24개 기획 실패: "+r.text[:500])
    try:items=json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
    except Exception as e:raise HTTPException(502,"Gemini 24개 기획 JSON을 해석하지 못했습니다.") from e
    if len(items)!=24 or sorted(x.get("slot_no") for x in items)!=list(range(1,25)):raise HTTPException(502,"Gemini가 정확한 1~24 구성표를 반환하지 않았습니다.")
    return items

def save_plan(pid:str,items:list[dict]):
    cols=["id","project_id","slot_no","phrase","intent","emotion","facial_expression","body_pose","motion_source","motion_prompt","camera","duration","speed","loop_strategy","text_style","difficulty","status"]
    rows=[]
    for x in items: rows.append([uuid.uuid4().hex,pid,x["slot_no"],x["phrase"],x["intent"],x["emotion"],x["facial_expression"],x["body_pose"],x["motion_source"],x["motion_prompt"],x["camera"],x["duration"],x["speed"],x["loop_strategy"],x["text_style"],x["difficulty"],"PLANNED"])
    with db() as con:
        con.execute("DELETE FROM sticker_items WHERE project_id=?",(pid,))
        con.executemany(f"INSERT INTO sticker_items({','.join(cols)}) VALUES({','.join('?' for _ in cols)})",rows)
        con.execute("UPDATE projects SET status=? WHERE id=?",("PLAN_REVIEW",pid))

@app.post("/api/projects/{pid}/plans/generate")
async def generate_plan(pid:str):
    p=project(pid);manifest=json.loads(p["manifest"]) if p.get("manifest") else {"style_prompt":"고품질 2D 이모티콘"}
    warning=None
    try:items=await gemini_plan(manifest)
    except HTTPException as e:
        if e.status_code==429:raise
        items=None;warning=e.detail
    provider="gemini_free"
    if items is None:items=fallback_plan();provider="local_fallback"
    save_plan(pid,items)
    return {"items":items,"count":len(items),"provider":provider,"paid":False,"warning":warning}

@app.get("/api/projects/{pid}/plans")
def get_plan(pid:str):
    project(pid)
    with db() as con:items=[dict(x) for x in con.execute("SELECT * FROM sticker_items WHERE project_id=? ORDER BY slot_no",(pid,)).fetchall()]
    return {"items":items,"count":len(items)}

def static_set_prompt(slot:int,phrase:str,motion:str)->str:
    return ("Create one polished Korean messenger emoticon sticker using the attached master image as a strict character reference. "
      "Preserve exactly the same two characters, facial identity, ear shapes, black hand-drawn outline, white body fill, proportions, strawberry prop, and overall brand style. "
      f"Sticker {slot:02d}/24. Meaning: {phrase}. Pose and expression: {motion}. "
      "Change the facial expression, arms, legs, and body pose so the meaning is immediately readable. Keep exactly two characters and anatomically correct limbs. "
      "No duplicate arms, no extra characters, no photorealism, no watermark, no speech bubble, and do not draw any text. "
      "Centered full-body composition on a clean plain white background, production-quality static sticker, square canvas.")

async def gemini_static_image(master:Path,prompt:str)->tuple[bytes,str]:
    key=os.getenv("GEMINI_API_KEY")
    if not key:raise HTTPException(409,"GEMINI_API_KEY가 없습니다. 키를 연결한 뒤 다시 실행하세요.")
    model=os.getenv("GEMINI_IMAGE_MODEL","gemini-3.1-flash-image-preview")
    if "image" not in model.lower():raise HTTPException(409,"GEMINI_IMAGE_MODEL은 이미지 출력 모델이어야 합니다.")
    encoded=base64.b64encode(master.read_bytes()).decode()
    body={"contents":[{"role":"user","parts":[{"inlineData":{"mimeType":"image/png","data":encoded}},{"text":prompt}]}],"generationConfig":{"responseModalities":["TEXT","IMAGE"],"imageConfig":{"aspectRatio":"1:1"}}}
    async with httpx.AsyncClient(timeout=180) as c:
        r=await c.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",headers={"x-goog-api-key":key},json=body)
    if r.status_code in (402,429):raise HTTPException(409,"무료 할당량을 사용할 수 없어 생성하지 않았습니다. 결제나 자동 충전은 실행하지 않습니다.")
    if r.status_code>=400:raise HTTPException(r.status_code,"Gemini 이미지 생성 실패: "+r.text[:500])
    for candidate in r.json().get("candidates",[]):
        for part in candidate.get("content",{}).get("parts",[]):
            inline=part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):return base64.b64decode(inline["data"]),model
    raise HTTPException(502,"Gemini가 이미지 데이터를 반환하지 않았습니다.")

@app.get("/api/projects/{pid}/static-set")
def get_static_set(pid:str):
    project(pid)
    with db() as con:rows=con.execute("SELECT * FROM static_assets WHERE project_id=? ORDER BY slot_no",(pid,)).fetchall()
    return {"items":[{"slot_no":x["slot_no"],"provider":x["provider"],"model":x["model"],"url":f"/api/projects/{pid}/files/{Path(x['path']).name}"} for x in rows],"completed":len(rows),"total":24,"paid_calls_allowed":False}

@app.post("/api/projects/{pid}/static-set/generate-one")
async def generate_static_item(pid:str,body:dict[str,Any]):
    p=project(pid);slot=int(body.get("slot_no",0))
    if slot not in range(1,25):raise HTTPException(400,"slot_no는 1~24여야 합니다.")
    with db() as con:planned=con.execute("SELECT phrase,motion_prompt FROM sticker_items WHERE project_id=? AND slot_no=?",(pid,slot)).fetchone()
    phrase=planned["phrase"] if planned else FALLBACK_PHRASES[slot-1];motion=planned["motion_prompt"] if planned else FALLBACK_MOTIONS[slot-1]
    raw,model=await gemini_static_image(Path(p["master_path"]),static_set_prompt(slot,phrase,motion))
    try:im=Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:raise HTTPException(502,"Gemini 이미지 결과를 읽을 수 없습니다.")
    im=ImageOps.fit(im,(740,640),method=Image.Resampling.LANCZOS);out=safe_dir(pid)/f"static_{slot:02d}_gemini.png";im.save(out,optimize=True)
    now=datetime.now(timezone.utc).isoformat()
    with db() as con:con.execute("INSERT OR REPLACE INTO static_assets VALUES(?,?,?,?,?,?)",(pid,slot,str(out),"gemini_ai_studio",model,now))
    record_event(pid,"STATIC_STICKER_GENERATED",out,provider="gemini_ai_studio",model=model,external=True,details={"slot_no":slot,"phrase":phrase,"paid_fallback":False})
    return {"slot_no":slot,"phrase":phrase,"url":f"/api/projects/{pid}/files/{out.name}","completed":True,"paid_fallback":False}

@app.post("/api/projects/{pid}/static-set/export")
def export_static_set(pid:str):
    p=project(pid)
    with db() as con:rows=con.execute("SELECT slot_no,path FROM static_assets WHERE project_id=? ORDER BY slot_no",(pid,)).fetchall()
    if not rows:raise HTTPException(409,"먼저 정적 이모티콘을 생성하세요.")
    out=safe_dir(pid)/"moticon_static_set.zip"
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
        for x in rows:z.write(x["path"],f"stickers/{x['slot_no']:02d}.png")
        z.writestr("README.txt",f"MotiCon static set\nProject: {p['name']}\nCompleted: {len(rows)}/24\nExternal paid fallback: disabled\n")
    return {"download_url":f"/api/projects/{pid}/files/{out.name}","completed":len(rows),"total":24}

@app.patch("/api/sticker-items/{item_id}")
def update_plan_item(item_id:str,body:dict[str,Any]):
    allowed={"phrase","intent","emotion","facial_expression","body_pose","motion_source","motion_prompt","camera","duration","speed","loop_strategy","text_style","difficulty"};changes={k:v for k,v in body.items() if k in allowed}
    if not changes:raise HTTPException(400,"수정 가능한 필드가 없습니다.")
    with db() as con:
        cur=con.execute("UPDATE sticker_items SET "+",".join(f"{k}=?" for k in changes)+" WHERE id=?",(*changes.values(),item_id))
        if not cur.rowcount:raise HTTPException(404,"구성 항목을 찾을 수 없습니다.")
        row=con.execute("SELECT * FROM sticker_items WHERE id=?",(item_id,)).fetchone()
    return dict(row)

@app.get("/api/projects/{pid}/handoffs/grok")
def grok_handoff(pid:str):
    p=project(pid);manifest=json.loads(p["manifest"]) if p.get("manifest") else {}
    with db() as con:items=[dict(x) for x in con.execute("SELECT * FROM sticker_items WHERE project_id=? ORDER BY slot_no",(pid,)).fetchall()]
    identity=json.dumps(manifest,ensure_ascii=False)
    master_prompt=("첨부한 사진 속 대상의 정체성을 유지한 고품질 한국 메신저 이모티콘 마스터 캐릭터를 만들어줘. "
      "얼굴, 헤어 또는 털, 의상, 체형, 대표 색은 유지하고 전문적인 2D 디지털 일러스트로 변환해. "
      "굵고 깨끗한 외곽선, 명확한 실루엣, 정면 전신, 자연스러운 기본 표정, 중앙 배치, 글자와 워터마크 없음. "
      "캐릭터 명세: "+identity)
    motion_prompts=[]
    for x in items[:3] if items else fallback_plan()[:3]:
        motion_prompts.append({"slot_no":x["slot_no"],"phrase":x["phrase"],"prompt":
          "첨부한 마스터 캐릭터의 얼굴, 색, 의상, 체형을 절대 바꾸지 말고 짧은 루프 영상으로 만들어줘. "
          +x["motion_prompt"]+" 카메라는 "+x["camera"]+". 시작과 마지막 자세가 자연스럽게 이어지고 배경은 단순하게. 영상 안에 글자는 넣지 마."})
    return {"mode":"manual_free_web","api_called":False,"cost_krw":0,"master_prompt":master_prompt,"motion_prompts":motion_prompts,"instructions":["Grok Imagine 웹에서 이미지 모드 선택","원본 JPG와 마스터 프롬프트 사용","완성 이미지를 다운로드해 이 앱에 가져오기","마스터 이미지를 첨부하고 영상 모드에서 동작 프롬프트 사용","완성 영상을 다운로드해 이 앱에 가져오기"]}

@app.post("/api/projects/{pid}/handoffs/grok/import")
async def import_grok_result(pid:str,kind:str,slot_no:int=0,file:UploadFile=File(...)):
    project(pid);raw=await file.read();limit=100*1024*1024
    if len(raw)>limit:raise HTTPException(413,"가져오기 파일은 100MB 이하여야 합니다.")
    folder=safe_dir(pid);mime=(file.content_type or "").lower()
    if kind=="master":
        if mime not in ("image/jpeg","image/png","image/webp"):raise HTTPException(415,"마스터는 JPG, PNG, WebP만 지원합니다.")
        try:im=Image.open(io.BytesIO(raw)).convert("RGBA")
        except Exception:raise HTTPException(415,"이미지 파일을 읽을 수 없습니다.")
        im=ImageOps.fit(im,(740,640),method=Image.Resampling.LANCZOS);out=folder/"master_grok_manual.png";im.save(out)
        with db() as con:con.execute("UPDATE projects SET master_path=?,status=? WHERE id=?",(str(out),"MASTER_REVIEW",pid))
        return {"kind":"master","url":f"/api/projects/{pid}/files/{out.name}","provider":"grok_web_manual","api_called":False,"paid":False}
    if kind=="motion":
        if slot_no==0:
            with db() as con:used={x[0] for x in con.execute("SELECT slot_no FROM motion_assets WHERE project_id=?",(pid,)).fetchall()}
            slot_no=next((n for n in range(1,25) if n not in used),1)
        if slot_no not in range(1,25):raise HTTPException(400,"slot_no는 1~24여야 합니다.")
        if mime not in ("video/mp4","video/webm","video/quicktime"):raise HTTPException(415,"영상은 MP4, WebM, MOV만 지원합니다.")
        ext={"video/mp4":".mp4","video/webm":".webm","video/quicktime":".mov"}[mime];source=folder/(f"grok_motion_{slot_no:02d}_source"+ext);source.write_bytes(raw);out=folder/f"motion_{slot_no:02d}_grok.webp"
        cmd=["ffmpeg","-y","-i",str(source),"-t","3","-vf","fps=10,scale=740:640:force_original_aspect_ratio=decrease,pad=740:640:(ow-iw)/2:(oh-ih)/2:color=white","-an","-loop","0","-c:v","libwebp_anim","-quality","62","-compression_level","4",str(out)]
        run=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
        if run.returncode!=0:raise HTTPException(500,"FFmpeg 영상 변환 실패: "+run.stderr[-500:])
        with db() as con:
            con.execute("INSERT OR REPLACE INTO motion_assets VALUES(?,?,?,?,?)",(pid,slot_no,str(out),"grok_web_manual",datetime.now(timezone.utc).isoformat()))
            con.execute("UPDATE projects SET motion_path=?,status=? WHERE id=?",(str(out),"SAMPLE_REVIEW",pid))
        record_event(pid,"ARTICULATED_MOTION_IMPORTED",out,provider="grok_web_manual",external=True,details={"slot_no":slot_no,"source":"user-operated image-to-video generation"})
        return {"kind":"motion","slot_no":slot_no,"url":f"/api/projects/{pid}/files/{out.name}","provider":"grok_web_manual","api_called":False,"paid":False,"articulated_motion":True}
    raise HTTPException(400,"kind는 master 또는 motion이어야 합니다.")

@app.post("/api/projects/{pid}/handoffs/{provider}/motion-import")
async def import_provider_motion(pid:str,provider:str,slot_no:int,file:UploadFile=File(...)):
    providers={"kling":"Kling","runway":"Runway","pika":"Pika"}
    if provider not in providers:raise HTTPException(400,"지원하지 않는 영상 서비스입니다.")
    result=await import_grok_result(pid,"motion",slot_no,file)
    provider_id=f"{provider}_web_manual"
    with db() as con:
        con.execute("UPDATE motion_assets SET provider=? WHERE project_id=? AND slot_no=?",(provider_id,pid,slot_no))
    result["provider"]=provider_id
    record_event(pid,"MOTION_PROVIDER_TAGGED",safe_dir(pid)/f"motion_{slot_no:02d}_grok.webp",provider=provider_id,external=True,details={"slot_no":slot_no,"service":providers[provider],"api_cost_krw":0})
    return result

@app.post("/api/projects/{pid}/motions/generate")
async def generate_motion(pid:str,body:dict[str,Any]|None=None):
    result=await ai_motion_samples(pid)
    return {"motion_url":result["items"][0]["motion_url"],"samples":result["items"],"provider":"gemini_keyframe_sheet","paid":False,"cost_krw":0,"articulated_motion":True}

def _subject_alpha(im:Image.Image)->Image.Image:
    """Use real alpha when present, otherwise remove a corner-connected flat background."""
    alpha=im.getchannel("A")
    if alpha.getextrema()[0]<16:return alpha
    rgb=im.convert("RGB");corners=[rgb.getpixel((2,2)),rgb.getpixel((im.width-3,2)),rgb.getpixel((2,im.height-3)),rgb.getpixel((im.width-3,im.height-3))]
    bg=tuple(sum(x[i] for x in corners)//4 for i in range(3));px=rgb.load();mask=Image.new("L",im.size,0);mp=mask.load()
    for y in range(im.height):
        for x in range(im.width):
            c=px[x,y];dist=sum(abs(c[i]-bg[i]) for i in range(3));mp[x,y]=0 if dist<42 else min(255,(dist-24)*7)
    return mask.filter(ImageFilter.GaussianBlur(1.2))

def _rig_masks(im:Image.Image):
    alpha=_subject_alpha(im);bbox=alpha.getbbox()
    if not bbox:raise HTTPException(422,"캐릭터 영역을 찾지 못했습니다. 배경이 단순하거나 투명한 PNG 마스터를 사용하세요.")
    l,t,r,b=bbox;w=r-l;h=b-t
    specs={
      "head":(l+.16*w,t,l+.84*w,t+.46*h),"left_arm":(l,t+.28*h,l+.35*w,t+.70*h),"right_arm":(l+.65*w,t+.28*h,r,t+.70*h),
      "left_leg":(l+.12*w,t+.68*h,l+.48*w,b),"right_leg":(l+.52*w,t+.68*h,l+.88*w,b)}
    masks={}
    for name,box in specs.items():
        m=Image.new("L",im.size,0);ImageDraw.Draw(m).ellipse(tuple(map(int,box)),fill=255);m=ImageChops.multiply(m,alpha);masks[name]=m.filter(ImageFilter.GaussianBlur(1.0))
    occupied=Image.new("L",im.size,0)
    for m in masks.values():occupied=ImageChops.lighter(occupied,m)
    masks["body"]=ImageChops.subtract(alpha,occupied)
    return bbox,masks

def _layer(im:Image.Image,mask:Image.Image):
    out=Image.new("RGBA",im.size,(0,0,0,0));out.paste(im,(0,0),mask);return out

def _transform_part(layer:Image.Image,angle=0,dx=0,dy=0,scale=1.0):
    box=layer.getbbox()
    if not box:return layer
    crop=layer.crop(box)
    if scale!=1:crop=crop.resize((max(1,int(crop.width*scale)),max(1,int(crop.height*scale))),Image.Resampling.LANCZOS)
    if angle:crop=crop.rotate(angle,Image.Resampling.BICUBIC,expand=True)
    out=Image.new("RGBA",layer.size,(0,0,0,0));x=int((box[0]+box[2])/2-crop.width/2+dx);y=int((box[1]+box[3])/2-crop.height/2+dy);out.alpha_composite(crop,(x,y));return out

def _face_expression(frame:Image.Image,bbox,phase:float,kind:str):
    l,t,r,b=bbox;w=r-l;h=b-t;d=ImageDraw.Draw(frame)
    if kind in ("wave","jump"):
        eye_y=int(t+.22*h);eye_w=max(3,int(.045*w));blink=abs(__import__('math').sin(phase*__import__('math').tau))>.93
        for ex in (l+.39*w,l+.61*w):
            if blink:d.line((int(ex-eye_w),eye_y,int(ex+eye_w),eye_y),fill=(55,38,25,230),width=max(2,int(w*.012)))
        if kind=="jump":
            cy=int(t+.34*h);d.ellipse((int(l+.46*w),cy,int(l+.54*w),cy+max(5,int(.07*h))),fill=(90,35,30,210))

def generate_rig_motion(pid:str,slot_no:int,action:str,phrase:str=""):
    p=project(pid);path=p.get("master_path") or p.get("source_path")
    if not path:raise HTTPException(409,"먼저 마스터 이미지를 생성하세요.")
    original=ImageOps.fit(Image.open(path).convert("RGBA"),(740,640),method=Image.Resampling.LANCZOS)
    bbox,masks=_rig_masks(original);parts={k:_layer(original,m) for k,m in masks.items()};frames=[];count=24
    for n in range(count):
        phase=n/(count-1);s=__import__('math').sin(phase*__import__('math').tau);lift=max(0,__import__('math').sin(phase*__import__('math').pi))
        frame=Image.new("RGBA",original.size,(0,0,0,0))
        if action=="run":cfg={"body":(0,0,-8*lift,1),"head":(-2*s,0,-10*lift,1),"left_arm":(18*s,0,-5*lift,1),"right_arm":(-18*s,0,-5*lift,1),"left_leg":(-16*s,0,0,1),"right_leg":(16*s,0,0,1)}
        elif action=="jump":cfg={"body":(0,0,-32*lift,1+.03*lift),"head":(0,0,-38*lift,1),"left_arm":(-38*lift,0,-28*lift,1),"right_arm":(38*lift,0,-28*lift,1),"left_leg":(10*lift,0,-12*lift,1),"right_leg":(-10*lift,0,-12*lift,1)}
        else:cfg={"body":(0,0,-3*lift,1),"head":(2*s,0,-4*lift,1),"left_arm":(-8*s,0,0,1),"right_arm":(-18-34*s,0,-10*lift,1),"left_leg":(0,0,0,1),"right_leg":(0,0,0,1)}
        for name in ("body","left_leg","right_leg","left_arm","right_arm","head"):
            angle,dx,dy,scale=cfg[name];frame.alpha_composite(_transform_part(parts[name],angle,dx,dy,scale))
        _face_expression(frame,bbox,phase,action);frames.append(frame)
    frames.append(frames[0].copy());out=safe_dir(pid)/f"motion_{slot_no:02d}_rig.webp"
    frames[0].save(out,save_all=True,append_images=frames[1:],duration=75,loop=0,lossless=False,quality=78,method=4)
    with db() as con:
        con.execute("INSERT OR REPLACE INTO motion_assets VALUES(?,?,?,?,?)",(pid,slot_no,str(out),"local_python_rig_v1",datetime.now(timezone.utc).isoformat()))
        con.execute("UPDATE projects SET motion_path=?,status=? WHERE id=?",(str(out),"SAMPLE_REVIEW",pid))
    record_event(pid,"RIGGED_MOTION_GENERATED",out,provider="local_python_rig_v1",details={"slot_no":slot_no,"action":action,"independent_parts":["head","body","left_arm","right_arm","left_leg","right_leg"],"frames":25})
    return {"slot_no":slot_no,"motion_url":f"/api/projects/{pid}/files/{out.name}","provider":"local_python_rig_v1","paid":False,"cost_krw":0,"articulated_motion":True,"parts":6}

@app.post("/api/projects/{pid}/motions/rig-generate")
def rig_generate(pid:str,body:dict[str,Any]|None=None):
    raise HTTPException(410,"고정 비율 리깅은 캐릭터 구조를 훼손하여 중단했습니다. AI 키프레임 생성을 사용하세요.")

@app.post("/api/projects/{pid}/motions/rig-samples")
async def rig_samples(pid:str):
    # Backward-compatible URL used by the UI. It now runs real AI keyframe generation.
    return await ai_motion_samples(pid)

def motion_sheet_prompt(phrase:str,action:str)->str:
    return (
      "The attached image is a strict master reference for a Korean messenger sticker. It contains a specific character composition that may include two joined animal characters. "
      "Do not reinterpret it as a human body. First identify each character, its actual face, ears, paws/arms, legs, tail, prop, and the boundary between the characters. "
      "Create a horizontal five-frame animation keyframe sheet, five equal square panels from left to right, on pure white. "
      "Every panel must contain exactly the same characters and props as the master, with identical line style, face identity, proportions, colors, and character count. "
      f"The action is '{action}' and the intended message is '{phrase}'. Show a natural sequence: anticipation, start, strongest pose, recovery, loop-ready return. "
      "Only move limbs that truly exist in the reference. Never invent a human torso, neck, shoulders, trousers, extra arms, duplicate faces, or extra characters. "
      "No text, captions, borders, panel numbers, speech bubbles, shadows, gray texture, watermark, or cropped body parts. Clean professional 2D sticker artwork."
    )

async def generate_ai_motion_sheet(pid:str,slot_no:int,action:str,phrase:str)->dict[str,Any]:
    p=project(pid);master=Path(p.get("master_path") or p.get("source_path") or "")
    if not master.exists():raise HTTPException(409,"먼저 마스터 이미지를 생성하세요.")
    raw,model=await gemini_static_image(master,motion_sheet_prompt(phrase,action))
    try:sheet=Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:raise HTTPException(502,"Gemini 키프레임 시트를 읽을 수 없습니다.")
    folder=safe_dir(pid)/"ai_keyframes"/f"slot_{slot_no:02d}";folder.mkdir(parents=True,exist_ok=True)
    # Gemini returns one horizontal storyboard. Python performs deterministic frame extraction and WebP encoding.
    panel_w=sheet.width/5;cleaned=[]
    for i in range(5):
        left=round(i*panel_w);right=round((i+1)*panel_w)
        panel=sheet.crop((left,0,right,sheet.height))
        panel=ImageOps.fit(panel,(740,640),method=Image.Resampling.LANCZOS)
        panel_path=folder/f"{i+1:02d}.png";panel.save(panel_path,"PNG",optimize=True);cleaned.append(panel)
    sequence=[*cleaned,cleaned[0]];frames=[]
    for left,right in zip(sequence,sequence[1:]):
        for n in range(4):frames.append(Image.blend(left,right,n/4))
    frames.append(cleaned[0]);out=safe_dir(pid)/f"motion_{slot_no:02d}_ai_sheet.webp"
    frames[0].save(out,save_all=True,append_images=frames[1:],duration=95,loop=0,lossless=False,quality=86,method=4)
    now=datetime.now(timezone.utc).isoformat()
    with db() as con:
        con.execute("INSERT OR REPLACE INTO motion_assets VALUES(?,?,?,?,?)",(pid,slot_no,str(out),"gemini_keyframe_sheet",now))
        con.execute("UPDATE projects SET motion_path=?,status=? WHERE id=?",(str(out),"SAMPLE_REVIEW",pid))
    record_event(pid,"AI_MOTION_SHEET_GENERATED",out,provider="gemini_keyframe_sheet",model=model,external=True,details={"slot_no":slot_no,"action":action,"keyframes":5,"paid_fallback":False})
    return {"slot_no":slot_no,"motion_url":f"/api/projects/{pid}/files/{out.name}","provider":"gemini_keyframe_sheet","model":model,"paid":False,"cost_krw":0,"articulated_motion":True,"keyframes":5}

@app.post("/api/projects/{pid}/motions/ai-samples")
async def ai_motion_samples(pid:str):
    project(pid)
    specs=[(1,"run","지금 가!"),(2,"wave","안녕!"),(3,"jump","신난다")]
    items=[]
    # Sequential calls keep the free-tier request rate conservative and prevent surprise parallel quota use.
    for slot,action,phrase in specs:items.append(await generate_ai_motion_sheet(pid,slot,action,phrase))
    return {"items":items,"provider":"gemini_keyframe_sheet","paid":False,"cost_krw":0,"quality_rule":"reference anatomy first; no geometric puppet fallback"}

@app.get("/api/projects/{pid}/motions")
def get_motions(pid:str):
    project(pid)
    with db() as con:rows=con.execute("SELECT * FROM motion_assets WHERE project_id=? ORDER BY slot_no",(pid,)).fetchall()
    valid=[x for x in rows if x["provider"]!="local_python_rig_v1" and Path(x["path"]).exists()]
    return {"items":[{"slot_no":x["slot_no"],"provider":x["provider"],"url":f"/api/projects/{pid}/files/{Path(x['path']).name}?v={int(Path(x['path']).stat().st_mtime)}","articulated_motion":True} for x in valid]}

@app.post("/api/projects/{pid}/keyframes/compile")
def compile_ai_keyframes(pid:str,body:dict[str,Any]|None=None):
    project(pid);body=body or {};action=str(body.get("action","wave"));slot=int(body.get("slot_no",2));folder=safe_dir(pid)/"ai_keyframes"/action
    files=sorted(p for p in folder.glob("*.png") if len(p.stem)>=2 and p.stem[:2].isdigit())
    if len(files)<3:raise HTTPException(409,"AI 키프레임 PNG가 3장 이상 필요합니다.")
    cleaned=[]
    for i,path in enumerate(files[:8]):
        # ImageGen already drew the final character anatomy.  Re-running the generic
        # cutout removes the characters' white faces/bodies together with the pale
        # background, so preserve the drawing and only neutralise the preview grid.
        source=Image.open(path).convert("RGB")
        gray=ImageOps.grayscale(source)
        gray=ImageOps.autocontrast(gray,cutoff=1)
        gray=gray.point(lambda value: 255 if value >= 205 else value)
        frame=ImageOps.contain(gray,(660,560),method=Image.Resampling.LANCZOS)
        canvas=Image.new("L",(740,640),255)
        canvas.paste(frame,((740-frame.width)//2,(640-frame.height)//2))
        frame=canvas.convert("RGBA")
        clean_path=folder/f"clean_{i+1:02d}.png";frame.save(clean_path,"PNG",optimize=True);cleaned.append(frame)
    # Keep the five authored poses exact. Pixel blending creates ghost limbs and
    # visibly softens the hand-drawn line, which is worse than discrete animation.
    frames=cleaned
    out=safe_dir(pid)/f"motion_{slot:02d}_ai_keyframes.webp"
    frames[0].save(out,save_all=True,append_images=frames[1:],duration=[120,100,110,100,150][:len(frames)],loop=0,lossless=True,method=6)
    with db() as con:
        con.execute("INSERT OR REPLACE INTO motion_assets VALUES(?,?,?,?,?)",(pid,slot,str(out),"codex_imagegen_keyframes",datetime.now(timezone.utc).isoformat()))
        con.execute("UPDATE projects SET motion_path=?,status=? WHERE id=?",(str(out),"SAMPLE_REVIEW",pid))
    record_event(pid,"AI_KEYFRAME_MOTION_COMPILED",out,provider="codex_imagegen_keyframes",external=True,details={"slot_no":slot,"action":action,"generated_keyframes":len(cleaned),"frames":len(frames)})
    return {"motion_url":f"/api/projects/{pid}/files/{out.name}","slot_no":slot,"frames":len(frames),"provider":"codex_imagegen_keyframes","paid_api_called_by_app":False,"articulated_motion":True}

@app.post("/api/projects/{pid}/qc")
def qc_project(pid:str):
    p=project(pid);checks=[]
    motion=Path(p["motion_path"]) if p.get("motion_path") else None
    if not motion or not motion.exists():raise HTTPException(409,"검사할 움직이는 WebP가 없습니다.")
    im=Image.open(motion);frames=getattr(im,"n_frames",1);size=motion.stat().st_size
    first=None;last=None
    for n in range(frames):
        im.seek(n);rgba=im.convert("RGBA")
        if n==0:first=rgba.copy()
        if n==frames-1:last=rgba.copy()
    import hashlib
    loop_match=hashlib.sha256(first.tobytes()).digest()==hashlib.sha256(last.tobytes()).digest()
    checks.extend([
      {"id":"canvas","label":"캔버스 740 × 640","passed":im.size==(740,640),"value":f"{im.width} × {im.height}"},
      {"id":"bytes","label":"파일 1MB 이하","passed":size<=1048576,"value":size},
      {"id":"frames","label":"100프레임 이하","passed":frames<=100,"value":frames},
      {"id":"loop","label":"첫·마지막 프레임 일치","passed":loop_match,"value":loop_match},
      {"id":"alpha","label":"투명 배경 가능 형식","passed":motion.suffix.lower()==".webp","value":"animated/webp"}])
    return {"checks":checks,"passed":all(x["passed"] for x in checks),"score":round(sum(x["passed"] for x in checks)/len(checks)*100),"note":"파일 규격 통과는 OGQ 심사 통과를 의미하지 않습니다."}

@app.post("/api/projects/{pid}/exports/ogq")
def export_ogq(pid:str):
    p=project(pid);report=qc_project(pid)
    if not report["passed"]:raise HTTPException(409,{"message":"QC 문제를 먼저 수정하세요.","qc":report})
    folder=safe_dir(pid);master=Image.open(p["master_path"]).convert("RGBA")
    main=ImageOps.fit(master,(240,240),method=Image.Resampling.LANCZOS);tab=ImageOps.fit(master,(96,74),method=Image.Resampling.LANCZOS)
    main_path=folder/"main.png";tab_path=folder/"tab.png";main.save(main_path);tab.save(tab_path)
    proof=provenance_document(pid)
    meta={"project_id":pid,"created_at":datetime.now(timezone.utc).isoformat(),"free_only":True,"paid_cost_krw":0,"ai_assisted":True,"ogq_approval_guaranteed":False,"qc":report}
    meta_path=folder/"metadata.json";meta_path.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    proof_path=folder/"provenance.json";proof_path.write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding="utf-8")
    out=folder/"ogq_submission_preview.zip"
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
        z.write(p["motion_path"],"animated/01.webp");z.write(main_path,"main.png");z.write(tab_path,"tab.png");z.write(meta_path,"metadata.json");z.write(proof_path,"provenance.json")
    record_event(pid,"OGQ_PREVIEW_EXPORTED",out,details={"approval_guaranteed":False})
    return {"download_url":f"/api/projects/{pid}/files/{out.name}","paid":False,"cost_krw":0,"contents":["animated/01.webp","main.png","tab.png","metadata.json","provenance.json"],"warning":"현재는 1개 샘플 파이프라인 ZIP입니다. 24개 전체 생성 후 최종 제출 패키지로 확장됩니다."}

@app.put("/api/projects/{pid}/brand")
def save_brand(pid:str,body:dict[str,Any]):
    project(pid)
    required=("brand_name","character_name","creator_alias","human_contribution")
    missing=[x for x in required if not str(body.get(x,"")).strip()]
    if missing:raise HTTPException(400,"브랜드 증빙 필수 항목: "+", ".join(missing))
    if not body.get("source_rights_confirmed") or not body.get("commercial_use_confirmed"):
        raise HTTPException(400,"원본 사용 권리와 상업적 이용 권한을 확인해야 합니다.")
    now=datetime.now(timezone.utc).isoformat()
    values=(pid,*[str(body[x]).strip()[:1000] for x in required],1,1,now)
    with db() as con:con.execute("INSERT OR REPLACE INTO project_brand VALUES(?,?,?,?,?,?,?,?)",values)
    record_event(pid,"BRAND_DECLARATION_UPDATED",details={"brand_name":values[1],"character_name":values[2],"human_contribution_recorded":True})
    return {"saved":True,"updated_at":now,"note":"실명 대신 활동명 저장을 권장합니다. 이 선언은 등록 권리를 대신하지 않습니다."}

@app.get("/api/projects/{pid}/provenance")
def get_provenance(pid:str):return provenance_document(pid)

@app.post("/api/projects/{pid}/provenance/verify")
def verify_provenance(pid:str,body:dict[str,Any]):
    expected=provenance_document(pid)["signature"]["value"]
    supplied=str(body.get("signature", ""))
    return {"valid":bool(supplied) and hmac.compare_digest(expected,supplied),"scope":"현재 로컬 설치의 데이터베이스와 파일 기준"}

@app.get("/api/projects/{pid}/files/{name}")
def file(pid:str,name:str):
    project(pid);path=(safe_dir(pid)/Path(name).name).resolve()
    if not path.exists():raise HTTPException(404,"파일이 없습니다.")
    return FileResponse(path)
