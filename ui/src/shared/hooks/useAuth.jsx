import { useEffect } from "react";
import { useRouter } from "next/router";
import { useSelector, useDispatch } from "react-redux";
import { authSelector, authActions } from "../../redux/features/authSlice";
import axios from "axios";
import apiRoutes from "../routes/apiRoutes";
import uiRoutes from "../routes/uiRoutes";

export default function useAuth() {
  const user = useSelector(authSelector);
  const dispatch = useDispatch();
  const router = useRouter();

  useEffect(() => {
    if (!user?.username) {
      getAccountInfo();
    }
  }, []);

  const clearStorage = () => {
    // remove all user data except theme preference
    const theme = localStorage.theme || "light";
    localStorage.clear();
    sessionStorage.clear();
    localStorage.theme = theme;
    dispatch(authActions.resetAccountInfo());
  };

  const getAccountInfo = async () => {
    return await axios
      .get(apiRoutes.accountInfo)
      .then((res) => {
        if (res?.data?.username) {
          dispatch(authActions.setAccountInfo(res.data));
          return res.data;
        } else {
          return {};
        }
      })
      .catch((err) => {});
  };

  const signIn = async (username, password) => {
    try {
      const response = await axios.post(apiRoutes.signIn, {
        username,
        password,
      });
      if (response?.data?.msg === "success") {
        await getAccountInfo();
      }
      return response?.data?.msg;
    } catch (error) {
      return error?.response?.data?.detail;
    }
  };

  const signOut = async (args) => {
    return await axios
      .post(apiRoutes.signOut, { withCredentials: true })
      .then((res) => {
        clearStorage();
        if (args?.redirect) {
          router.push(uiRoutes.root);
        }
      })
      .catch((err) => {
        console.log(err);
      });
  };

  const autoRoute = async () => {
    if (!user?.username) {
      await getAccountInfo().then((data) => {
        switch (data?.role) {
          case "admin":
            router.push(uiRoutes.home);
            break;
          case "user":
            router.push(uiRoutes.home);
            break;
          default:
            router.push(uiRoutes.signIn);
            break;
        }
      });
    } else {
      switch (user?.role) {
        case "admin":
          router.push(uiRoutes.home);
          break;
        case "user":
          router.push(uiRoutes.home);
          break;
        default:
          router.push(uiRoutes.signIn);
          break;
      }
    }
  };

  return {
    user,
    signIn,
    signOut,
    getAccountInfo,
    autoRoute,
  };
}
