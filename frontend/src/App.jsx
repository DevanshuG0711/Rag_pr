import { useState } from "react";
import axios from "axios";

function App() {
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [copiedKey, setCopiedKey] = useState("");
  const [queryHistory, setQueryHistory] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("");

  const answerText = response?.answer || "";
  const flowHeader = "Flow Explanation:";
  const flowHeaderIndex = answerText.toLowerCase().indexOf(flowHeader.toLowerCase());

  const hasFlowSection = flowHeaderIndex !== -1;
  let mainAnswer = answerText.trim();
  let flowLines = [];

  if (hasFlowSection) {
    const beforeFlow = answerText.slice(0, flowHeaderIndex).trim();
    const afterFlow = answerText.slice(flowHeaderIndex + flowHeader.length).trim();

    let flowBlock = afterFlow;
    let trailingAnswer = "";
    const sectionBreak = afterFlow.search(/\n\s*\n/);

    if (sectionBreak !== -1) {
      flowBlock = afterFlow.slice(0, sectionBreak).trim();
      trailingAnswer = afterFlow.slice(sectionBreak).trim();
    }

    flowLines = flowBlock
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);

    mainAnswer = [beforeFlow, trailingAnswer].filter(Boolean).join("\n\n");
  }

  const copyToClipboard = async (text, key) => {
    if (!text) return;

    try {
      await navigator.clipboard.writeText(text);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(""), 1400);
    } catch (err) {
      console.error("Copy failed", err);
    }
  };

  const handleFileSelection = (file) => {
    if (!file) return;

    const allowedExtensions = [".py", ".txt", ".pdf"];
    const lowerName = file.name.toLowerCase();
    const isAllowed = allowedExtensions.some((ext) => lowerName.endsWith(ext));

    if (!isAllowed) {
      setUploadStatus("Please select a .py, .txt, or .pdf file.");
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);
    setUploadStatus("");
  };

  const handleUpload = async () => {
    if (!selectedFile || uploading) return;

    try {
      setUploading(true);
      setUploadStatus("");

      const formData = new FormData();
      formData.append("file", selectedFile);

      await axios.post("http://127.0.0.1:8000/api/ingest", formData);
      setUploadStatus("File uploaded successfully.");
    } catch (err) {
      console.error(err);
      setUploadStatus("Upload failed. Please try again.");
    } finally {
      setUploading(false);
    }
  };

  const handleSubmit = async () => {
    const trimmedQuery = query.trim();
    if (!trimmedQuery) return;

    try {
      setLoading(true);
      const res = await axios.post("http://127.0.0.1:8000/api/query", {
        query: trimmedQuery,
        top_k: 5,
      });
      setResponse(res.data);
      setQueryHistory((prev) => {
        const deduped = prev.filter((item) => item !== trimmedQuery);
        return [trimmedQuery, ...deduped].slice(0, 5);
      });
    } catch (err) {
      console.error(err);
      alert("Error fetching response");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-black via-slate-950 to-blue-950 text-white flex flex-col items-center justify-center px-6 py-10 md:px-8">

      <h1 className="mb-8 text-center text-3xl font-semibold tracking-tight text-slate-100 md:mb-10 md:text-5xl">
        🚀 Codebase Intelligence Engine
      </h1>

      <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 lg:flex-row lg:items-start">
        <aside className="w-full rounded-xl border border-white/10 bg-slate-900/55 p-4 shadow-[0_10px_24px_rgba(0,0,0,0.24)] lg:sticky lg:top-8 lg:w-64">
          <h2 className="mb-3 text-sm font-semibold text-slate-200">Recent Queries</h2>

          {queryHistory.length === 0 ? (
            <p className="text-xs leading-6 text-slate-400">Your last 5 queries will appear here.</p>
          ) : (
            <div className="space-y-2">
              {queryHistory.map((item, index) => {
                const isActive = item === query.trim();
                return (
                  <button
                    key={`${item}-${index}`}
                    onClick={() => setQuery(item)}
                    className={`w-full truncate rounded-lg px-3 py-2 text-left text-xs transition ${
                      isActive
                        ? "border border-cyan-300/45 bg-cyan-400/12 text-cyan-100"
                        : "border border-white/10 bg-slate-900/60 text-slate-300 hover:bg-slate-800/70"
                    }`}
                  >
                    {item}
                  </button>
                );
              })}
            </div>
          )}
        </aside>

        <div className="w-full lg:flex-1">
          {/* Upload Section */}
          <div className="mx-auto mb-5 w-full max-w-2xl rounded-xl border border-white/10 bg-slate-900/55 p-4 shadow-[0_10px_24px_rgba(0,0,0,0.24)] md:mb-6 md:p-5">
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setIsDragging(false);
                handleFileSelection(e.dataTransfer.files?.[0]);
              }}
              className={`rounded-xl border-2 border-dashed p-5 text-center transition ${
                isDragging
                  ? "border-cyan-300/60 bg-cyan-400/10"
                  : "border-white/20 bg-slate-900/45"
              }`}
            >
              <p className="text-sm text-slate-200">Drag and drop a file here, or select one</p>
              <p className="mt-1 text-xs text-slate-400">Supported: .py, .txt, .pdf</p>

              <div className="mt-4 flex flex-col items-center justify-center gap-3 sm:flex-row">
                <label className="cursor-pointer rounded-lg border border-white/20 bg-slate-800/70 px-3 py-2 text-xs text-slate-200 transition hover:bg-slate-700/70">
                  Choose File
                  <input
                    type="file"
                    accept=".py,.txt,.pdf"
                    onChange={(e) => handleFileSelection(e.target.files?.[0])}
                    className="hidden"
                  />
                </label>

                <button
                  onClick={handleUpload}
                  disabled={!selectedFile || uploading}
                  className="rounded-lg bg-cyan-500 px-3 py-2 text-xs font-medium text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-55"
                >
                  {uploading ? "Uploading..." : "Upload"}
                </button>
              </div>

              {selectedFile && (
                <p className="mt-3 truncate text-xs text-slate-300">Selected: {selectedFile.name}</p>
              )}

              {uploadStatus && (
                <p
                  className={`mt-3 text-xs ${
                    uploadStatus.toLowerCase().includes("success")
                      ? "text-emerald-300"
                      : "text-rose-300"
                  }`}
                >
                  {uploadStatus}
                </p>
              )}
            </div>
          </div>

          {/* Input Section */}
          <div className="mx-auto flex w-full max-w-2xl gap-3 md:gap-4">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask anything about your codebase..."
              className="flex-1 rounded-2xl border border-white/15 bg-slate-900/70 px-4 py-3 text-sm text-slate-100 shadow-[0_6px_20px_rgba(0,0,0,0.25)] outline-none transition duration-300 placeholder:text-slate-400 focus:border-cyan-300/45 focus:ring-4 focus:ring-cyan-400/25"
            />
            <button
              onClick={handleSubmit}
              className="rounded-2xl bg-cyan-500 px-6 py-3 text-sm font-medium text-slate-950 transition-all duration-300 hover:-translate-y-0.5 hover:bg-cyan-400 hover:shadow-[0_12px_28px_rgba(34,211,238,0.32)] active:translate-y-0"
            >
              {loading ? "..." : "Ask"}
            </button>
          </div>

          {loading && (
            <div className="mx-auto mt-8 w-full max-w-2xl animate-[fadeIn_0.25s_ease-out] rounded-xl border border-white/10 bg-slate-900/65 p-6 shadow-[0_12px_32px_rgba(0,0,0,0.28)] md:p-7">
              <p className="mb-4 text-sm font-medium text-cyan-100">Analyzing codebase...</p>
              <div className="space-y-3 animate-pulse">
                <div className="h-4 w-1/3 rounded bg-slate-700/70" />
                <div className="h-3.5 w-full rounded bg-slate-700/60" />
                <div className="h-3.5 w-11/12 rounded bg-slate-700/60" />
                <div className="h-3.5 w-4/5 rounded bg-slate-700/60" />
              </div>
            </div>
          )}

          {/* Answer */}
          {response && (
            <div className="mx-auto w-full max-w-2xl animate-[fadeIn_0.35s_ease-out]">
          {mainAnswer && (
            <div className="mt-8 w-full rounded-xl border border-white/10 bg-slate-800/70 p-6 shadow-[0_12px_32px_rgba(0,0,0,0.32)] transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_16px_38px_rgba(0,0,0,0.38)] md:mt-10 md:p-7">
              <h2 className="mb-4 text-lg font-semibold text-slate-100 md:text-xl">Answer</h2>
              <p className="whitespace-pre-wrap text-sm leading-7 text-slate-200 md:text-base md:leading-8">
                {mainAnswer}
              </p>
            </div>
          )}

          {hasFlowSection && flowLines.length > 0 && (
            <div className={`${mainAnswer ? "mt-5" : "mt-8 md:mt-10"} w-full rounded-xl border border-blue-400/45 bg-slate-900/70 p-6 shadow-[0_12px_32px_rgba(37,99,235,0.18)] transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_16px_38px_rgba(37,99,235,0.24)] md:p-7`}>
              <div className="mb-4 flex items-center justify-between gap-3">
                <h3 className="text-base font-semibold text-blue-200 md:text-lg">Flow Explanation</h3>
                <button
                  onClick={() => copyToClipboard(flowLines.join("\n"), "flow")}
                  className="rounded-md border border-blue-300/40 px-2.5 py-1 text-xs text-blue-100 transition hover:bg-blue-400/15"
                >
                  {copiedKey === "flow" ? "Copied" : "Copy"}
                </button>
              </div>
              <div className="space-y-2 font-mono text-sm leading-7 text-blue-100">
                {flowLines.map((line, index) => (
                  <p key={`${line}-${index}`}>{line}</p>
                ))}
              </div>
            </div>
          )}

          {Array.isArray(response?.retrieved_chunks) && response.retrieved_chunks.length > 0 && (
            <div className="mt-6 w-full rounded-xl border border-white/10 bg-slate-900/60 p-6 shadow-[0_12px_32px_rgba(0,0,0,0.3)] md:p-7">
              <h3 className="mb-4 text-base font-semibold text-slate-100 md:text-lg">Relevant Code Chunks</h3>

              <div className="space-y-4">
                {response.retrieved_chunks.map((chunk, index) => (
                  <div
                    key={chunk.id || `${chunk.file_name || "chunk"}-${index}`}
                    className="rounded-xl border border-white/10 bg-slate-900/70 p-4 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_14px_30px_rgba(15,23,42,0.55)]"
                  >
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <p className="truncate text-sm font-medium text-slate-100">
                        {chunk.file_name || "Unknown file"}
                      </p>
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-slate-300">
                          score: {Number(chunk.score || 0).toFixed(2)}
                        </span>
                        <button
                          onClick={() => copyToClipboard(chunk.chunk_text || "", `chunk-${index}`)}
                          className="rounded-md border border-white/20 px-2.5 py-1 text-xs text-slate-200 transition hover:bg-white/10"
                        >
                          {copiedKey === `chunk-${index}` ? "Copied" : "Copy"}
                        </button>
                      </div>
                    </div>

                    <pre className="code-scroll max-h-56 overflow-auto rounded-lg border border-white/10 bg-black/30 p-3 font-mono text-xs leading-6 text-slate-200">
                      {chunk.chunk_text || "No code available."}
                    </pre>
                  </div>
                ))}
              </div>
            </div>
          )}
          <style>{`
            @keyframes fadeIn {
              from { opacity: 0; transform: translateY(6px); }
              to { opacity: 1; transform: translateY(0); }
            }

            .code-scroll::-webkit-scrollbar {
              width: 8px;
              height: 8px;
            }

            .code-scroll::-webkit-scrollbar-track {
              background: rgba(15, 23, 42, 0.55);
              border-radius: 9999px;
            }

            .code-scroll::-webkit-scrollbar-thumb {
              background: rgba(148, 163, 184, 0.45);
              border-radius: 9999px;
            }

            .code-scroll::-webkit-scrollbar-thumb:hover {
              background: rgba(148, 163, 184, 0.65);
            }
          `}</style>
            </div>
          )}
        </div>
      </div>

    </div>
  );
}

export default App;