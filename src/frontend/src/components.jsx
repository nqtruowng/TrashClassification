import { useState } from "react";

const iconPaths = {
  leaf: <><path d="M20.5 3.5C12 3.5 5 5.6 5 12.3a5.1 5.1 0 0 0 5.2 5.2c6.7 0 8.8-7 8.8-15.5Z" /><path d="M3 21c2.7-5.4 6.5-8.9 11.6-11.5" /></>,
  camera: <><path d="M4 7h3l2-2h6l2 2h3a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2Z" /><circle cx="12" cy="13" r="3.5" /></>,
  image: <><rect x="3" y="3" width="18" height="18" rx="3" /><circle cx="8.5" cy="8.5" r="1.5" /><path d="m21 15-5-5L5 21" /></>,
  video: <><rect x="3" y="5" width="13" height="14" rx="2" /><path d="m16 10 5-3v10l-5-3" /></>,
  upload: <><path d="M12 16V4m0 0L7 9m5-5 5 5" /><path d="M5 14v5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-5" /></>,
  scan: <><circle cx="10.8" cy="10.8" r="6.8" /><path d="m16 16 5 5M10.8 7.5v6.6M7.5 10.8h6.6" /></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></>,
  shield: <><path d="M12 3 4 7v5c0 5 3.4 8 8 9 4.6-1 8-4 8-9V7l-8-4Z" /><path d="m8.5 12 2.2 2.2 4.8-5" /></>,
  recycle: <><path d="m7 7 1 14h8l1-14M5 7h14M10 7V4h4v3m-2 4v6" /></>,
  organic: <><path d="M12 21c4.4-2.2 7-5.8 7-10.5C19 6 16 3 12 3S5 6 5 10.5C5 15.2 7.6 18.8 12 21Z" /><path d="M12 20c-.4-5.8 1.1-9.6 4.4-12.5" /></>,
  other: <><path d="M5 4h14v16H5zM8 8h8m-8 4h8m-8 4h5" /></>,
  spark: <><path d="m12 3 1.5 6.5L20 11l-6.5 1.5L12 19l-1.5-6.5L4 11l6.5-1.5L12 3Z" /><path d="m19 16 .7 2.3L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-.7L19 16Z" /></>,
  close: <path d="m6 6 12 12M18 6 6 18" />,
  check: <path d="m5 12 4 4L19 6" />,
  grid: <><rect x="3" y="3" width="8" height="8" rx="2" /><rect x="13" y="3" width="8" height="5" rx="2" /><rect x="13" y="10" width="8" height="11" rx="2" /><rect x="3" y="13" width="8" height="8" rx="2" /></>,
  book: <><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21.5z" /><path d="M4 5.5v16M8 7h8m-8 4h8" /></>,
};

export function Icon({ name, size = 18, className = "" }) {
  return <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{iconPaths[name]}</svg>;
}

export function Brand() {
  return <a className="brand" href="#recognition" aria-label="GreenLens trang nhận diện"><span className="brand-mark"><Icon name="leaf" size={19} /></span><span>Green<em>Lens</em></span></a>;
}

export function Sidebar({ page, onNavigate }) {
  const links = [
    ["dashboard", "\u0054\u1ed5ng quan", "grid"],
    ["recognition", "AI nh\u1eadn di\u1ec7n", "scan"],
    ["history", "L\u1ecbch s\u1eed phi\u00ean", "calendar"],
    ["guide", "C\u1ea9m nang t\u00e1i ch\u1ebf", "book"],
  ];
  return <aside className="sidebar">
    <Brand />
    <div className="workspace-label">USER WORKSPACE<strong>Trash classification</strong></div>
    <p className="nav-caption">WORKSPACE</p>
    <nav className="side-nav" aria-label="\u0110i\u1ec1u h\u01b0\u1edbng ch\u00ednh">
      {links.map(([id, label, icon]) => <a key={id} href={`#${id}`} onClick={(event) => onNavigate(event, id)} className={`side-nav-item ${page === id ? "is-selected" : ""}`} aria-current={page === id ? "page" : undefined}><Icon name={icon} />{label}</a>)}
    </nav>
    <div className="sidebar-note"><strong>Phiên hiện tại</strong><small>Số liệu nhận diện được tính trong phiên này.</small></div>
    <div className="sidebar-status"><i /><span><strong>Model sẵn sàng</strong><small>YOLO26n · chạy cục bộ</small></span></div>
  </aside>;
}

export function AppHeader({ page, user, onLogout, onAdmin }) {
  const labels = { dashboard: "T\u1ed5ng quan", recognition: "AI nh\u1eadn di\u1ec7n", history: "L\u1ecbch s\u1eed phi\u00ean", guide: "C\u1ea9m nang t\u00e1i ch\u1ebf" };
  return <header className="topbar"><div className="breadcrumb">User workspace <span>/</span> <b>{labels[page] || labels.dashboard}</b></div><div className="topbar-right"><span className="model-status"><i /> Đang hoạt động</span><span className="account-email">{user.email}</span><button className="logout-button" type="button" onClick={onAdmin}>Admin portal</button><button className="logout-button" type="button" onClick={onLogout}>Đăng xuất</button></div></header>;
}

export function AuthPage({ onAuthenticated }) {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    setError("");
    if (isRegister && password !== confirmPassword) {
      setError("Mật khẩu xác nhận chưa trùng khớp.");
      return;
    }
    setLoading(true);
    try {
      const response = await fetch(`/api/auth/${isRegister ? "register" : "login"}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ email, password }),
      });
      const data = await response.json();
      if (!response.ok) {
        const detail = typeof data.detail === "string" ? data.detail : "Thông tin chưa hợp lệ. Hãy kiểm tra email và mật khẩu.";
        throw new Error(data.error || detail);
      }
      onAuthenticated(data.user);
    } catch (requestError) {
      setError(requestError.message || "Không kết nối được máy chủ. Hãy thử lại sau.");
    } finally {
      setLoading(false);
    }
  }

  return <main className="auth-page">
    <section className="auth-card">
      <Brand />
      <p className="eyebrow">KHÔNG GIAN CỦA BẠN</p>
      <h1>{isRegister ? "Tạo tài khoản" : "Chào mừng trở lại"}</h1>
      <p className="auth-description">{isRegister ? "Tạo tài khoản để bắt đầu sử dụng trợ lý phân loại rác." : "Đăng nhập để tiếp tục sử dụng GreenLens."}</p>
      <form className="auth-form" onSubmit={submit}>
        <label htmlFor="auth-email">Tài khoản</label>
        <input id="auth-email" type="email" autoComplete="email" required maxLength={254} value={email} onChange={(event) => setEmail(event.target.value)} />
        <label htmlFor="auth-password">Mật khẩu</label>
        <input id="auth-password" type="password" autoComplete={isRegister ? "new-password" : "current-password"} required minLength={8} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Ít nhất 8 ký tự" />
        {isRegister && <><label htmlFor="auth-confirm-password">Nhập lại mật khẩu</label><input id="auth-confirm-password" type="password" autoComplete="new-password" required minLength={8} maxLength={128} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} placeholder="Nhập lại mật khẩu" /></>}
        {error && <p className="auth-error" role="alert">{error}</p>}
        <button className="button button-green auth-submit" type="submit" disabled={loading}>{loading ? "Đang xử lý…" : isRegister ? "Tạo tài khoản" : "Đăng nhập"}</button>
      </form>
      <p className="auth-switch">{isRegister ? "Đã có tài khoản?" : "Chưa có tài khoản?"} <button type="button" onClick={() => { setIsRegister(!isRegister); setError(""); }}> {isRegister ? "Đăng nhập" : "Tạo tài khoản"}</button></p>
      <p className="auth-security"><Icon name="shield" size={15} />Mật khẩu được mã hóa trước khi lưu trữ.</p>
    </section>
    <aside className="auth-aside"><span className="auth-leaf"><Icon name="leaf" size={26} /></span><p className="eyebrow">GREENLENS</p><h2>Nhận diện rác,<br /><span>sống xanh hơn.</span></h2><p>Phân loại rác hữu cơ, tái chế và khó tái chế qua ảnh, video hoặc camera trực tuyến.</p><div className="auth-aside-note"><Icon name="spark" size={18} />Trợ lý phân loại luôn sẵn sàng khi bạn cần.</div></aside>
  </main>;
}

const guideCategories = [
  {
    id: "organic", label: "Hữu cơ", model: "Biodegradable", icon: "organic",
    examples: "Thức ăn thừa, vỏ rau củ quả, bã cà phê, lá cây.",
    action: "Để ráo nước và bỏ vào thùng rác hữu cơ hoặc nơi ủ compost nếu địa phương có hỗ trợ.",
  },
  {
    id: "recycle", label: "Có thể tái chế", model: "Recyclable", icon: "recycle",
    examples: "Chai nhựa, lon kim loại, chai lọ thủy tinh, giấy và bìa sạch.",
    action: "Làm sạch thức ăn hoặc chất lỏng còn lại, để khô và phân loại theo hướng dẫn điểm thu gom.",
  },
  {
    id: "other", label: "Khó tái chế", model: "Non-recyclable", icon: "other",
    examples: "Bao bì nhiều lớp, vật liệu dính bẩn hoặc đồ không có điểm thu gom phù hợp.",
    action: "Gạt bỏ phần thừa và bỏ vào thùng rác còn lại theo quy định tại nơi bạn sống.",
  },
];

export function GuidePage() {
  return <div className="guide-page">
    <div className="page-heading guide-heading">
      <div><p className="eyebrow">CẨM NANG SỬ DỤNG</p><h1>Phân loại đúng,<br /><span>giảm rác mỗi ngày.</span></h1><p>Tham khảo cách xử lý cho ba nhóm rác GreenLens nhận diện.</p></div>
      <a className="button button-green guide-cta" href="#recognition">Bắt đầu nhận diện <span aria-hidden="true">→</span></a>
    </div>
    <section className="guide-categories" aria-label="Hướng dẫn theo nhóm rác">
      {guideCategories.map((category, index) => <article className={`guide-card guide-${category.id}`} key={category.id}>
        <div className="guide-card-top"><span className="guide-icon"><Icon name={category.icon} size={21} /></span><span className="guide-index">0{index + 1}</span></div>
        <h2>{category.label}</h2><span className="guide-model-label">NHÃN MODEL · {category.model}</span>
        <div className="guide-detail"><h3>Ví dụ thường gặp</h3><p>{category.examples}</p></div>
        <div className="guide-detail guide-action"><h3>Cách xử lý gợi ý</h3><p>{category.action}</p></div>
      </article>)}
    </section>
    <section className="guide-steps" aria-labelledby="guide-steps-title">
      <div className="guide-steps-heading"><p className="eyebrow">QUY TRÌNH NHANH</p><h2 id="guide-steps-title">Ba bước trước khi bỏ rác</h2></div>
      <ol>{[
        ["Nhận diện", "Dùng ảnh, video hoặc camera để xem nhóm rác model dự đoán."],
        ["Kiểm tra", "Xem lại vật liệu và mức độ sạch; kết quả AI chỉ mang tính tham khảo."],
        ["Phân loại", "Làm theo quy định thu gom tại khu vực của bạn."],
      ].map(([title, description], index) => <li key={title}><span>{index + 1}</span><div><strong>{title}</strong><p>{description}</p></div></li>)}</ol>
    </section>
    <p className="guide-footnote"><Icon name="shield" size={16} />Quy định tái chế khác nhau theo địa phương. Hãy kiểm tra hướng dẫn từ đơn vị thu gom gần bạn.</p>
  </div>;
}

export function PageHeading({ today }) {
  return <div className="page-heading" id="top">
    <div><p className="eyebrow">TRỢ LÝ PHÂN LOẠI RÁC</p><h1>Nhận diện rác,<br /><span>sống xanh hơn.</span></h1><p>Chọn ảnh, video hoặc camera trực tuyến để bắt đầu.</p></div>
    <span className="pill date-pill"><Icon name="calendar" size={15} />{today}</span>
  </div>;
}

export function StatCard({ label, value, foot, icon }) {
  return <article className="stat-card"><div className="stat-top"><span>{label}</span><span className="stat-icon"><Icon name={icon} /></span></div><div className="stat-value">{value}</div><div className="stat-foot">{foot}</div></article>;
}

const modes = [
  { id: "image", label: "Ảnh", detail: "JPG, PNG", icon: "image" },
  { id: "video", label: "Video", detail: "Phân tích theo khung hình", icon: "video" },
  { id: "live", label: "Camera trực tuyến", detail: "Nhận diện liên tục", icon: "camera" },
];

function ModeSelector({ mode, onChange, disabled }) {
  return <div className="mode-selector" role="tablist" aria-label="Chọn chế độ nhận diện">
    {modes.map((item) => <button key={item.id} type="button" role="tab" aria-selected={mode === item.id} className={`mode-option ${mode === item.id ? "is-active" : ""}`} disabled={disabled} onClick={() => onChange(item.id)}>
      <span className="mode-icon"><Icon name={item.icon} size={19} /></span><span className="mode-label"><strong>{item.label}</strong><small>{item.detail}</small></span>
    </button>)}
  </div>;
}

export function RecognitionPanel({
  mode, onModeChange, videoRef, fileRef, videoFileRef, streaming, previewUrl,
  videoUrl, resultImageUrl, result, selectedFile, selectedVideo, loading,
  modeLocked, videoProgress, error, cameraError, toggleCamera, selectFile, selectVideo, analyze,
}) {
  const imageForOverlay = mode === "image" && resultImageUrl;
  return <article className="panel camera-panel" id="recognition">
    <div className="panel-heading recognition-heading"><div><h2>Không gian nhận diện</h2><p>Chọn một chế độ để phân loại vật thể</p></div><span className={`pill ${streaming ? "pill-live" : ""}`}><i className="dot" />{streaming ? "Đang nhận diện" : "Model sẵn sàng"}</span></div>
    <ModeSelector mode={mode} onChange={onModeChange} disabled={modeLocked} />
    <div className={`camera-stage ${imageForOverlay || previewUrl || videoUrl || streaming ? "has-image" : ""}`}>
      {mode === "image" && imageForOverlay && <>
        <img className="camera-media" src={resultImageUrl} alt="Ảnh kết quả nhận diện" />
        {result?.found && result.image_size?.length === 2 && <svg className="detection-overlay" viewBox={`0 0 ${result.image_size[0]} ${result.image_size[1]}`} preserveAspectRatio="xMidYMid meet" aria-label="Khung nhận diện">
          {result.detections.map((detection, index) => {
            const [x1, y1, x2, y2] = detection.box || [];
            if (![x1, y1, x2, y2].every(Number.isFinite)) return null;
            const color = { recycle: "#73d18a", non_recyclable: "#ef8a79", organic: "#c4e66b", other: "#f0bd62" }[detection.category] || "#f0bd62";
            const fontSize = Math.max(14, Math.min(result.image_size[0], result.image_size[1]) * 0.035);
            return <g key={`${detection.class_name}-${index}`}><rect x={x1} y={y1} width={Math.max(0, x2 - x1)} height={Math.max(0, y2 - y1)} fill={`${color}20`} stroke={color} strokeWidth={Math.max(3, fontSize / 7)} /><text x={x1} y={Math.max(fontSize, y1 - 6)} fill={color} stroke="#14231a" strokeWidth={fontSize / 5} paintOrder="stroke" fontSize={fontSize} fontWeight="700">{detection.label} {Math.round(detection.confidence * 100)}%</text></g>;
          })}
        </svg>}
      </>}
      {mode === "image" && !imageForOverlay && previewUrl && <img className="camera-media" src={previewUrl} alt="Ảnh đã chọn để nhận diện" />}
      {mode === "video" && videoUrl && <video className="camera-media video-preview" src={videoUrl} controls preload="metadata" aria-label="Video đã chọn để nhận diện" />}
      {mode === "live" && streaming && <video ref={videoRef} className="camera-media" autoPlay playsInline muted aria-label="Hình ảnh camera trực tuyến" />}
      {((mode === "image" && !previewUrl && !resultImageUrl) || (mode === "video" && !videoUrl) || (mode === "live" && !streaming)) && <>
        <span className="scan-frame" />
        <span className="drop-content">
          <span className="upload-icon"><Icon name={mode === "image" ? "image" : mode === "video" ? "video" : "camera"} size={23} /></span>
          <strong>{mode === "image" ? "Chọn ảnh cần phân loại" : mode === "video" ? "Chọn video cần phân tích" : "Sẵn sàng kết nối camera"}</strong>
          <span>{mode === "image" ? "Hỗ trợ JPG, PNG" : mode === "video" ? "Video được phân tích tối đa 8 khung hình" : "Cho phép trình duyệt truy cập camera để bắt đầu"}</span>
        </span>
      </>}
      {mode === "image" && (previewUrl || resultImageUrl) && <span className="camera-hint">Ảnh đã chọn</span>}
      {mode === "video" && videoUrl && <span className="camera-hint">Video · {selectedVideo?.name}</span>}
      {streaming && <span className="camera-live"><i /> LIVE · ĐANG NHẬN DIỆN</span>}
    </div>

    {mode === "image" && <>
      <input ref={fileRef} className="visually-hidden" type="file" accept="image/*" onChange={selectFile} aria-label="Chọn ảnh để nhận diện" />
      <div className="camera-actions"><button className="button button-green" type="button" onClick={() => fileRef.current?.click()}><Icon name="upload" />{selectedFile ? "Đổi ảnh" : "Chọn ảnh"}</button><button className="button button-lime analyze-button" type="button" disabled={loading || !selectedFile} onClick={analyze}><Icon name="scan" />{loading ? "Đang nhận diện…" : "Phân tích ảnh"}<span aria-hidden="true">→</span></button></div>
      {selectedFile && <p className="selected-file">Ảnh: <strong>{selectedFile.name}</strong></p>}
    </>}

    {mode === "video" && <>
      <input ref={videoFileRef} className="visually-hidden" type="file" accept="video/*" onChange={selectVideo} aria-label="Chọn video để nhận diện" />
      <div className="camera-actions"><button className="button button-green" type="button" onClick={() => videoFileRef.current?.click()}><Icon name="upload" />{selectedVideo ? "Đổi video" : "Chọn video"}</button><button className="button button-lime analyze-button" type="button" disabled={loading || !selectedVideo} onClick={analyze}><Icon name="scan" />{loading ? "Đang phân tích…" : "Phân tích video"}<span aria-hidden="true">→</span></button></div>
      {selectedVideo && <p className="selected-file">Video: <strong>{selectedVideo.name}</strong>{videoProgress && <span className="video-progress">{videoProgress}</span>}</p>}
    </>}

    {mode === "live" && <div className="camera-actions live-actions"><button className={`button ${streaming ? "button-muted" : "button-green"}`} type="button" onClick={toggleCamera}><Icon name={streaming ? "close" : "camera"} />{streaming ? "Dừng camera" : "Bật camera trực tuyến"}</button><span className="live-help">{streaming ? "Đang phân tích khung hình định kỳ" : "Camera sẽ nhận diện tự động sau khi được bật"}</span></div>}

    {cameraError && <p className="inline-error" role="alert">{cameraError}</p>}
    {error && <p className="inline-error" role="alert">{error}</p>}
    <div className="privacy-note"><Icon name="shield" size={15} />Ảnh và video được xử lý trên hệ thống GreenLens.</div>
  </article>;
}

export function ResultCard({ best, result, loading, confidence, videoProgress }) {
  const categoryIcon = best?.category === "recycle" ? "recycle" : best?.category === "organic" ? "organic" : "other";
  return <article className="panel result-panel"><div className="panel-heading"><div><h2>Kết quả nhận diện</h2><p>Phân loại và hướng dẫn xử lý</p></div><span className={`pill ${best ? "pill-success" : ""}`}>{loading ? "Đang phân tích" : best ? `${result.detections.length} vật thể` : result ? "Không phát hiện" : "Chờ nhận diện"}</span></div>
    {videoProgress && <div className="result-progress"><span style={{ width: `${videoProgress.percent}%` }} /></div>}
    {!best ? <div className="result-placeholder"><Icon name="spark" size={23} /><p>{result?.message || "Kết quả và hướng dẫn xử lý sẽ hiển thị ở đây."}</p></div> : <div className="result-content">
      <div className="prediction-title"><span className={`category-icon category-${best.category}`}><Icon name={categoryIcon} size={20} /></span><div><small>Loại rác được dự đoán</small><strong>{best.label}</strong></div></div>
      <div className="confidence-block"><div className="confidence-label"><span>Độ tin cậy</span><strong>{confidence}%</strong></div><div className="meter"><span style={{ width: `${confidence}%` }} /></div></div>
      <div className="advice"><Icon name="check" size={16} /><p><strong>Gợi ý xử lý:</strong> {best.advice}{confidence < 50 && " Độ tin cậy thấp, hãy thử chọn khung hình rõ hơn."}</p></div>
      {result.detections.length > 1 && <div className="extra-detections">Còn {result.detections.length - 1} vật thể khác trong khung hình.</div>}
    </div>}
  </article>;
}

export function SessionCard({ counts, total }) {
  return <article className="panel stats-panel"><div className="stats-heading"><h2>Thống kê phiên này</h2><span>{total} lượt</span></div><div className="stats-grid">
    <div className="stat-box"><span><i className="dot-recycle" />Tái chế</span><strong>{String(counts.recycle).padStart(2, "0")}</strong></div>
    <div className="stat-box"><span><i className="dot-non-recyclable" />Không tái chế</span><strong>{String(counts.non_recyclable).padStart(2, "0")}</strong></div>
    <div className="stat-box"><span><i className="dot-organic" />Hữu cơ</span><strong>{String(counts.organic).padStart(2, "0")}</strong></div>
    <div className="stat-box"><span><i className="dot-other" />Khác</span><strong>{String(counts.other).padStart(2, "0")}</strong></div>
  </div></article>;
}


export function DashboardPage({ total, recycleRate, confidence, onNavigate }) {
  return <>
    <div className="main-head"><div><p className="eyebrow">TỔNG QUAN CÁ NHÂN</p><h1>Chào bạn</h1><p className="subhead">Theo dõi các phiên nhận diện trong lần sử dụng này.</p></div><button className="button button-green" type="button" onClick={() => onNavigate("recognition")}>Bắt đầu nhận diện <Icon name="scan" /></button></div>
    <section className="cards user-stats" aria-label="Thống kê phiên nhận diện">
      <StatCard label="Vật thể đã nhận diện" value={total} foot="Tổng lượt qua ảnh, video và camera" icon="recycle" />
      <StatCard label="Tỷ lệ tái chế" value={`${recycleRate}%`} foot="Trong phiên hiện tại" icon="image" />
      <StatCard label="Độ tin cậy gần nhất" value={`${confidence}%`} foot="Theo kết quả vừa nhận diện" icon="spark" />
    </section>
    <section className="dashboard-welcome panel"><div><span className="guide-icon"><Icon name="leaf" /></span><h2>Sẵn sàng phân loại rác?</h2><p>Tải ảnh, chọn video hoặc bật camera để nhận gợi ý phân loại.</p></div><button className="button button-outline" type="button" onClick={() => onNavigate("guide")}>Xem cẩm nang</button></section>
  </>;
}

export function HistoryPage({ total, counts }) {
  const hasHistory = total > 0;
  return <div className="history-page"><div className="main-head"><div><p className="eyebrow">LỊCH SỬ PHIÊN</p><h1>Lịch sử nhận diện</h1><p className="subhead">Tổng hợp hoạt động trong phiên hiện tại.</p></div></div><article className="panel"><div className="panel-head"><div><h2>Các nhóm rác đã nhận diện</h2><p>{total} vật thể trong phiên này</p></div></div>{hasHistory ? <div className="history-list">{[["Tái chế", counts.recycle, "recycle"], ["Hữu cơ", counts.organic, "organic"], ["Không tái chế", counts.non_recyclable, "other"], ["Khác", counts.other, "other"]].filter(([, count]) => count > 0).map(([name, count, icon]) => <div className="history-row" key={name}><span className="guide-icon"><Icon name={icon} /></span><strong>{name}</strong><span>{count} vật thể</span></div>)}</div> : <div className="empty-state"><span className="guide-icon"><Icon name="calendar" /></span><strong>Chưa có phiên nhận diện</strong><p>Kết quả sẽ xuất hiện tại đây sau khi bạn phân tích ảnh hoặc video.</p></div>}</article></div>;
}

const adminLinks = [["overview", "Tổng quan", "grid"], ["analytics", "Thống kê", "spark"], ["records", "Lịch sử nhận diện", "calendar"], ["models", "Model & đánh giá", "scan"], ["users", "Người dùng", "other"]];
const demoUsers = [["linh.nguyen@email.com", "248", "5 phút trước", true], ["minh.tran@email.com", "186", "22 phút trước", true], ["ha.pham@email.com", "104", "1 giờ trước", false]];

export function AdminPortal({ onExit }) {
  const [view, setView] = useState("overview");
  const [selectedModel, setSelectedModel] = useState("11-11-2026-yolo26n");
  const title = adminLinks.find(([id]) => id === view)?.[1] || "Tổng quan";
  return <div className="app-shell admin-app">
    <aside className="sidebar admin-sidebar"><Brand /><div className="workspace-label">ADMIN CONSOLE<strong>Quản trị hệ thống</strong></div><p className="nav-caption">QUẢN LÝ</p><nav className="side-nav" aria-label="Điều hướng admin">{adminLinks.map(([id, label, icon]) => <button key={id} className={`side-nav-item ${view === id ? "is-selected" : ""}`} type="button" onClick={() => setView(id)}><Icon name={icon} />{label}</button>)}</nav><div className="sidebar-note"><strong>Admin workspace</strong><small>Theo dõi dữ liệu toàn hệ thống</small></div><div className="sidebar-status"><span className="avatar">A</span><span><strong>System Admin</strong><small>Quản trị viên</small></span></div></aside>
    <div className="app-content"><header className="topbar"><div className="breadcrumb">Admin <span>/</span> <b>{title}</b></div><button className="logout-button" type="button" onClick={onExit}>Mở User portal</button></header><main className="main-area admin-main">
      {view === "overview" && <><div className="main-head"><div><p className="eyebrow">TOÀN HỆ THỐNG</p><h1>Tổng quan</h1><p className="subhead">Tình hình sử dụng và hiệu suất nhận diện.</p></div><span className="pill date-pill">30 ngày qua</span></div><div className="cards admin-stats">{[["Tổng người dùng", "1,284", "+12.8% so với tháng trước"], ["Lượt nhận diện", "18,426", "Tổng trên tất cả tài khoản"], ["User hoạt động", "362", "Trong 30 ngày gần nhất"], ["Model đang chạy", "11-11-2026", "best.pt · YOLO26n"]].map(([label, value, foot]) => <article className="stat-card" key={label}><div className="stat-top">{label}<span className="stat-icon"><Icon name="spark" size={15} /></span></div><div className="stat-value">{value}</div><div className="stat-foot">{foot}</div></article>)}</div><div className="callout preview-data-note">Dữ liệu minh họa cho bản xem trước giao diện.</div><div className="cards admin-overview-grid"><article className="panel"><div className="panel-heading"><div><h2>Lượt nhận diện</h2><p>Khối lượng theo ngày trong 7 ngày</p></div><span className="pill">7 ngày</span></div><div className="chart-bars">{[[42,"T2"],[61,"T3"],[53,"T4"],[78,"T5"],[67,"T6"],[92,"T7"],[72,"CN"]].map(([height, day]) => <div key={day}><i style={{height:`${height}%`}}/><small>{day}</small></div>)}</div></article><article className="panel"><div className="panel-heading"><div><h2>Phân loại rác</h2><p>Tỷ trọng detection</p></div></div><div className="distribution">{[["Tái chế",48,"green"],["Hữu cơ",31,"amber"],["Không tái chế",21,"gray"]].map(([label, value, tone]) => <div className="distribution-item" key={label}><div><span><i className={`legend-dot ${tone}-dot`}/>{label}</span><b>{value}%</b></div><div className={`distribution-bar ${tone}`}><span style={{width:`${value}%`}}/></div></div>)}</div></article></div><article className="panel admin-table-panel"><div className="panel-heading"><div><h2>Người dùng hoạt động</h2><p>Tài khoản có nhiều lượt nhận diện</p></div><button className="text-link" onClick={() => setView("users")}>Xem danh sách</button></div><div className="table-wrap"><table><thead><tr><th>NGƯỜI DÙNG</th><th>LƯỢT NHẬN DIỆN</th><th>HOẠT ĐỘNG GẦN ĐÂY</th><th>TRẠNG THÁI</th></tr></thead><tbody>{demoUsers.map(([email, count, recent, active]) => <tr key={email}><td>{email}</td><td>{count}</td><td>{recent}</td><td><span className={`pill ${active ? "green" : ""}`}>{active ? "Hoạt động" : "Không hoạt động"}</span></td></tr>)}</tbody></table></div></article></>}
      {view === "analytics" && <><div className="main-head"><div><p className="eyebrow">ANALYTICS</p><h1>Thống kê toàn hệ thống</h1><p className="subhead">Xu hướng sử dụng và phân loại theo thời gian.</p></div></div><div className="cards admin-stats">{[["Precision validation","59.93%"],["Recall validation","53.06%"],["mAP@50","56.68%"],["mAP@50–95","41.73%"]].map(([label,value])=><article className="stat-card" key={label}><div className="stat-top">{label}</div><div className="stat-value">{value}</div><div className="stat-foot">YOLO26n · validation</div></article>)}</div><div className="callout preview-data-note">Metric minh họa từ lần validation của model YOLO26n.</div></>}
      {view === "records" && <><div className="main-head"><div><p className="eyebrow">RECOGNITION LOG</p><h1>Lịch sử nhận diện</h1><p className="subhead">Các lượt nhận diện gần đây trên hệ thống.</p></div></div><article className="panel admin-table-panel"><div className="table-wrap"><table><thead><tr><th>NGƯỜI DÙNG</th><th>VẬT THỂ</th><th>PHÂN LOẠI</th><th>ĐỘ TIN CẬY</th><th>THỜI GIAN</th></tr></thead><tbody>{[["linh.nguyen@email.com","Chai nhựa","Tái chế","96%","5 phút trước"],["minh.tran@email.com","Vỏ rau củ","Hữu cơ","91%","22 phút trước"],["ha.pham@email.com","Túi nhiều lớp","Không tái chế","84%","1 giờ trước"]].map(([email,item,category,confidence,time])=><tr key={email}><td>{email}</td><td>{item}</td><td>{category}</td><td>{confidence}</td><td>{time}</td></tr>)}</tbody></table></div><div className="table-note">Dữ liệu minh họa cho bản xem trước giao diện.</div></article></>}
      {view === "models" && <><div className="main-head"><div><p className="eyebrow">MODEL CENTER</p><h1>Model & đánh giá</h1><p className="subhead">Model hiện được chọn để phục vụ nhận diện.</p></div><span className="pill green">Inference: {selectedModel}</span></div><div className="cards model-admin-grid"><article className="panel"><div className="panel-heading"><div><h2>Model trong workspace</h2><p>Chọn model dùng cho request tiếp theo.</p></div></div><div className="model-options">{[["11-11-2026-yolo26n","YOLO26n · best.pt"],["10-11-2026-yolo26n","YOLO26n · checkpoint"]].map(([name,detail])=><label className={`model-option ${selectedModel===name?'selected':''}`} key={name}><input type="radio" name="admin-model" checked={selectedModel===name} onChange={()=>setSelectedModel(name)} /><span><b>{name}</b><small>{detail}</small></span><em>{selectedModel===name?"Đang chạy":"Chọn"}</em></label>)}</div></article><article className="panel"><div className="panel-heading"><div><h2>Đánh giá model</h2><p>Metric validation của checkpoint đang chọn.</p></div></div><div className="eval-metrics">{[["Precision","59.93%"],["Recall","53.06%"],["mAP@50","56.68%"]].map(([label,value])=><div key={label}><span>{label}</span><b>{selectedModel==="11-11-2026-yolo26n"?value:"Chưa có dữ liệu"}</b></div>)}</div><p className="table-note">Confidence của một lượt nhận diện không phải Precision validation.</p></article></div></>}
      {view === "users" && <><div className="main-head"><div><p className="eyebrow">USER MANAGEMENT</p><h1>Người dùng</h1><p className="subhead">Theo dõi tài khoản và mức độ sử dụng.</p></div></div><article className="panel admin-table-panel"><div className="table-wrap"><table><thead><tr><th>EMAIL</th><th>LƯỢT NHẬN DIỆN</th><th>LẦN CUỐI</th><th>TRẠNG THÁI</th></tr></thead><tbody>{demoUsers.map(([email,count,recent,active])=><tr key={email}><td>{email}</td><td>{count}</td><td>{recent}</td><td><span className={`pill ${active?'green':''}`}>{active?'Hoạt động':'Không hoạt động'}</span></td></tr>)}</tbody></table></div></article></>}
    </main></div>
  </div>;
}

export function Toast({ children }) {
  return children ? <div className="toast" role="status">{children}</div> : null;
}
