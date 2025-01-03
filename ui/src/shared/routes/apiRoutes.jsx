const API_PREFIX = process.env.API_PREFIX || "/api";

let apiRoutes = {
  // auth
  signUp: "/auth/signup",
  signIn: "/auth/signin",
  signOut: "/auth/signout",
  accountInfo: "/auth/me",

  // torrents
  addMagnet: "/torrent/add",
  listTorrents: "/torrent/all",

  //files
  browseFiles: '/files/browse',
  streamFile: '/files/stream',
  deleteFile: '/files/delete'
};

Object.entries(apiRoutes).forEach(([key, value]) => {
  apiRoutes[key] = API_PREFIX + value;
});

export default apiRoutes;
