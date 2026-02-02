import { FiSearch, FiX } from "react-icons/fi";

const SearchBar = ({ query, setQuery, loading, onSearch, onCancel }) => (
  <div className="flex w-full h-[3.2rem] rounded-lg overflow-hidden">
    <div className="relative flex-1">
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && onSearch()}
        placeholder="Search torrent here"
        className="w-full h-full px-4 pr-10 text-sm bg-zinc-100 dark:bg-black text-zinc-900 dark:text-zinc-100 outline-none"
      />
      {query && (
        <button
          onClick={() => setQuery("")}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
          aria-label="Clear search"
        >
          <FiX size={16} />
        </button>
      )}
    </div>
    <button
      onClick={loading ? onCancel : onSearch}
      className={`w-12 flex items-center justify-center text-white ${
        loading
          ? "bg-red-600 dark:bg-red-700"
          : "bg-blue-600 dark:bg-blue-700"
      }`}
    >
      {loading ? (
        <div className="relative w-5 h-5 flex items-center justify-center">
          <div className="absolute inset-0 rounded-full border-2 border-white/40 border-t-white animate-spin" />
          <FiX className="relative z-10" />
        </div>
      ) : (
        <FiSearch />
      )}
    </button>
  </div>
);

export default SearchBar;
