import { useEffect, useRef, useState, useCallback, useContext } from "react";
import _debounce from "lodash/debounce";
import { BsInputCursorText } from "react-icons/bs";
import { AiOutlineEye, AiOutlineEyeInvisible } from "react-icons/ai";
import DropDownSuggestion from "./DropDownSuggestion";
import { SocketContext } from "@/shared/contexts/socket";

export default function TextBox({
  label,
  required,
  placeholder,
  value,
  setValue,
  defaultValue,
  onKeyDown,
  icon,
  disabled,
  cursor,
  numeric,
  className,
  error,
  mask,
  ctsRoute,
  stcRoute,
  defaultSuggestions,
}) {
  const socket = useContext(SocketContext);
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [suggestionVisible, setSuggestionVisible] = useState(false);
  const [suggestionResult, setSuggestionResult] = useState([]);

  const inputRef = useRef();
  useEffect(() => {
    error && inputRef.current && inputRef.current.focus();
  }, [error]);

  const getSuggestions = (value) => {
    if (ctsRoute) {
      socket.emit(ctsRoute, value);
    } else if (defaultSuggestions) {
      setSuggestionResult(defaultSuggestions);
    }
  };

  const debounceGetSuggestions = useCallback(
    _debounce(getSuggestions, 100, {
      trailing: true,
    }),
    []
  );

  useEffect(() => {
    if (stcRoute) {
      // listen for data via websocket
      socket.on(stcRoute, (data) => {
        if (data) {
          setSuggestionResult(data.slice(0, 3));
          setSuggestionVisible(true);
        } else {
          setSuggestionVisible(true);
        }
      });
    }

    return () => {
      if (stcRoute) {
        // cleanup
        socket.off(stcRoute);
      }
    };
  }, []);

  useEffect(() => {
    if (defaultValue && !value) {
      setValue(defaultValue);
    }

    if (defaultSuggestions && !stcRoute) {
      setSuggestionResult(defaultSuggestions);
    }
  }, []);

  return (
    <div className={`block w-full mb-2 mt-1 text-xs md:text-sm ${className}`}>
      <div className="flex items-center space-x-1">
        <p className="ml-1 mb-1">{label}</p>
        {required && <p className="text-xs md:text-sm text-red-500">*</p>}
      </div>

      <div
        className="border flex items-center border-neutral-200 dark:border-neutral-800 rounded-lg bg-white dark:bg-black"
        style={{ borderColor: error ? "red" : "" }}
      >
        <div className="pl-4 text-neutral-400 dark:text-neutral-600">
          {icon || <BsInputCursorText size={20} />}
        </div>
        <input
          type={
            mask
              ? passwordVisible
                ? "text"
                : "password"
              : numeric
              ? "number"
              : "text"
          }
          ref={inputRef}
          value={value || ""}
          onChange={(e) => {
            setValue(e.target.value), debounceGetSuggestions(e.target.value);
          }}
          onClick={() => {
            setSuggestionVisible(true);
          }}
          onKeyDown={onKeyDown}
          className="border-0 placeholder-neutral-400 dark:placeholder-neutral-600 focus:ring-0 w-full rounded-lg text-xs md:text-sm py-3.5 bg-white dark:bg-black"
          style={{ cursor: cursor }}
          placeholder={placeholder ? placeholder : label}
          disabled={disabled ? true : false}
        />
        {mask && (
          <div
            className="pl-0.5 pr-4 text-neutral-400 dark:text-neutral-600 cursor-pointer"
            onClick={() => setPasswordVisible(!passwordVisible)}
          >
            {passwordVisible ? (
              <AiOutlineEye size={20} />
            ) : (
              <AiOutlineEyeInvisible size={20} />
            )}
          </div>
        )}
      </div>
      {error && (
        <p className="text-xs ml-1 mt-1" style={{ color: "red" }}>
          {error === true ? `${label} is required` : `${error}`}
        </p>
      )}

      {(stcRoute || defaultSuggestions) && (
        <div className="relative z-20">
          <DropDownSuggestion
            keyword={value}
            setKeyword={(value) => setValue(value)}
            keywordResult={suggestionResult}
            visible={suggestionVisible}
            setVisible={setSuggestionVisible}
          />
        </div>
      )}
    </div>
  );
}
