export const CLIPBOARD_COPY_STATUS = {
  COPIED: "copied",
  MANUAL: "manual",
  FAILED: "failed",
};

export const copyTextToClipboard = async (text) => {
  if (!text) return CLIPBOARD_COPY_STATUS.FAILED;
  if (typeof document === "undefined") return CLIPBOARD_COPY_STATUS.FAILED;

  if (
    typeof navigator !== "undefined" &&
    typeof window !== "undefined" &&
    navigator.clipboard?.writeText &&
    window.isSecureContext
  ) {
    try {
      await navigator.clipboard.writeText(text);
      return CLIPBOARD_COPY_STATUS.COPIED;
    } catch (err) {
      // Fall through to the selection based copy path.
    }
  }

  const textArea = document.createElement("textarea");
  textArea.value = text;
  textArea.setAttribute("readonly", "");
  textArea.style.position = "fixed";
  textArea.style.top = "0";
  textArea.style.left = "0";
  textArea.style.width = "1px";
  textArea.style.height = "1px";
  textArea.style.padding = "0";
  textArea.style.border = "0";
  textArea.style.opacity = "0";
  textArea.style.fontSize = "16px";

  document.body.appendChild(textArea);
  textArea.focus();
  textArea.select();
  textArea.setSelectionRange(0, textArea.value.length);

  let copied = false;
  try {
    copied = document.execCommand("copy");
  } catch (err) {
    copied = false;
  }

  document.body.removeChild(textArea);

  if (!copied) {
    if (typeof window !== "undefined") {
      window.prompt("Copy this text", text);
      return CLIPBOARD_COPY_STATUS.MANUAL;
    }
  }

  return copied ? CLIPBOARD_COPY_STATUS.COPIED : CLIPBOARD_COPY_STATUS.FAILED;
};
