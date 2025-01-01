import React from 'react';
import { BsCircleFill } from 'react-icons/bs';
import { formatFileSize, getQuality } from '@/shared/utils/fileUtils';
import { formatTimeRemaining } from '@/shared/utils/timeUtils';
import InfoBlock from './InfoBlock';
import ProgressBar from '@/shared/components/ProgressBar/ProgressBar';

const TorrentCard = ({ torrentData }) => {
  const {
    name,
    total_bytes,
    downloaded_bytes,
    download_speed,
    progress,
    is_finished
  } = torrentData;

  const { resolution, source } = getQuality(name);
  const remainingBytes = total_bytes - downloaded_bytes;
  const timeLeftSeconds = download_speed > 0 ? remainingBytes / download_speed : 0;

  return (
    <div className='bg-gray-100 dark:bg-indigo-900 rounded-xl p-3 flex flex-col gap-3'>
      <div>
        <h3 className='text-lg font-semibold dark:text-white truncate'>{name}</h3>
        <div className='flex items-center gap-2'>
          {resolution && (
            <span className='text-sm'>
              {resolution}
            </span>
          )}
          {resolution && source && (
            <BsCircleFill className='w-1 h-1 flex-shrink-0' />
          )}
          {source && (
            <span className='text-sm'>
              {source}
            </span>
          )}
          <BsCircleFill className='w-1 h-1 flex-shrink-0' />
          {total_bytes && (
            <span className='text-sm'>
              {formatFileSize(total_bytes)}
            </span>
          )}
        </div>
      </div>

      {!is_finished && (
        <>
          <ProgressBar progress={progress} />          
          <div className='flex flex-1 w-full gap-3'>
            <InfoBlock 
              title="Speed" 
              value={`${formatFileSize(download_speed)}/s`} 
            />
            <InfoBlock 
              title="Downloaded" 
              value={formatFileSize(downloaded_bytes)} 
            />
            <InfoBlock 
              title="Remaining" 
              value={formatFileSize(remainingBytes)} 
            />
            <InfoBlock 
              title="Time Remaining" 
              value={formatTimeRemaining(timeLeftSeconds)} 
            />
          </div>
        </>
      )}
    </div>
  );
};

export default TorrentCard;