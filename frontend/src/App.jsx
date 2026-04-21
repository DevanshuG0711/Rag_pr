import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import axios from "axios";
import QueryInput from "./components/QueryInput";
import AnswerPanel from "./components/AnswerPanel";

const HISTORY_KEY = "rag_query_history_v1";
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

function App() {
  const [query, setQuery] = useState("");
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [copiedKey, setCopiedKey] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [queryHistory, setQueryHistory] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [indexingRepo, setIndexingRepo] = useState(false);
  const [repoStatus, setRepoStatus] = useState("");
  const answerRef = useRef(null);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(HISTORY_KEY);
      if (!stored) return;

      const parsed = JSON.parse(stored);
      if (!Array.isArray(parsed)) return;

      const normalized = parsed
        .filter(
          (item) =>
            item &&
            typeof item.query === "string" &&
            typeof item.answer === "string"
        )
        .slice(0, 5);

      setQueryHistory(normalized);
    } catch (error) {
      console.error("Failed to load query history", error);
    }
  }, []);

  useEffect(() => {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(queryHistory.slice(0, 5)));
  }, [queryHistory]);

  useEffect(() => {
    if (response && answerRef.current) {
      answerRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [response]);

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

    const allowedExtensions = [".py", ".go", ".js", ".ts"];
    const lowerName = file.name.toLowerCase();
    const isAllowed = allowedExtensions.some((ext) => lowerName.endsWith(ext));

    if (!isAllowed) {
      setUploadStatus("Please select a .py, .go, .js, or .ts file.");
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
      setErrorMessage("");

      const formData = new FormData();
      formData.append("file", selectedFile);

      await axios.post(`${API_BASE_URL}/api/ingest`, formData);
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
      setErrorMessage("");

      const res = await axios.post(`${API_BASE_URL}/api/query`, {
        query: trimmedQuery,
        top_k: 5,
      });

      setResponse(res.data);
      setQueryHistory((prev) => {
        const nextItem = {
          query: trimmedQuery,
          answer: String(res?.data?.answer || ""),
        };
        const deduped = prev.filter((item) => item.query !== trimmedQuery);
        return [nextItem, ...deduped].slice(0, 5);
      });
    } catch (err) {
      console.error(err);
      setErrorMessage(
        err?.response?.data?.detail ||
          "Unable to process your request right now. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  const handleIndexRepo = async () => {
    const trimmedRepoUrl = repoUrl.trim();

    if (!trimmedRepoUrl || indexingRepo) return;

    if (!/^https?:\/\//i.test(trimmedRepoUrl)) {
      setRepoStatus("Please enter a valid repository URL starting with http or https.");
      return;
    }

    try {
      setIndexingRepo(true);
      setRepoStatus("");

      await axios.post(`${API_BASE_URL}/api/index_repo`, {
        repo_url: trimmedRepoUrl,
      });

      setRepoStatus("Repository indexed successfully.");
    } catch (err) {
      console.error(err);
      setRepoStatus("Failed to index repository. Please try again.");
    } finally {
      setIndexingRepo(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.6 }}
      className="relative min-h-screen overflow-x-clip bg-[#020617] px-6 py-12 text-slate-100 md:px-12 lg:px-24"
    >
      {/* Dynamic Animated Background Mesh */}
      <motion.div 
        animate={{ 
          scale: [1, 1.2, 1],
          opacity: [0.3, 0.5, 0.3],
          x: [0, 50, 0],
          y: [0, 30, 0]
        }}
        transition={{ duration: 15, repeat: Infinity, ease: "linear" }}
        className="pointer-events-none absolute -left-40 -top-40 h-[600px] w-[600px] rounded-full bg-blue-600/15 blur-[120px]" 
      />
      <motion.div 
        animate={{ 
          scale: [1, 1.3, 1],
          opacity: [0.2, 0.4, 0.2],
          x: [0, -60, 0],
          y: [0, -40, 0]
        }}
        transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
        className="pointer-events-none absolute -bottom-40 -right-20 h-[700px] w-[700px] rounded-full bg-indigo-600/15 blur-[120px]" 
      />
      <motion.div 
        animate={{ 
          scale: [1, 1.1, 1],
          opacity: [0.15, 0.3, 0.15],
          x: [0, 40, 0],
          y: [0, -50, 0]
        }}
        transition={{ duration: 18, repeat: Infinity, ease: "linear" }}
        className="pointer-events-none absolute right-[20%] top-[30%] h-[500px] w-[500px] rounded-full bg-purple-600/15 blur-[120px]" 
      />

      <div className="relative z-10 mx-auto flex w-full max-w-7xl flex-col">
        <motion.header
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.2, duration: 0.5, type: "spring", stiffness: 100 }}
          className="mb-16 flex flex-col items-center text-center font-['Outfit']"
        >
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-blue-500/30 bg-blue-500/10 px-4 py-1.5 text-xs font-semibold tracking-wide text-blue-300 backdrop-blur-md shadow-[0_0_20px_rgba(59,130,246,0.15)]">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75"></span>
              <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-500"></span>
            </span>
            SYSTEM ONLINE
          </div>
          <h1 className="text-5xl font-bold tracking-tight text-white md:text-7xl lg:text-[5.5rem] leading-tight">
            Repo<span className="text-gradient">Lens</span>
          </h1>
          <p className="mt-8 max-w-2xl text-lg leading-relaxed text-slate-400 md:text-xl font-light">
            The RAG engine that actually understands software architecture.
          </p>
        </motion.header>

        <div className="flex w-full flex-col gap-8 lg:flex-row lg:items-start lg:gap-12">
          {/* Sidebar */}
          <motion.aside
            initial={{ x: -20, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            transition={{ delay: 0.3, duration: 0.5 }}
            className="glass-panel flex w-full flex-col rounded-3xl p-6 lg:sticky lg:top-8 lg:w-80 xl:w-96"
          >
            <div className="mb-6 flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500/20 text-blue-400 border border-blue-500/30">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/></svg>
              </div>
              <h2 className="text-xs font-bold uppercase tracking-[0.2em] text-slate-300 font-['Outfit']">
                Query History
              </h2>
            </div>

            {queryHistory.length === 0 ? (
              <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-700/50 bg-slate-800/10 py-12 text-center">
                 <p className="text-sm font-medium text-slate-400">No recent queries</p>
                 <p className="text-xs text-slate-500 mt-2">Start asking to build history.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {queryHistory.map((item, index) => {
                  const isActive = item.query === query.trim();
                  return (
                    <motion.button
                      key={`${item.query}-${index}`}
                      whileHover={{ scale: 1.02, x: 4 }}
                      onClick={() => {
                        setQuery(item.query);
                        setResponse({ answer: item.answer });
                      }}
                      className={`group relative w-full overflow-hidden rounded-2xl p-4 text-left transition-all ${
                        isActive
                          ? "border border-blue-500/50 bg-blue-500/15 shadow-[0_4px_30px_rgba(59,130,246,0.15)]"
                          : "border border-slate-700/30 bg-slate-800/20 hover:border-slate-600/50 hover:bg-slate-800/40"
                      }`}
                    >
                      {isActive && (
                         <div className="absolute left-0 top-0 h-full w-[3px] bg-gradient-to-b from-blue-400 to-indigo-500 rounded-l-2xl" />
                      )}
                      <p className={`truncate text-sm font-semibold transition-colors ${isActive ? 'text-white' : 'text-slate-300 group-hover:text-blue-300'}`}>
                        {item.query}
                      </p>
                      <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-slate-500 font-['Space_Grotesk']">
                        {item.answer}
                      </p>
                    </motion.button>
                  );
                })}
              </div>
            )}
          </motion.aside>

          {/* Main Area */}
          <div className="flex w-full flex-1 flex-col space-y-10">
            <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
              {/* File Upload Section */}
              <motion.section
                initial={{ y: 20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ delay: 0.4, duration: 0.5 }}
                className="glass-panel rounded-3xl p-8"
              >
                <div className="mb-6 flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><path d="M12 18v-6"/><path d="m9 15 3-3 3 3"/></svg>
                  </div>
                  <h2 className="text-xs font-bold uppercase tracking-[0.2em] text-slate-300 font-['Outfit']">
                    Ingest File
                  </h2>
                </div>

                <div
                  onDragOver={(event) => {
                    event.preventDefault();
                    setIsDragging(true);
                  }}
                  onDragLeave={() => setIsDragging(false)}
                  onDrop={(event) => {
                    event.preventDefault();
                    setIsDragging(false);
                    handleFileSelection(event.dataTransfer.files?.[0]);
                  }}
                  className={`relative flex flex-col items-center justify-center overflow-hidden rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-all duration-300 ${
                    isDragging
                      ? "border-blue-400 bg-blue-500/10 shadow-[0_0_30px_rgba(59,130,246,0.2)] scale-[1.02]"
                      : "border-slate-700/50 bg-slate-800/10 hover:border-slate-500 hover:bg-slate-800/30"
                  }`}
                >
                  {isDragging && <div className="absolute inset-0 bg-gradient-to-r from-blue-500/5 to-purple-500/5 animate-pulse" />}
                  
                  <div className="rounded-full bg-slate-900/80 p-4 mb-5 shadow-inner ring-1 ring-white/10">
                     <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-slate-300"><path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M12 12v9"/><path d="m8 17 4-4 4 4"/></svg>
                  </div>

                  <p className="text-sm font-semibold text-slate-200">Drag & Drop file</p>
                  <p className="mt-1.5 text-xs text-slate-400 font-['Space_Grotesk']">Supported: .py, .ts, .go, .js</p>

                  <div className="relative mt-8 flex w-full flex-col gap-3 sm:flex-row sm:items-center sm:justify-center">
                    <label className="group relative cursor-pointer overflow-hidden rounded-xl border border-white/10 bg-white/5 px-6 py-3 text-sm font-semibold text-slate-200 transition-all hover:bg-white/10 hover:shadow-lg">
                      <span className="relative z-10">Browse Files</span>
                      <input
                        type="file"
                        accept=".py,.go,.js,.ts"
                        onChange={(event) => handleFileSelection(event.target.files?.[0])}
                        className="hidden"
                      />
                    </label>

                    <motion.button
                      whileHover={{ scale: !selectedFile || uploading ? 1 : 1.05 }}
                      whileTap={{ scale: !selectedFile || uploading ? 1 : 0.95 }}
                      onClick={handleUpload}
                      disabled={!selectedFile || uploading}
                      className="relative overflow-hidden rounded-xl bg-white text-slate-950 px-8 py-3 text-sm font-bold shadow-[0_0_20px_rgba(255,255,255,0.3)] transition-all disabled:opacity-50 disabled:shadow-none hover:shadow-[0_0_30px_rgba(255,255,255,0.5)]"
                    >
                      {uploading ? (
                         <div className="flex items-center gap-2">
                            <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                            Uploading
                         </div>
                      ) : "Ingest"}
                    </motion.button>
                  </div>

                  {selectedFile && (
                    <motion.div initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} className="mt-6 flex items-center justify-center gap-2 rounded-lg bg-blue-500/10 px-4 py-2 border border-blue-500/20 backdrop-blur-sm">
                      <span className="h-2 w-2 rounded-full bg-blue-400 animate-pulse"></span>
                      <p className="truncate text-xs font-semibold text-blue-200">{selectedFile.name}</p>
                    </motion.div>
                  )}

                  {uploadStatus && (
                    <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className={`mt-5 text-sm font-medium ${uploadStatus.toLowerCase().includes("success") ? "text-emerald-400" : "text-rose-400"}`}>
                      {uploadStatus}
                    </motion.p>
                  )}
                </div>
              </motion.section>

              {/* GitHub Repo Section */}
              <motion.section
                initial={{ y: 20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ delay: 0.5, duration: 0.5 }}
                className="glass-panel rounded-3xl p-8"
              >
                <div className="mb-6 flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-500/20 text-purple-400 border border-purple-500/30">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"/><path d="M9 18c-4.51 2-5-2-7-2"/></svg>
                  </div>
                  <h2 className="text-xs font-bold uppercase tracking-[0.2em] text-slate-300 font-['Outfit']">
                    Index Repository
                  </h2>
                </div>
                
                <div className="flex h-[calc(100%-4rem)] flex-col justify-center gap-6">
                  <p className="text-sm leading-relaxed text-slate-400">Directly ingest a public GitHub repository for fast, comprehensive codebase indexing.</p>
                  
                  <div className="relative group">
                    <div className="absolute -inset-1 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 opacity-20 blur-md transition duration-500 group-focus-within:opacity-50 group-focus-within:duration-200"></div>
                    <input
                      value={repoUrl}
                      onChange={(event) => setRepoUrl(event.target.value)}
                      placeholder="https://github.com/owner/repo"
                      className="relative w-full rounded-xl border border-white/10 bg-[#020617]/80 px-5 py-4 text-sm text-slate-100 shadow-inner outline-none transition placeholder:text-slate-500 focus:border-purple-500/50 focus:bg-[#020617]"
                    />
                  </div>

                  <motion.button
                    whileHover={{ scale: indexingRepo || !repoUrl.trim() ? 1 : 1.02 }}
                    whileTap={{ scale: indexingRepo || !repoUrl.trim() ? 1 : 0.98 }}
                    onClick={handleIndexRepo}
                    disabled={indexingRepo || !repoUrl.trim()}
                    className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-purple-500 to-indigo-600 px-5 py-4 text-sm font-bold tracking-wide text-white shadow-lg shadow-indigo-500/25 transition-all hover:shadow-indigo-500/40 disabled:opacity-50 disabled:shadow-none"
                  >
                    {indexingRepo ? (
                      <>
                        <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                        Indexing...
                      </>
                    ) : "Commence Indexing"}
                  </motion.button>

                  {repoStatus && (
                    <motion.div initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} className={`rounded-xl border border-white/5 bg-black/20 p-4 text-center text-sm font-medium ${repoStatus.toLowerCase().includes("success") ? "text-emerald-400" : "text-rose-400"}`}>
                      {repoStatus}
                    </motion.div>
                  )}
                </div>
              </motion.section>
            </div>

            <motion.div
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.6, duration: 0.5 }}
              className="mt-6 sticky top-6 z-50 transition-all duration-300"
            >
              <QueryInput
                query={query}
                setQuery={setQuery}
                onSubmit={handleSubmit}
                loading={loading}
              />
            </motion.div>

            {errorMessage && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="overflow-hidden rounded-2xl border border-rose-500/30 bg-rose-500/10 shadow-[0_10px_30px_rgba(244,63,94,0.15)] backdrop-blur-md"
              >
                <div className="flex items-center gap-3 bg-rose-500/20 px-5 py-3.5">
                   <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-rose-400"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                   <span className="text-sm font-bold text-rose-200">Error Encountered</span>
                </div>
                <div className="px-5 py-5 text-sm text-rose-100 font-medium">
                  {errorMessage}
                </div>
              </motion.div>
            )}

            {loading && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="glass-panel relative overflow-hidden rounded-3xl p-8 shadow-[0_20px_50px_rgba(0,0,0,0.5)]"
              >
                <div className="absolute left-0 top-0 h-1 w-full bg-slate-800">
                   <motion.div 
                     initial={{ x: "-100%" }}
                     animate={{ x: "100%" }}
                     transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
                     className="h-full w-1/2 bg-gradient-to-r from-transparent via-blue-500 to-transparent" 
                   />
                </div>
                <div className="flex items-center gap-5 mb-8">
                  <div className="relative flex h-12 w-12 items-center justify-center">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-500 opacity-20 duration-1000"></span>
                    <svg className="animate-spin h-7 w-7 text-blue-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                  </div>
                  <div>
                    <h3 className="text-xl font-bold tracking-tight text-white">Synthesizing Context</h3>
                    <p className="text-sm text-slate-400 mt-1">Analyzing vector embeddings...</p>
                  </div>
                </div>
                <div className="space-y-4">
                  <div className="h-4 w-1/3 rounded-lg bg-slate-800 animate-pulse" />
                  <div className="h-4 w-full rounded-lg bg-slate-800 animate-pulse delay-75" />
                  <div className="h-4 w-11/12 rounded-lg bg-slate-800 animate-pulse delay-100" />
                  <div className="h-4 w-4/5 rounded-lg bg-slate-800 animate-pulse delay-150" />
                </div>
              </motion.div>
            )}

            {response && !loading && (
              <div ref={answerRef} className="pb-24">
                <AnswerPanel response={response} copiedKey={copiedKey} onCopy={copyToClipboard} />
              </div>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
}

export default App;