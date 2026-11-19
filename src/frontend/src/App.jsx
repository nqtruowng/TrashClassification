import { useEffect, useRef, useState } from "react";

const iconPaths = {
  leaf: <><path d="M20.5 3.5C12 3.5 5 5.6 5 12.3a5.1 5.1 0 0 0 5.2 5.2c6.7 0 8.8-7 8.8-15.5Z" /><path d="M3 21c2.7-5.4 6.5-8.9 11.6-11.5" /></>,
  camera: <><path d="M4 7h3l2-2h6l2 2h3a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2Z" /><circle cx="12" cy="13" r="3.5" /></>,
  upload: <><path d="M12 16V4m0 0L7 9m5-5 5 5" /><path d="M5 14v5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-5" /></>,
  scan: <><circle cx="10.8" cy="10.8" r="6.8" /><path d="m16 16 5 5M10.8 7.5v6.6M7.5 10.8h6.6" /></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></>,
  shield: <><path d="M12 3 4 7v5c0 5 3.4 8 8 9 4.6-1 8-4 8-9V7l-8-4Z" /><path d="m8.5 12 2.2 2.2 4.8-5" /></>,
  recycle: <><path d="m7 7 1 14h8l1-14M5 7h14M10 7V4h4v3m-2 4v6" /></>,
  organic: <><path d="M12 21c4.4-2.2 7-5.8 7-10.5C19 6 16 3 12 3S5 6 5 10.5C5 15.2 7.6 18.8 12 21Z" /><path d="M12 20c-.4-5.8 1.1-9.6 4.4-12.5" /></>,
  other: <><path d="M5 4h14v16H5zM8 8h8m-8 4h8m-8 4h5" /></>,
  spark: <><path d="m12 3 1.5 6.5L20 11l-6.5 1.5L12 19l-1.5-6.5L4 11l6.5-1.5L12 3Z" /><path d="m19 16 .7 2.3L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-.7L19 16Z" /></>,
  close: <><path d="m6 6 12 12M18 6 6 18" /></>,
  check: <path d="m5 12 4 4L19 6" />,
};

function Icon({ name, size = 18, className = "" }) {
  return <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{iconPaths[name]}</svg>;
}

function formatTime(date) {
  return new Intl.DateTimeFormat("vi-VN", { hour: "2-digit", minute: "2-digit" }).format(date);
}

function categoryIcon(category) {
  if (category === "recycle") return "recycle";
  if (category === "organic") return "organic";
  return "other";
}

const detectionColors = { recycle: "#73d18a", non_recyclable: "#ef8a79", organic: "#c4e66b", other: "#f0bd62" };

function App() {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const fileRef = useRef(null);
  const [streaming, setStreaming] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [resultImageUrl, setResultImageUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [counts, setCounts] = useState({ recycle: 0, non_recyclable: 0, organic: 0, other: 0 });
  const [toast, setToast] = useState("");
  const [cameraError, setCameraError] = useState("");

  useEffect(() => () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
  }, []);

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  useEffect(() => () => {
    if (resultImageUrl) URL.revokeObjectURL(resultImageUrl);
  }, [resultImageUrl]);

  useEffect(() => {
    if (!toast) return undefined;
    const timer = window.setTimeout(() => setToast(""), 2800);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    if (videoRef.current && streamRef.current) videoRef.current.srcObject = streamRef.current;
  }, [streaming]);

  async function toggleCamera() {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      setStreaming(false);
      setResult(null);
      setResultImageUrl("");
      setCameraError("");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
      streamRef.current = stream;
      setSelectedFile(null);
      setPreviewUrl("");
      setResult(null);
      setResultImageUrl("");
      setCameraError("");
      setStreaming(true);
    } catch {
      setCameraError("Không mở được camera. Hãy cấp quyền truy cập hoặc tải ảnh lên.");
    }
  }

  function selectFile(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setStreaming(false);
    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
    setResult(null);
    setResultImageUrl("");
    setCameraError("");
    setError("");
    event.target.value = "";
  }

  async function captureFrame() {
    const video = videoRef.current;
    if (!video || video.readyState < 2) return null;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.92));
  }

  async function analyze() {
    setError("");
    setResult(null);
    setResultImageUrl("");
    let image = selectedFile;
    if (streamRef.current) image = await captureFrame();
    if (!image) {
      setError("Bật camera hoặc tải ảnh lên trước khi nhận diện.");
      return;
    }

    setLoading(true);
    try {
      const response = await fetch("/api/predict", {
        method: "POST",
        headers: { "Content-Type": "application/octet-stream" },
        body: image,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Không thể chạy nhận diện.");
      setResultImageUrl(URL.createObjectURL(image));
      if (!data.found) {
        setResult({ found: false, message: data.message });
        setToast("Model chưa phát hiện vật thể.");
        return;
      }

      setResult(data);
      setCounts((current) => {
        const next = { ...current };
        for (const detection of data.detections) next[detection.category] = (next[detection.category] || 0) + 1;
        return next;
      });
      setHistory((current) => [
        ...data.detections.map((detection) => ({ ...detection, time: formatTime(new Date()), source: selectedFile ? "Ảnh tải lên" : "Camera" })),
        ...current,
      ].slice(0, 8));
      setToast(`Model phát hiện ${data.detections.length} vật thể.`);
    } catch (requestError) {
      setError(requestError.message || "Không kết nối được model. Hãy kiểm tra backend Docker.");
    } finally {
      setLoading(false);
    }
  }

  function clearHistory() {
    setHistory([]);
    setCounts({ recycle: 0, non_recyclable: 0, organic: 0, other: 0 });
  }

  const best = result?.found ? result.detections[0] : null;
  const confidence = best ? Math.round(best.confidence * 100) : 0;
  const today = new Intl.DateTimeFormat("vi-VN", { weekday: "long", day: "numeric", month: "long" }).format(new Date());

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="GreenLens trang chủ">
          <span className="brand-mark"><Icon name="leaf" size={21} /></span>
          <span>Green<span className="brand-accent">Lens</span></span>
        </a>
        <div className="topbar-right"><span className="model-status"><i /> YOLO26n · chạy cục bộ</span><div className="avatar">GL</div></div>
      </header>

      <main id="top" className="page-wrap">
        <section className="hero">
          <div>
            <p className="eyebrow">TRỢ LÝ PHÂN LOẠI RÁC</p>
            <h1>Nhận diện rác,<br /><span>sống xanh hơn.</span></h1>
            <p className="hero-subtitle">Đưa vật thể vào khung hình để nhận gợi ý phân loại ngay.</p>
          </div>
          <div className="date-pill"><Icon name="calendar" size={16} />{today}</div>
        </section>

        <section className="dashboard">
          <article className="panel camera-panel">
            <div className="panel-heading"><div><h2>Camera nhận diện</h2><p>Căn vật thể vào giữa khung hình</p></div><span className={`live-tag ${streaming ? "is-live" : ""}`}><i />{streaming ? "ĐANG QUAY" : "SẴN SÀNG"}</span></div>
            <div className="camera-stage">
              {resultImageUrl && <>
                <img className="camera-media result-media" src={resultImageUrl} alt="Ảnh kết quả nhận diện" />
                {result?.found && result.image_size?.length === 2 && <svg className="detection-overlay" viewBox={`0 0 ${result.image_size[0]} ${result.image_size[1]}`} preserveAspectRatio="xMidYMid meet" aria-label="Khung nhận diện">
                  {result.detections.map((detection, index) => {
                    const [x1, y1, x2, y2] = detection.box || [];
                    if (![x1, y1, x2, y2].every(Number.isFinite)) return null;
                    const color = detectionColors[detection.category] || detectionColors.other;
                    const label = `${detection.label} ${Math.round(detection.confidence * 100)}%`;
                    const fontSize = Math.max(14, Math.min(result.image_size[0], result.image_size[1]) * 0.035);
                    return <g key={`${detection.class_name}-${index}`}>
                      <rect x={x1} y={y1} width={Math.max(0, x2 - x1)} height={Math.max(0, y2 - y1)} fill={`${color}20`} stroke={color} strokeWidth={Math.max(3, fontSize / 7)} />
                      <text x={x1} y={Math.max(fontSize, y1 - 6)} fill={color} stroke="#14231a" strokeWidth={fontSize / 5} paintOrder="stroke" fontSize={fontSize} fontWeight="700">{label}</text>
                    </g>;
                  })}
                </svg>}
              </>}
              {!resultImageUrl && streaming && <video ref={videoRef} className="camera-media" autoPlay playsInline muted />}
              {!resultImageUrl && !streaming && previewUrl && <img className="camera-media" src={previewUrl} alt="Ảnh đã chọn để nhận diện" />}
              {!resultImageUrl && !streaming && !previewUrl && <div className="camera-placeholder"><span className="placeholder-icon"><Icon name="camera" size={26} /></span><strong>Camera đang chờ</strong><span>Bật camera hoặc tải ảnh lên để bắt đầu</span></div>}
              <span className="frame-corner top-left" /><span className="frame-corner bottom-right" />
              <span className="camera-hint">Ảnh đầu vào · 640 px</span>
              {streaming && <span className="camera-live"><i /> LIVE</span>}
            </div>
            {cameraError && <p className="inline-error">{cameraError}</p>}
            <div className="camera-actions">
              <button className={`button ${streaming ? "button-muted" : "button-green"}`} type="button" onClick={toggleCamera}><Icon name={streaming ? "close" : "camera"} />{streaming ? "Tắt camera" : "Bật camera"}</button>
              <button className="button button-outline" type="button" onClick={() => fileRef.current?.click()}><Icon name="upload" />Tải ảnh lên</button>
              <input ref={fileRef} className="visually-hidden" type="file" accept="image/*" onChange={selectFile} />
              <button className="button button-lime analyze-button" type="button" disabled={loading} onClick={analyze}><Icon name={loading ? "spark" : "scan"} />{loading ? "Đang nhận diện…" : "Phân tích vật thể"}</button>
            </div>
            {selectedFile && <p className="selected-file">Ảnh: <strong>{selectedFile.name}</strong></p>}
            {error && <p className="inline-error">{error}</p>}
            <div className="privacy-note"><Icon name="shield" size={15} />Ảnh được xử lý bằng model cục bộ trên máy chủ của bạn.</div>
          </article>

          <div className="side-column">
            <article className="panel result-panel">
              <div className="panel-heading result-heading"><div><h2>Kết quả nhận diện</h2></div><span className={`result-state ${best ? "state-success" : ""}`}>{loading ? "Đang chạy model" : best ? `${result.detections.length} vật thể` : result ? "Không phát hiện" : "Chưa phân tích"}</span></div>
              {!best && <div className="result-placeholder"><Icon name="spark" size={25} /><p>{result?.message || "Kết quả và hướng dẫn xử lý sẽ hiển thị ở đây."}</p></div>}
              {best && <div className="result-content">
                <div className="prediction-title"><span className={`category-icon category-${best.category}`}><Icon name={categoryIcon(best.category)} size={21} /></span><div><small>Loại rác được dự đoán</small><strong>{best.label}</strong></div></div>
                <div className="confidence-block"><div className="confidence-label"><span>Độ tin cậy</span><strong>{confidence}%</strong></div><div className="meter"><span style={{ width: `${confidence}%` }} /></div></div>
                <div className="advice"><Icon name="check" size={17} /><p><strong>Gợi ý xử lý:</strong> {best.advice}{confidence < 50 && " Độ tin cậy thấp, hãy thử chụp lại rõ hơn."}</p></div>
                {result.detections.length > 1 && <div className="extra-detections">Còn {result.detections.length - 1} vật thể khác trong khung hình.</div>}
              </div>}
            </article>

            <article className="panel stats-panel">
              <div className="stats-heading"><h2>Thống kê phiên này</h2><span>{history.length} lượt</span></div>
              <div className="stats-grid">
                <div className="stat-box"><span><i className="dot-recycle" />Tái chế</span><strong>{String(counts.recycle).padStart(2, "0")}</strong></div>
                <div className="stat-box"><span><i className="dot-non-recyclable" />Không tái chế được</span><strong>{String(counts.non_recyclable).padStart(2, "0")}</strong></div>
                <div className="stat-box"><span><i className="dot-organic" />Hữu cơ</span><strong>{String(counts.organic).padStart(2, "0")}</strong></div>
                <div className="stat-box"><span><i className="dot-other" />Khác</span><strong>{String(counts.other).padStart(2, "0")}</strong></div>
              </div>
            </article>

            <article className="panel history-panel">
              <div className="history-heading"><h2>Lịch sử nhận diện</h2><button type="button" onClick={clearHistory} disabled={!history.length}>Xóa lịch sử</button></div>
              <div className="history-list">
                {!history.length && <p className="history-empty">Các vật thể đã nhận diện sẽ xuất hiện ở đây.</p>}
                {history.map((item, index) => <div className="history-row" key={`${item.time}-${index}`}><span className={`history-icon category-${item.category}`}><Icon name={categoryIcon(item.category)} size={16} /></span><div className="history-detail"><strong>{item.class_name} · {item.label}</strong><small>{item.time} · {item.source}</small></div><b>{Math.round(item.confidence * 100)}%</b></div>)}
              </div>
            </article>
          </div>
        </section>

        <section className="feature-strip"><div className="feature-symbol"><Icon name="spark" size={20} /></div><div className="feature-copy"><strong>Có thể mở rộng thêm</strong><span>Bản đồ điểm thu gom · Thống kê theo tuần · Nhắc chụp lại khi độ tin cậy thấp</span></div><span className="feature-label">GỢI Ý TÍNH NĂNG</span></section>
      </main>

      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  );
}

export default App;
