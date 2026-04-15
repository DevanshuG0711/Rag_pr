import { motion } from "framer-motion";

function SourceCard({ chunk, index, copiedKey, onCopy }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ delay: index * 0.08, duration: 0.4, type: "spring" }}
      whileHover={{ y: -4, scale: 1.01 }}
      className="group relative overflow-hidden rounded-[1.5rem] border border-white/5 bg-gradient-to-br from-white/[0.04] to-black/20 p-5 shadow-[0_8px_30px_rgba(0,0,0,0.4)] backdrop-blur-md transition-all duration-300 hover:border-purple-500/50 hover:shadow-[0_20px_50px_rgba(168,85,247,0.25)] hover:bg-white/[0.06] transform-gpu"
    >
      <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 via-transparent to-transparent opacity-0 transition-opacity duration-500 group-hover:opacity-100" />
      
      <div className="relative z-10 mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/20">
             <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><path d="m10 13-2 2 2 2"/><path d="m14 17 2-2-2-2"/></svg>
          </div>
          <p className="truncate text-sm font-bold tracking-wide text-slate-200 group-hover:text-purple-300 transition-colors font-['Outfit']">
            {chunk.file_name || "Unknown file"}
          </p>
        </div>

        <div className="flex flex-wrap sm:flex-nowrap shrink-0 items-center gap-3">
          <div className="flex items-center gap-1.5 rounded-full bg-black/40 px-3 py-1 border border-white/5 backdrop-blur-sm shadow-inner">
             <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-yellow-500"><path d="M4 22h14a2 2 0 0 0 2-2V7l-5-5H6a2 2 0 0 0-2 2v4"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M3 15h6"/><path d="M3 19h6"/><path d="M13 18.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z"/></svg>
             <span className="text-xs font-semibold text-slate-300">
               {Number(chunk.score || 0).toFixed(2)}
             </span>
          </div>
          <button
            onClick={() => onCopy(chunk.chunk_text || "", `chunk-${index}`)}
            className="group/btn flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-200 transition-all hover:bg-purple-500/20 hover:border-purple-500/30 hover:text-white"
          >
            {copiedKey === `chunk-${index}` ? (
               <>
                 <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className="text-emerald-400"><polyline points="20 6 9 17 4 12"/></svg>
                 Copied
               </>
            ) : (
               <>
                 <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="group-hover/btn:scale-110 transition-transform"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
                 Copy
               </>
            )}
          </button>
        </div>
      </div>

      <div className="relative z-10 rounded-xl bg-black/40 p-1 border border-white/5 ring-1 ring-white/5 shadow-inner">
         <pre className="code-scroll max-h-64 overflow-auto rounded-lg bg-transparent p-4 font-mono text-sm leading-relaxed text-slate-300 antialiased selection:bg-purple-500/30">
           {chunk.chunk_text || "No code available."}
         </pre>
      </div>
    </motion.div>
  );
}

export default SourceCard;
