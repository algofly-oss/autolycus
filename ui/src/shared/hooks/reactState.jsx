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

const cloneValue = (val) => {
  if (Array.isArray(val)) {
    return [...val];
  }
  if (val && typeof val === "object") {
    return { ...val };
  }
  return {};
};

const writeObject = (obj, path, val) => {
  const keys = path.split(".");
  const lastKey = keys.pop();
  const nextRoot = cloneValue(obj);
  let cursor = nextRoot;

  keys.forEach((key) => {
    cursor[key] = cloneValue(cursor[key]);
    cursor = cursor[key];
  });

  cursor[lastKey] = val;
  return nextRoot;
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
      const current = readObject(value, key);
      if (Object.is(current, val)) {
        return;
      }
      setValue(writeObject(value, key, val));
      return;
    }

    if (!key || typeof key !== "object") {
      return;
    }

    const updates = key;
    const hasChanges = Object.keys(updates).some(
      (updateKey) => !Object.is(value[updateKey], updates[updateKey])
    );

    if (!hasChanges) {
      return;
    }

    setValue(updates);
  };

  return { value, setValue, get, set, reset };
}
