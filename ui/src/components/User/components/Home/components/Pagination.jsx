import React from "react";
import { FiChevronLeft, FiChevronRight } from "react-icons/fi";

export default function FloatingPagination({
  currentPage,
  totalPages,
  pageInput,
  pageSize,
  pageSizeOptions,
  rangeStart,
  rangeEnd,
  totalItems,
  onPageButtonClick,
  onPageInputChange,
  onApplyPageInput,
  onPageSizeChange,
}) {
  const canPrev = currentPage > 1;
  const canNext = currentPage < totalPages;

  const handlePrev = () => {
    if (canPrev && onPageButtonClick) {
      onPageButtonClick(currentPage - 1);
    }
  };

  const handleNext = () => {
    if (canNext && onPageButtonClick) {
      onPageButtonClick(currentPage + 1);
    }
  };

  const handlePageInputKeyDown = (event) => {
    if (event.key === "Enter") {
      onApplyPageInput?.();
    }
  };

  return (
    <div className="fixed bottom-[4.5rem] md:bottom-4 left-1/2 z-50 -translate-x-1/2">
      <div className="flex items-center gap-2 rounded-md border border-neutral-200/70 bg-white/90 px-3 py-2 text-sm shadow-lg backdrop-blur dark:border-neutral-800 dark:bg-neutral-900/90">
        {/* Page size */}
        <div className="flex items-center gap-1 text-xs font-medium text-neutral-700 dark:text-neutral-100">
          <span className="select-none">Page size</span>
          <div className="relative">
            <span className="inline-flex h-8 w-10 select-none items-center justify-center rounded-md border border-neutral-200 px-2 text-xs font-medium text-neutral-700 dark:border-neutral-800 dark:text-neutral-100">
              {pageSize}
            </span>
            <select
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
              className="absolute inset-0 h-8 w-10 cursor-pointer opacity-0 focus:outline-none focus:ring-0 focus:ring-offset-0"
              aria-label="Page size"
            >
              {pageSizeOptions.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Prev */}
        <button
          disabled={!canPrev}
          onClick={handlePrev}
          className="flex h-8 w-10 items-center justify-center rounded-md border border-neutral-200 text-neutral-600 disabled:opacity-40 dark:border-neutral-800 dark:text-neutral-300"
        >
          <FiChevronLeft />
        </button>

        {/* Page input */}
        <div className="flex items-center gap-1 text-xs font-medium text-neutral-700 dark:text-neutral-200">
          <input
            value={pageInput}
            onChange={(e) => onPageInputChange?.(e.target.value)}
            onKeyDown={handlePageInputKeyDown}
            onBlur={() => onApplyPageInput?.()}
            inputMode="numeric"
            className="h-8 w-10 rounded-md border border-neutral-200 bg-transparent px-2 text-center text-xs font-medium text-neutral-700 focus:outline-none dark:border-neutral-800 dark:text-neutral-100"
          />
        </div>

        {/* Range */}
        <span className="whitespace-nowrap text-xs font-medium text-neutral-700 dark:text-neutral-200">
          {rangeStart}–{rangeEnd} of {totalItems}
        </span>

        {/* Next */}
        <button
          disabled={!canNext}
          onClick={handleNext}
          className="flex h-8 w-10 items-center justify-center rounded-md border border-neutral-200 text-neutral-600 disabled:opacity-40 dark:border-neutral-800 dark:text-neutral-300"
        >
          <FiChevronRight />
        </button>
      </div>
    </div>
  );
}
