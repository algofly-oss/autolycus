import React from 'react';

const ProgressBar = ({ progress, showLabel = true }) => {
  return (
    <div>
      {showLabel && (
        <div className='flex justify-between mb-1'>
          <p className='bg-indigo-400 text-white dark:bg-indigo-700 py-1 px-2 rounded-3xl text-xs font-semibold flex-shrink-0'>
            DOWNLOADING
          </p>
          <p className='text-xs flex-shrink-0'>{progress}%</p>
        </div>
      )}
      <div className="w-full bg-gray-200 rounded-full h-2.5 dark:bg-gray-700">
        <div
          className="bg-indigo-600 h-2.5 rounded-full"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
};

export default ProgressBar;
