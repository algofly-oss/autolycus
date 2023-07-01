// Object storage with nested key read/write

import { useReducer } from "react";

const readObject = (obj, path) => {
  let val = null;
  if (path.includes(".")) {
    path
      .split(".")
      .map((path) => (val = val ? val[path] || null : obj[path] || null));
    return val;
  } else {
    return obj[path];
  }
};

const writeObject = (obj, path, val) => {
  const keys = path.split(".");
  const lastKey = keys.pop();
  const lastObj = keys.reduce((obj, key) => (obj[key] = obj[key] || {}), obj);
  lastObj[lastKey] = val;
  return obj;
};

export default function reactState(defaultState) {
  const [value, setValue] = useReducer(
    (state, updates) =>
      updates.__reset__
        ? {}
        : {
            ...state,
            ...updates,
          },
    defaultState || {}
  );

  const reset = () => {
    setValue({ __reset__: true });
  };

  const get = (key) => {
    if (key) {
      return readObject(value, key);
    } else {
      return value;
    }
  };

  const set = (key, val) => {
    if (typeof key === "string") {
      setValue(writeObject(value, key, val));
    } else {
      setValue(key);
    }
  };

  return { value, setValue, get, set, reset };
}
