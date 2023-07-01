const UI_PREFIX = process.env.UI_PREFIX || "";

const uiRoutes = {
  root: "/",
  home: "/home",
  accountRedirect: "/account",
  signIn: "/account/signin",
  signUp: "/account/signup",
  forgotPassword: "/account/forgot",
};

Object.entries(uiRoutes).forEach(([key, value]) => {
  uiRoutes[key] = UI_PREFIX + value;
});

export default uiRoutes;
