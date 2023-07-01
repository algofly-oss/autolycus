import { configureStore } from "@reduxjs/toolkit";
import thunkMiddleware from "redux-thunk";
import authSlice from "./features/authSlice";

export default configureStore({
  reducer: {
    auth: authSlice,
  },
  middleware: [thunkMiddleware],
});
