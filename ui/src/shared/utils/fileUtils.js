export const formatFileSize = (bytes) => {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
};

export const getFileType = (filename) => {
  const extension = filename.split(".").pop()?.toLowerCase();

  const fileTypes = {
    video: ["mp4", "mkv", "avi", "mov", "wmv", "flv", "webm"],
    audio: ["mp3", "wav", "ogg", "aac", "m4a"],
    image: ["jpg", "jpeg", "png", "gif", "webp"],
    document: ["pdf", "doc", "docx", "txt", "rtf"],
  };

  for (const [type, extensions] of Object.entries(fileTypes)) {
    if (extensions.includes(extension)) return type;
  }

  return "Unknown Quality";
};

export const getQuality = (filename) => {
  const result = {
    resolution: null,
    source: null
  };

  const resolutions = ['480p', '720p', '1080p', '2160p', '4K', 'HD'];
  const sources = ['BluRay', 'WEBRip', 'WEB-DL', 'HDRip', 'DVDRip', 'BRRip', 'HDTV'];

  const upperName = filename.toUpperCase();

  for (const res of resolutions) {
    if (upperName.includes(res.toUpperCase())) {
      result.resolution = res;
      break;
    }
  }

  for (const source of sources) {
    if (upperName.includes(source.toUpperCase())) {
      result.source = source;
      break;
    }
  }

  return result;
};
