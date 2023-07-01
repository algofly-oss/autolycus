import { useEffect, useState, useRef } from "react";
import { useOnClickOutside } from "usehooks-ts";

export default function DropDownSuggestion({
  keyword,
  setKeyword,
  keywordResult,
  visible,
  setVisible,
}) {
  const ref = useRef(null);
  useOnClickOutside(ref, () => setVisible(false));

  useEffect(() => {
    const handleEsc = (event) => {
      if (event.keyCode === 27) {
        setVisible(false);
      }
    };
    window.addEventListener("keydown", handleEsc);

    return () => {
      window.removeEventListener("keydown", handleEsc);
    };
  }, []);

  return (
    <div
      className={`w-full absolute bg-white dark:bg-black py-1 rounded-md border dark:border-neutral-800 drop-shadow-sm ${
        keyword && keywordResult?.length > 0 && visible ? "block" : "hidden"
      }`}
      ref={ref}
    >
      {keywordResult?.length > 0 &&
        keywordResult.map((suggestedKeyword, idx) => (
          <div
            key={idx}
            className="p-2 px-3 hover:bg-blue-500 hover:text-white dark:hover:bg-blue-700 cursor-pointer"
            onClick={() => (setKeyword(suggestedKeyword), setVisible(false))}
          >
            <button className="truncate w-full text-left">
              {suggestedKeyword}
            </button>
          </div>
        ))}
    </div>
  );
}
