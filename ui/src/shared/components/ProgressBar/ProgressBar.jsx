import React from "react";

const ProgressBar = ({ progress, is_paused, progress_height, showLabel = true }) => {
  return (
    <div>
      {showLabel && (
        <div className="flex justify-between mb-1">
          <p
            className={`${
              is_paused
                ? "bg-rose-500/20 text-rose-500"
                : "bg-amber-500/20 text-amber-500"
            } py-1 px-2 rounded-3xl text-xs font-semibold flex-shrink-0`}
          >
            {is_paused ? "PAUSED" : "DOWNLOADING"}
          </p>
          <p className="text-xs flex-shrink-0">{progress}%</p>
        </div>
      )}
      <div className={`w-full bg-gray-200 rounded-full dark:bg-gray-700 drop-shadow-sm ${progress_height}`}>
        <div
          className={`bg-blue-500 dark:bg-blue-500 rounded-full transition-all duration-300 ${progress_height}`}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
};

export default ProgressBar;
