import React from 'react'
import { FiSearch } from 'react-icons/fi'

const SearchBar = ({ onSearch, loading }) => {
  const [searchText, setSearchText] = React.useState('')

  const handleSearch = async () => {
    if (searchText.trim()) {
      onSearch(searchText)
    }
  }

  return (
    <div className="flex">
      <input
        type="text"
        value={searchText}
        placeholder="Search torrent here..."
        className="text-xs md:text-sm border-0 outline-0 focus:ring-0 rounded-l-lg w-full bg-zinc-100 dark:bg-black pl-4"
        onChange={(e) => setSearchText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            handleSearch()
          }
        }}
        disabled={loading}
      />
      <button
        className="bg-blue-500 dark:bg-blue-700 rounded-r-lg p-4 px-5 -ml-2 text-white active:opacity-90 disabled:opacity-50"
        onClick={handleSearch}
        disabled={loading}
      >
        <FiSearch size={20} />
      </button>
    </div>
  )
}

export default SearchBar