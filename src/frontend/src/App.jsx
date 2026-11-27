import { useEffect, useRef, useState } from "react";
import {
  AdminPortal,
  AppHeader,
  DashboardPage,
  HistoryPage,
  AuthPage,
  GuidePage,
  Icon,
  PageHeading,
  RecognitionPanel,
  ResultCard,
  SessionCard,
  Sidebar,
  StatCard,
  Toast,
} from "./components.jsx";

function waitForMedia(video, eventName) {
  return new Promise((resolve, reject) => {
    const cleanup = () => {
      video.removeEventListener(eventName, onReady);
      video.removeEventListener("error", onError);
    };
    const onReady = () => { cleanup(); resolve(); };
    const onError = () => { cleanup(); reject(new Error("Không đọc được video này. Hãy chọn video định dạng phổ biến như MP4 hoặc WebM.")); };
    video.addEventListener(eventName, onReady, { once: true });
    video.addEventListener("error", onError, { once: true });
  });
}

function App() {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const liveTimerRef = useRef(null);
  const fileRef = useRef(null);
  const videoFileRef = useRef(null);
  const [mode, setMode] = useState("image");
  const [streaming, setStreaming] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [selectedVideo, setSelectedVideo] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [videoUrl, setVideoUrl] = useState("");
  const [resultImageUrl, setResultImageUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [videoProgress, setVideoProgress] = useState(null);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [counts, setCounts] = useState({ recycle: 0, non_recyclable: 0, organic: 0, other: 0 });
  const [toast, setToast] = useState("");
  const [cameraError, setCameraError] = useState("");
  const [page, setPage] = useState(() => ["dashboard", "recognition", "history", "guide"].includes(window.location.hash.slice(1)) ? window.location.hash.slice(1) : "dashboard");
  const [adminPortal, setAdminPortal] = useState(false);
  const [authUser, setAuthUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);

  useEffect(() => {
    let active = true;
    fetch("/api/auth/me", { credentials: "same-origin" })
      .then((response) => response.ok ? response.json() : null)
      .then((data) => { if (active) setAuthUser(data?.user || null); })
      .catch(() => { if (active) setAuthUser(null); })
      .finally(() => { if (active) setAuthLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const syncPage = () => { const next = window.location.hash.slice(1); if (["dashboard", "recognition", "history", "guide"].includes(next)) setPage(next); };
    window.addEventListener("hashchange", syncPage);
    window.addEventListener("popstate", syncPage);
    return () => {
      window.removeEventListener("hashchange", syncPage);
      window.removeEventListener("popstate", syncPage);
    };
  }, []);

  function navigate(event, nextPage) {
    event.preventDefault();
    const hash = `#${nextPage}`;
    if (window.location.hash !== hash) window.history.pushState({}, "", hash);
    setPage(nextPage);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function logout() {
    try { await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" }); }
    finally { setAuthUser(null); }
  }

  useEffect(() => () => {
    if (liveTimerRef.current) window.clearTimeout(liveTimerRef.current);
    streamRef.current?.getTracks().forEach((track) => track.stop());
  }, []);
  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);
  useEffect(() => () => { if (videoUrl) URL.revokeObjectURL(videoUrl); }, [videoUrl]);
  useEffect(() => () => { if (resultImageUrl) URL.revokeObjectURL(resultImageUrl); }, [resultImageUrl]);
  useEffect(() => {
    if (!toast) return undefined;
    const timer = window.setTimeout(() => setToast(""), 2800);
    return () => window.clearTimeout(timer);
  }, [toast]);
  useEffect(() => {
    if (videoRef.current && streamRef.current) videoRef.current.srcObject = streamRef.current;
  }, [streaming, mode]);

  async function requestPrediction(image) {
    const response = await fetch("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream" },
      body: image,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Không thể chạy nhận diện.");
    return data;
  }

  function recordDetections(detections) {
    if (!detections.length) return;
    setCounts((current) => {
      const next = { ...current };
      for (const detection of detections) next[detection.category] = (next[detection.category] || 0) + 1;
      return next;
    });
  }

  async function captureFrame() {
    const video = videoRef.current;
    if (!video || video.readyState < 2 || !video.videoWidth || !video.videoHeight) return null;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
  }

  async function analyzeImage(image) {
    setError("");
    setLoading(true);
    try {
      const data = await requestPrediction(image);
      setResult(data);
      setResultImageUrl(URL.createObjectURL(image));
      if (data.found) {
        recordDetections(data.detections);
        setToast(`Model phát hiện ${data.detections.length} vật thể.`);
      } else {
        setToast("Model chưa phát hiện vật thể.");
      }
      return data;
    } catch (requestError) {
      setError(requestError.message || "Không kết nối được model. Hãy kiểm tra backend Docker.");
      return null;
    } finally {
      setLoading(false);
    }
  }

  function stopCamera() {
    if (liveTimerRef.current) window.clearTimeout(liveTimerRef.current);
    liveTimerRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setStreaming(false);
  }

  async function toggleCamera() {
    if (streamRef.current) {
      stopCamera();
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraError("Trình duyệt này không hỗ trợ camera. Hãy mở ứng dụng qua HTTPS hoặc localhost.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
      streamRef.current = stream;
      setResult(null);
      setResultImageUrl("");
      setError("");
      setCameraError("");
      setStreaming(true);

      const recognizeNextFrame = async () => {
        if (streamRef.current !== stream) return;
        const frame = await captureFrame();
        if (frame) await analyzeImage(frame);
        if (streamRef.current === stream) liveTimerRef.current = window.setTimeout(recognizeNextFrame, 2200);
      };
      liveTimerRef.current = window.setTimeout(recognizeNextFrame, 900);
    } catch {
      setCameraError("Không mở được camera. Hãy cấp quyền truy cập camera trên trình duyệt.");
    }
  }

  function selectFile(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (streamRef.current) stopCamera();
    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
    setResult(null);
    setResultImageUrl("");
    setCameraError("");
    setError("");
    event.target.value = "";
  }

  function selectVideo(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (streamRef.current) stopCamera();
    setSelectedVideo(file);
    setVideoUrl(URL.createObjectURL(file));
    setResult(null);
    setResultImageUrl("");
    setVideoProgress(null);
    setError("");
    event.target.value = "";
  }

  function changeMode(nextMode) {
    if (nextMode === mode) return;
    if (streamRef.current && nextMode !== "live") stopCamera();
    setMode(nextMode);
    setResult(null);
    setResultImageUrl("");
    setError("");
    setCameraError("");
    setVideoProgress(null);
  }

  async function analyzeVideo() {
    if (!videoUrl || !selectedVideo) return;
    setError("");
    setResult(null);
    setResultImageUrl("");
    setLoading(true);
    setVideoProgress({ current: 0, total: 0, percent: 0 });
    let frameVideo;
    try {
      frameVideo = document.createElement("video");
      frameVideo.preload = "auto";
      frameVideo.muted = true;
      frameVideo.playsInline = true;
      const metadata = waitForMedia(frameVideo, "loadedmetadata");
      frameVideo.src = videoUrl;
      frameVideo.load();
      await metadata;
      if (!Number.isFinite(frameVideo.duration) || frameVideo.duration <= 0) throw new Error("Không xác định được thời lượng video.");

      const frameCount = Math.min(8, Math.max(1, Math.ceil(frameVideo.duration / 3)));
      const times = Array.from({ length: frameCount }, (_, index) => frameCount === 1
        ? 0
        : Math.min(frameVideo.duration - 0.05, (frameVideo.duration * index) / (frameCount - 1)));
      const detections = [];
      let lastResult = null;
      let lastFrame = null;
      setVideoProgress({ current: 0, total: frameCount, percent: 0 });

      for (let index = 0; index < times.length; index += 1) {
        const time = times[index];
        if (index === 0 && frameVideo.readyState < 2) {
          await waitForMedia(frameVideo, "loadeddata");
        } else if (Math.abs(frameVideo.currentTime - time) > 0.01) {
          const seeked = waitForMedia(frameVideo, "seeked");
          frameVideo.currentTime = time;
          await seeked;
        }
        const canvas = document.createElement("canvas");
        canvas.width = frameVideo.videoWidth;
        canvas.height = frameVideo.videoHeight;
        if (!canvas.width || !canvas.height) throw new Error("Video không có khung hình hợp lệ.");
        canvas.getContext("2d").drawImage(frameVideo, 0, 0);
        const frame = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.88));
        if (!frame) throw new Error("Không thể trích xuất khung hình từ video.");

        const data = await requestPrediction(frame);
        lastResult = data;
        lastFrame = frame;
        if (data.found) detections.push(...data.detections);
        setVideoProgress({ current: index + 1, total: frameCount, percent: Math.round(((index + 1) / frameCount) * 100) });
      }

      const finalResult = detections.length ? { ...lastResult, found: true, detections: detections.slice(-lastResult.detections.length) } : lastResult;
      setResult(finalResult);
      setResultImageUrl(lastFrame ? URL.createObjectURL(lastFrame) : "");
      recordDetections(detections);
      setToast(`Đã phân tích ${frameCount} khung hình, phát hiện ${detections.length} lượt.`);
    } catch (analysisError) {
      setError(analysisError.message || "Không thể phân tích video này.");
    } finally {
      if (frameVideo) {
        frameVideo.pause();
        frameVideo.removeAttribute("src");
        frameVideo.load();
      }
      setLoading(false);
    }
  }

  function analyze() {
    if (mode === "image") return selectedFile ? analyzeImage(selectedFile) : undefined;
    if (mode === "video") return analyzeVideo();
    return undefined;
  }

  const best = result?.found ? result.detections[0] : null;
  const total = Object.values(counts).reduce((sum, count) => sum + count, 0);
  const confidence = best ? Math.round(best.confidence * 100) : 0;
  const recycleRate = total ? Math.round((counts.recycle / total) * 100) : 0;
  const today = new Intl.DateTimeFormat("vi-VN", { weekday: "long", day: "numeric", month: "long" }).format(new Date());

  if (authLoading) return <div className="auth-loading" role="status">Đang kiểm tra phiên đăng nhập…</div>;
  if (!authUser) return <AuthPage onAuthenticated={setAuthUser} />;
  if (adminPortal) return <AdminPortal onExit={() => setAdminPortal(false)} />;

  return <div className="app-shell">
    <Sidebar page={page} onNavigate={navigate} />
    <div className="app-content">
      <AppHeader page={page} user={authUser} onLogout={logout} onAdmin={() => setAdminPortal(true)} />
      <main className="main-area">
        {page === "guide" ? <GuidePage /> : page === "dashboard" ? <DashboardPage total={total} recycleRate={recycleRate} confidence={confidence} onNavigate={(next) => { window.history.pushState({}, "", `#${next}`); setPage(next); }} /> : page === "history" ? <HistoryPage total={total} counts={counts} /> : <>
          <PageHeading today={today} />
          <section className="cards user-stats" aria-label="Thống kê phiên nhận diện">
            <StatCard label="Vật thể đã nhận diện" value={total} foot="Tổng lượt qua ảnh, video và camera" icon="recycle" />
            <StatCard label="Tỷ lệ tái chế" value={`${recycleRate}%`} foot="Trong phiên hiện tại" icon="image" />
            <StatCard label="Độ tin cậy gần nhất" value={`${confidence}%`} foot="Theo kết quả vừa nhận diện" icon="spark" />
          </section>
          <section className="cards user-grid">
            <RecognitionPanel mode={mode} onModeChange={changeMode} videoRef={videoRef} fileRef={fileRef} videoFileRef={videoFileRef} streaming={streaming} previewUrl={previewUrl} videoUrl={videoUrl} resultImageUrl={resultImageUrl} result={result} selectedFile={selectedFile} selectedVideo={selectedVideo} loading={loading} modeLocked={loading && mode === "video"} videoProgress={videoProgress} error={error} cameraError={cameraError} toggleCamera={toggleCamera} selectFile={selectFile} selectVideo={selectVideo} analyze={analyze} />
            <div className="right-stack"><ResultCard best={best} result={result} loading={loading} confidence={confidence} videoProgress={videoProgress} /><SessionCard counts={counts} total={total} /></div>
          </section>
        </>}
      </main>
    </div>
    <Toast>{toast}</Toast>
  </div>;
}

export default App;
