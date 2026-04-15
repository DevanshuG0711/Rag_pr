import { motion } from "framer-motion";
import SourceCard from "./SourceCard";

function AnswerPanel({ response, copiedKey, onCopy }) {
  const answerText = response?.answer || "";
  const flowHeader = "Flow Explanation:";
  const flowHeaderIndex = answerText
    .toLowerCase()
    .indexOf(flowHeader.toLowerCase());

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

  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, type: "spring", stiffness: 80 }}
      className="mx-auto w-full max-w-4xl space-y-8"
    >
      {mainAnswer && (
        <motion.section
          whileHover={{ scale: 1.01, y: -2 }}
          className="relative overflow-hidden rounded-[2rem] border border-white/5 bg-gradient-to-br from-white/[0.04] to-black/20 p-8 shadow-[0_20px_50px_rgba(0,0,0,0.5)] backdrop-blur-2xl transition-all duration-300 hover:border-blue-500/30 hover:shadow-[0_20px_60px_rgba(59,130,246,0.15)] transform-gpu hover:bg-white/[0.06]"
        >
          <div className="absolute left-0 top-0 h-full w-[4px] bg-gradient-to-b from-blue-400 to-transparent" />
          <div className="mb-6 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/20 text-blue-400 border border-blue-500/20">
               <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/><path d="m9 12 2 2 4-4"/></svg>
            </div>
            <h2 className="text-xl font-bold tracking-tight text-white font-['Outfit']">
              Synthesized Answer
            </h2>
          </div>
          <p className="whitespace-pre-wrap text-base leading-relaxed text-slate-300 font-['Space_Grotesk']">
            {mainAnswer}
          </p>
        </motion.section>
      )}

      {hasFlowSection && flowLines.length > 0 && (
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, duration: 0.5 }}
          whileHover={{ scale: 1.005 }}
          className="relative overflow-hidden rounded-[2rem] border border-indigo-500/30 bg-gradient-to-b from-indigo-500/10 to-[#020617] p-8 shadow-[0_20px_50px_rgba(79,70,229,0.15)] backdrop-blur-xl"
        >
          <div className="absolute top-0 right-0 h-[300px] w-[300px] bg-indigo-500/20 blur-[100px] rounded-full pointer-events-none" />
          <div className="relative z-10 mb-6 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
                 <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M7 7h10"/><path d="M7 12h10"/><path d="M7 17h10"/></svg>
              </div>
              <h3 className="text-xl font-bold text-indigo-100 font-['Outfit']">Flow Execution Path</h3>
            </div>
            <button
              onClick={() => onCopy(flowLines.join("\n"), "flow")}
              className="group flex items-center gap-2 rounded-xl border border-indigo-400/30 bg-indigo-500/10 px-4 py-2 text-xs font-semibold text-indigo-200 transition-all hover:bg-indigo-500/30 hover:text-white"
            >
              {copiedKey === "flow" ? (
                 <>
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className="text-emerald-400"><polyline points="20 6 9 17 4 12"/></svg>
                    Copied
                 </>
              ) : (
                 <>
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="group-hover:scale-110 transition-transform"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
                    Copy Flow
                 </>
              )}
            </button>
          </div>

          <div className="relative z-10 space-y-4 rounded-2xl bg-black/40 border border-white/5 p-6 shadow-inner backdrop-blur-md">
            {flowLines.map((line, index) => (
              <div key={`${line}-${index}`} className="flex gap-4">
                 <div className="flex flex-col items-center mt-1.5">
                    <div className="h-2.5 w-2.5 rounded-full bg-indigo-400 shadow-[0_0_10px_rgba(129,140,248,0.8)]" />
                    {index !== flowLines.length - 1 && <div className="h-full w-[2px] bg-indigo-500/30 my-2 rounded-full" />}
                 </div>
                 <p className="font-mono text-sm leading-relaxed text-indigo-100/90 tracking-wide pb-2">{line}</p>
              </div>
            ))}
          </div>
        </motion.section>
      )}

      {Array.isArray(response?.retrieved_chunks) && response.retrieved_chunks.length > 0 && (
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4, duration: 0.5 }}
          whileHover={{ scale: 1.01 }}
          className="relative rounded-[2rem] border border-white/5 bg-gradient-to-br from-white/[0.04] to-black/20 p-8 shadow-[0_20px_50px_rgba(0,0,0,0.5)] backdrop-blur-2xl transition-all duration-300 hover:border-purple-500/30 hover:shadow-[0_20px_60px_rgba(168,85,247,0.15)] transform-gpu hover:bg-white/[0.04]"
        >
          <div className="mb-8 flex items-center gap-3">
             <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-500/20 text-purple-400 border border-purple-500/30">
               <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="m18 16 4-4-4-4"/><path d="m6 8-4 4 4 4"/><path d="m14.5 4-5 16"/></svg>
             </div>
             <h3 className="text-xl font-bold text-slate-100 font-['Outfit']">Extracted Code Context</h3>
          </div>
          <div className="grid gap-6">
            {response.retrieved_chunks.map((chunk, index) => (
              <SourceCard
                key={chunk.id || `${chunk.file_name || "chunk"}-${index}`}
                chunk={chunk}
                index={index}
                copiedKey={copiedKey}
                onCopy={onCopy}
              />
            ))}
          </div>
        </motion.section>
      )}
    </motion.div>
  );
}

export default AnswerPanel;
