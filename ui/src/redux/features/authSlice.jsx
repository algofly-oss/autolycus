import { createSlice } from "@reduxjs/toolkit";

const initialUserState = {
  name: null,
  username: null,
  role: "unknown",
  activated: false,
};

export const authSlice = createSlice({
  name: "auth",
  initialState: {
    user: initialUserState,
  },
  reducers: {
    setAccountInfo: (state, action) => {
      state.user = action.payload;
    },
    updateAccountInfo: (state, action) => {
      state.user = Object.assign(state.user, action.payload);
    },
    resetAccountInfo: (state) => {
      state.user = initialUserState;
    },
  },
});

export const authActions = authSlice.actions;
export const authSelector = (state) => state.auth.user;
export default authSlice.reducer;
