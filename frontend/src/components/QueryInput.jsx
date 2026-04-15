import { motion } from "framer-motion";

function QueryInput({ query, setQuery, onSubmit, loading }) {
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSubmit();
    }
  };

  return (
    <div className="mx-auto w-full max-w-4xl relative group transform-gpu transition-transform duration-300 hover:scale-[1.01]">
      <div className="absolute -inset-1 rounded-[2rem] bg-gradient-to-r from-blue-600 via-purple-600 to-indigo-600 opacity-25 blur-xl transition-all duration-500 group-focus-within:opacity-75 group-focus-within:blur-2xl group-hover:opacity-50"></div>
      <div className="relative flex w-full items-center gap-3 md:gap-4 rounded-3xl border border-white/10 bg-[#020617]/80 p-2 shadow-2xl backdrop-blur-2xl transition-all duration-300 group-focus-within:border-blue-500/50 group-focus-within:bg-[#020617]/90 group-focus-within:shadow-[0_0_40px_rgba(59,130,246,0.3)]">
        
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-blue-500/10 text-blue-400 ml-1 border border-blue-500/20">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
        </div>

        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask anything about your codebase..."
          className="flex-1 bg-transparent px-2 py-4 text-base font-medium text-slate-100 outline-none placeholder:text-slate-500 font-['Outfit']"
        />

        <motion.button
          whileHover={{ scale: loading || !query.trim() ? 1 : 1.05 }}
          whileTap={{ scale: loading || !query.trim() ? 1 : 0.95 }}
          onClick={onSubmit}
          disabled={loading || !query.trim()}
          className="relative overflow-hidden mr-1 flex h-12 items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-blue-500 to-indigo-600 px-8 text-sm font-bold tracking-wide text-white shadow-lg transition-all disabled:opacity-50 disabled:grayscale hover:shadow-blue-500/25"
        >
          {loading ? (
             <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
          ) : (
             <>
               Ask
               <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>
             </>
          )}
        </motion.button>
      </div>
    </div>
  );
}

export default QueryInput;
