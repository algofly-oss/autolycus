import React from "react";
import { Menu } from "@mantine/core";
import { FiChevronDown, FiChevronLeft, FiChevronRight } from "react-icons/fi";

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
      <div className="flex items-center gap-1 rounded-md border border-neutral-200/70 bg-white/90 px-2 py-2 text-sm shadow-lg backdrop-blur sm:gap-2 sm:px-3 dark:border-neutral-800 dark:bg-neutral-900/90">
        {/* Page size */}
        <div className="flex items-center gap-1 text-xs font-medium text-neutral-700 dark:text-neutral-100">
          <span className="hidden select-none sm:inline">Page size</span>
          <Menu shadow="md" width={90} position="top-start" withinPortal={false}>
            <Menu.Target>
              <button
                type="button"
                className="inline-flex h-8 min-w-11 items-center justify-center gap-1 rounded-md border border-neutral-200 px-2 text-xs font-medium text-neutral-700 transition-colors hover:bg-neutral-100 dark:border-neutral-800 dark:text-neutral-100 dark:hover:bg-neutral-800"
                aria-label="Page size"
              >
                {pageSize}
                <FiChevronDown size={12} />
              </button>
            </Menu.Target>
            <Menu.Dropdown className="border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900">
              {pageSizeOptions.map((size) => (
                <Menu.Item
                  key={size}
                  onClick={() => onPageSizeChange(size)}
                  className={
                    size === pageSize
                      ? "bg-blue-500/10 font-semibold text-blue-600 dark:bg-blue-500/20 dark:text-blue-300"
                      : "text-neutral-700 dark:text-neutral-100"
                  }
                >
                  {size}
                </Menu.Item>
              ))}
            </Menu.Dropdown>
          </Menu>
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
        <span className="hidden whitespace-nowrap text-xs font-medium text-neutral-700 sm:inline dark:text-neutral-200">
          {rangeStart}–{rangeEnd} of {totalItems}
        </span>
        <span className="whitespace-nowrap text-xs font-medium text-neutral-700 sm:hidden dark:text-neutral-200">
          {rangeStart}–{rangeEnd}
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
