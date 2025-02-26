const API_PREFIX = process.env.API_PREFIX || "/api";

let apiRoutes = {
  // auth
  signUp: "/auth/signup",
  signIn: "/auth/signin",
  signOut: "/auth/signout",
  accountInfo: "/auth/me",

  // torrents
  addMagnet: "/torrent/add",
  addTorrent: "/torrent/add-file",
  pauseTorrent: "/torrent/pause",
  resumeTorrent: "/torrent/resume",
  listTorrents: "/torrent/all",
  getTorrentInfo: "/torrent/get",
  deleteTorrent: "/torrent/delete",
  searchTorrent: "/torrent/search",
  getMagnet: "/torrent/search/get-magnet",
  downloadStatusTorrent: "/torrent/download-status",

  //files
  browseFiles: "/files/browse",
  streamFile: "/files/stream",
  deleteFile: "/files/delete",
  archiveDir: "/files/archive",
  copyFile: "/files/copy",
  moveFile: "/files/move",
  renameFile: "/files/rename",
  diskUsage: "/files/status",
  transcodeStart: "/files/transcode/start",
  transcodeStop: "/files/transcode/stop",
  transcodeProgress: "/files/transcode/progress",
};

Object.entries(apiRoutes).forEach(([key, value]) => {
  apiRoutes[key] = API_PREFIX + value;
});

export default apiRoutes;
