import { useState, useRef, useCallback, useEffect } from "react";
import axios from "axios";

function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function ClipCard({ clip, jobId }) {
  const [showPreview, setShowPreview] = useState(false);
  const [showDetails, setShowDetails] = useState(false);

  const videoUrl = `/api/download/${jobId}/${clip.index}`;

  const download = async () => {
    const { data } = await axios.get(videoUrl, { responseType: "blob" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(data);
    a.download = `${clip.title.replace(/[^a-zA-Z0-9 _-]/g, "_")}.mp4`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <div className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900 transition hover:border-zinc-700">
      {/* Preview */}
      {showPreview && (
        <div className="relative bg-black">
          <video
            src={videoUrl}
            controls
            className="mx-auto max-h-[60vh] w-full"
          />
        </div>
      )}

      {/* Main row */}
      <div className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
        <div className="flex items-center gap-3 sm:gap-4">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-violet-500/10 text-sm font-bold text-violet-400 sm:h-10 sm:w-10">
            {clip.index + 1}
          </div>
          <div className="min-w-0">
            <h3 className="truncate font-semibold text-zinc-200">
              {clip.title}
            </h3>
            <p className="text-sm text-zinc-500">
              {clip.duration}s
              {clip.segments?.length > 1 && (
                <span className="ml-1.5 text-violet-400/70">
                  · {clip.segments.length} parts stitched
                </span>
              )}
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowPreview((v) => !v)}
            className="flex items-center gap-1.5 rounded-lg bg-zinc-800 px-3 py-2 text-sm font-medium transition hover:bg-zinc-700"
          >
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              {showPreview ? (
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13.875 18.825A10.05 10.05 0 0112 19c-5 0-9.27-3.11-11-7.5a11.72 11.72 0 013.168-4.477M6.343 6.343A9.972 9.972 0 0112 5c5 0 9.27 3.11 11 7.5a11.72 11.72 0 01-4.168 4.477M6.343 6.343L3 3m3.343 3.343l2.829 2.829M17.657 17.657L21 21m-3.343-3.343l-2.829-2.829M17.657 17.657A9.972 9.972 0 0112 19c-5 0-9.27-3.11-11-7.5a11.72 11.72 0 013.168-4.477"
                />
              ) : (
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"
                />
              )}
            </svg>
            <span className="hidden xs:inline">
              {showPreview ? "Hide" : "Preview"}
            </span>
          </button>

          <button
            onClick={() => setShowDetails((v) => !v)}
            className="flex items-center gap-1.5 rounded-lg bg-zinc-800 px-3 py-2 text-sm font-medium transition hover:bg-zinc-700"
          >
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M13 16h-1v-4h-1m1-4h.01M12 2a10 10 0 100 20 10 10 0 000-20z"
              />
            </svg>
            <span className="hidden xs:inline">Details</span>
          </button>

          <button
            onClick={download}
            className="flex items-center gap-1.5 rounded-lg bg-violet-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-violet-500"
          >
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
              />
            </svg>
            <span className="hidden xs:inline">Download</span>
          </button>
        </div>
      </div>

      {/* Expandable details */}
      {showDetails && (
        <div className="border-t border-zinc-800 bg-zinc-950/50 px-4 py-3 sm:px-5">
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-zinc-500">
            Source timestamps
          </p>
          <div className="space-y-1.5">
            {(clip.segments || []).map((seg, i) => (
              <div
                key={i}
                className="flex items-center gap-2 text-sm text-zinc-400"
              >
                {clip.segments.length > 1 && (
                  <span className="w-5 text-xs text-zinc-600">#{i + 1}</span>
                )}
                <span className="rounded bg-zinc-800 px-1.5 py-0.5 font-mono text-xs text-zinc-300">
                  {formatTime(seg.start)}
                </span>
                <span className="text-zinc-600">→</span>
                <span className="rounded bg-zinc-800 px-1.5 py-0.5 font-mono text-xs text-zinc-300">
                  {formatTime(seg.end)}
                </span>
                <span className="text-zinc-600">
                  ({(seg.end - seg.start).toFixed(1)}s)
                </span>
              </div>
            ))}
            {clip.segments?.length > 1 && (
              <p className="mt-1 text-xs text-violet-400/60">
                {clip.segments.length} sections stitched into one clip
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [phase, setPhase] = useState("idle");
  const [file, setFile] = useState(null);
  const [clipCount, setClipCount] = useState(3);
  const [progress, setProgress] = useState(0);
  const [step, setStep] = useState("");
  const [clips, setClips] = useState([]);
  const [note, setNote] = useState(null);
  const [error, setError] = useState("");
  const [jobId, setJobId] = useState(null);
  const [dragOver, setDragOver] = useState(false);

  const inputRef = useRef(null);
  const pollRef = useRef(null);

  useEffect(() => () => clearInterval(pollRef.current), []);

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f?.type.startsWith("video/")) setFile(f);
  }, []);

  const startPolling = useCallback((id) => {
    pollRef.current = setInterval(async () => {
      try {
        const { data } = await axios.get(`/api/status/${id}`);
        setStep(data.step);
        setProgress(data.progress);
        if (data.status === "complete") {
          clearInterval(pollRef.current);
          setClips(data.clips);
          setNote(data.note);
          setPhase("complete");
        } else if (data.status === "error") {
          clearInterval(pollRef.current);
          setError(data.error || "Processing failed");
          setPhase("error");
        }
      } catch {
        clearInterval(pollRef.current);
        setError("Lost connection to server");
        setPhase("error");
      }
    }, 2000);
  }, []);

  const submit = async () => {
    if (!file) return;
    setPhase("uploading");
    setProgress(0);
    setStep("Uploading video…");

    try {
      const fd = new FormData();
      fd.append("video", file);
      fd.append("clip_count", clipCount);

      const { data } = await axios.post("/api/upload", fd, {
        onUploadProgress: (e) =>
          setProgress(Math.round((e.loaded / e.total) * 100)),
      });

      setJobId(data.job_id);
      setPhase("processing");
      setProgress(0);
      startPolling(data.job_id);
    } catch (err) {
      setError(err.response?.data?.detail || "Upload failed");
      setPhase("error");
    }
  };

  const reset = async () => {
    clearInterval(pollRef.current);
    if (jobId) {
      axios.delete(`/api/cleanup/${jobId}`).catch(() => {});
    }
    setPhase("idle");
    setFile(null);
    setClipCount(3);
    setProgress(0);
    setStep("");
    setClips([]);
    setNote(null);
    setError("");
    setJobId(null);
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <header className="border-b border-zinc-800/60 px-4 py-3 sm:px-6 sm:py-4">
        <div className="mx-auto flex max-w-4xl items-center justify-between">
          <h1 className="text-lg font-bold tracking-tight sm:text-xl">
            <span className="text-violet-400">trimmer</span>
            <span className="ml-1.5 text-xs font-normal text-zinc-500 sm:ml-2 sm:text-sm">
              AI Video Clipper
            </span>
          </h1>
          {phase !== "idle" && (
            <button
              onClick={reset}
              className="text-sm text-zinc-400 transition hover:text-zinc-200"
            >
              Start Over
            </button>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-4 py-8 sm:px-6 sm:py-12">
        {/* ── IDLE ── */}
        {phase === "idle" && (
          <div className="space-y-8 sm:space-y-10">
            <div className="space-y-2 text-center">
              <h2 className="text-2xl font-bold sm:text-3xl">
                Create Instagram Clips
              </h2>
              <p className="text-sm text-zinc-400 sm:text-base">
                Upload a video and AI will find the best moments for you
              </p>
            </div>

            {/* Drop zone */}
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              onClick={() => inputRef.current?.click()}
              className={`cursor-pointer rounded-2xl border-2 border-dashed p-8 text-center transition-all sm:p-14 ${
                dragOver
                  ? "border-violet-400 bg-violet-400/5"
                  : file
                    ? "border-emerald-500/50 bg-emerald-500/5"
                    : "border-zinc-700 bg-zinc-900/50 hover:border-zinc-500"
              }`}
            >
              <input
                ref={inputRef}
                type="file"
                accept="video/*"
                onChange={(e) => e.target.files[0] && setFile(e.target.files[0])}
                className="hidden"
              />
              {file ? (
                <div className="space-y-2">
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/10">
                    <svg
                      className="h-6 w-6 text-emerald-400"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                  </div>
                  <p className="truncate font-medium text-zinc-200">
                    {file.name}
                  </p>
                  <p className="text-sm text-zinc-500">
                    {(file.size / 1024 / 1024).toFixed(1)} MB
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-zinc-800">
                    <svg
                      className="h-6 w-6 text-zinc-400"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                      />
                    </svg>
                  </div>
                  <p className="text-zinc-300">
                    Drop your video here or click to browse
                  </p>
                  <p className="text-sm text-zinc-600">MP4, MOV, AVI, WebM</p>
                </div>
              )}
            </div>

            {/* Clip count */}
            <div className="flex items-center justify-center gap-4 sm:gap-6">
              <label className="text-sm text-zinc-400">Up to clips</label>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setClipCount((c) => Math.max(1, c - 1))}
                  className="flex h-9 w-9 items-center justify-center rounded-lg bg-zinc-800 transition hover:bg-zinc-700"
                >
                  −
                </button>
                <span className="w-8 text-center text-2xl font-bold">
                  {clipCount}
                </span>
                <button
                  onClick={() => setClipCount((c) => Math.min(10, c + 1))}
                  className="flex h-9 w-9 items-center justify-center rounded-lg bg-zinc-800 transition hover:bg-zinc-700"
                >
                  +
                </button>
              </div>
            </div>

            <div className="text-center">
              <button
                onClick={submit}
                disabled={!file}
                className={`w-full rounded-xl px-8 py-3 text-sm font-semibold transition-all sm:w-auto ${
                  file
                    ? "bg-violet-600 text-white shadow-lg shadow-violet-600/20 hover:bg-violet-500"
                    : "cursor-not-allowed bg-zinc-800 text-zinc-500"
                }`}
              >
                Generate Clips
              </button>
            </div>
          </div>
        )}

        {/* ── UPLOADING / PROCESSING ── */}
        {(phase === "uploading" || phase === "processing") && (
          <div className="mx-auto max-w-md space-y-8 text-center">
            <div className="space-y-2">
              <h2 className="text-xl font-bold sm:text-2xl">
                {phase === "uploading" ? "Uploading…" : "Processing…"}
              </h2>
              <p className="text-sm text-zinc-400 sm:text-base">{step}</p>
            </div>

            <div className="space-y-2">
              <div className="h-2 overflow-hidden rounded-full bg-zinc-800">
                <div
                  className="h-full rounded-full bg-violet-500 transition-all duration-500 ease-out"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <p className="text-sm text-zinc-500">{progress}%</p>
            </div>

            <div className="flex justify-center">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-violet-400 border-t-transparent" />
            </div>

            <p className="text-xs text-zinc-600">
              This may take a few minutes depending on video length
            </p>
          </div>
        )}

        {/* ── COMPLETE ── */}
        {phase === "complete" && (
          <div className="space-y-6 sm:space-y-8">
            <div className="space-y-3 text-center">
              <h2 className="text-xl font-bold sm:text-2xl">
                Your Clips Are Ready
              </h2>
              <p className="text-sm text-zinc-400 sm:text-base">
                {clips.length} clip{clips.length !== 1 && "s"} generated
              </p>
              {note && (
                <p className="mx-auto max-w-lg rounded-lg border border-amber-500/20 bg-amber-500/5 px-4 py-2.5 text-sm text-amber-300/90">
                  {note}
                </p>
              )}
            </div>

            <div className="grid gap-4">
              {clips.map((clip) => (
                <ClipCard key={clip.index} clip={clip} jobId={jobId} />
              ))}
            </div>
          </div>
        )}

        {/* ── ERROR ── */}
        {phase === "error" && (
          <div className="mx-auto max-w-md space-y-6 text-center">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-red-500/10">
              <svg
                className="h-8 w-8 text-red-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </div>
            <div className="space-y-2">
              <h2 className="text-xl font-bold sm:text-2xl">
                Something went wrong
              </h2>
              <p className="text-sm text-zinc-400 sm:text-base">{error}</p>
            </div>
            <button
              onClick={reset}
              className="rounded-xl bg-zinc-800 px-6 py-2.5 text-sm font-medium transition hover:bg-zinc-700"
            >
              Try Again
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
