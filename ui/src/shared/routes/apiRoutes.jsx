const API_PREFIX = process.env.API_PREFIX || "/api";

let apiRoutes = {
  // auth
  signUp: "/auth/signup",
  signIn: "/auth/signin",
  signOut: "/auth/signout",
  accountInfo: "/auth/me",

  // torrents
  addMagnet: "/torrent/add",
  pauseTorrent: "/torrent/pause",
  resumeTorrent: "/torrent/resume",
  listTorrents: "/torrent/all",
  getTorrentInfo: "/torrent/get",
  deleteTorrent: "/torrent/delete",

  //files
  browseFiles: "/files/browse",
  streamFile: "/files/stream",
  deleteFile: "/files/delete",
  archiveDir: "/files/archive",
  copyFile: "/files/copy",
  moveFile: "/files/move",
  renameFile: "/files/rename",
  diskUsage: "/files/status",
};

Object.entries(apiRoutes).forEach(([key, value]) => {
  apiRoutes[key] = API_PREFIX + value;
});

export default apiRoutes;
