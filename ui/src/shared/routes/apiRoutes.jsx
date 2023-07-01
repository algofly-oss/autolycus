const API_PREFIX = process.env.API_PREFIX || "/api";

let apiRoutes = {
  // auth
  signIn: "/auth/signin",
  signOut: "/auth/signout",
  accountInfo: "/auth/me",
};

Object.entries(apiRoutes).forEach(([key, value]) => {
  apiRoutes[key] = API_PREFIX + value;
});

export default apiRoutes;
