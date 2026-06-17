import { useEffect, useMemo, useState } from "react";
import { Modal, useMantineColorScheme } from "@mantine/core";
import { FiExternalLink, FiLoader } from "react-icons/fi";

const IMAGE_EXTENSIONS = new Set([
  "jpg",
  "jpeg",
  "png",
  "gif",
  "webp",
  "bmp",
  "avif",
]);

const AUDIO_EXTENSIONS = new Set(["mp3", "wav", "ogg", "aac", "m4a", "flac"]);
const PDF_EXTENSIONS = new Set(["pdf"]);
const TEXT_EXTENSIONS = new Set([
  "txt",
  "log",
  "md",
  "json",
  "csv",
  "xml",
  "srt",
  "vtt",
  "nfo",
  "yml",
  "yaml",
  "ini",
  "conf",
  "toml",
  "js",
  "jsx",
  "ts",
  "tsx",
  "css",
  "scss",
  "py",
  "sh",
  "java",
  "c",
  "cpp",
  "h",
  "hpp",
  "go",
  "rs",
  "php",
  "rb",
]);

const getExtension = (name = "") =>
  String(name).split(".").pop()?.toLowerCase() || "";

export const getPreviewType = (name) => {
  const extension = getExtension(name);
  if (IMAGE_EXTENSIONS.has(extension)) return "image";
  if (AUDIO_EXTENSIONS.has(extension)) return "audio";
  if (PDF_EXTENSIONS.has(extension)) return "pdf";
  if (TEXT_EXTENSIONS.has(extension)) return "text";
  return null;
};

export default function FilePreview({ open, url, name, type, onClose }) {
  const { colorScheme } = useMantineColorScheme();
  const [textContent, setTextContent] = useState("");
  const [loadingText, setLoadingText] = useState(false);
  const [textError, setTextError] = useState("");
  const isDarkTheme = colorScheme === "dark";
  const colors = {
    surface: isDarkTheme ? "#1A1B1E" : "#ffffff",
    border: isDarkTheme ? "#33363b" : "#e5e5e5",
    text: isDarkTheme ? "#f5f5f5" : "#171717",
    muted: isDarkTheme ? "#a3a3a3" : "#737373",
    hover: isDarkTheme ? "#2a2b2f" : "#e5e5e5",
  };

  useEffect(() => {
    if (!open || type !== "text" || !url) {
      setTextContent("");
      setTextError("");
      setLoadingText(false);
      return;
    }

    const controller = new AbortController();
    setLoadingText(true);
    setTextError("");

    fetch(url, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Unable to load file");
        }
        return response.text();
      })
      .then((content) => {
        setTextContent(content);
      })
      .catch((error) => {
        if (error.name !== "AbortError") {
          setTextError("Unable to preview this text file.");
        }
      })
      .finally(() => {
        setLoadingText(false);
      });

    return () => controller.abort();
  }, [open, type, url]);

  const title = useMemo(
    () => (
      <div className="flex min-w-0 items-center gap-3">
        <span className="min-w-0 truncate" style={{ color: colors.text }}>
          {name}
        </span>
        {url ? (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="shrink-0 rounded-md p-1.5 transition-colors"
            style={{ color: colors.muted }}
            title="Open in new tab"
            onClick={(event) => event.stopPropagation()}
            onMouseEnter={(event) => {
              event.currentTarget.style.backgroundColor = colors.hover;
              event.currentTarget.style.color = colors.text;
            }}
            onMouseLeave={(event) => {
              event.currentTarget.style.backgroundColor = "transparent";
              event.currentTarget.style.color = colors.muted;
            }}
          >
            <FiExternalLink size={16} />
          </a>
        ) : null}
      </div>
    ),
    [colors.hover, colors.muted, colors.text, name, url]
  );

  const renderContent = () => {
    if (type === "image") {
      return (
        <div
          className="flex max-h-[75vh] items-center justify-center rounded-lg p-2"
          style={{ backgroundColor: colors.surface }}
        >
          <img
            src={url}
            alt={name}
            className="max-h-[72vh] max-w-full rounded-md object-contain"
          />
        </div>
      );
    }

    if (type === "audio") {
      return (
        <div
          className="rounded-lg p-4"
          style={{ backgroundColor: colors.surface }}
        >
          <audio className="w-full" controls src={url}>
            Your browser does not support the audio tag.
          </audio>
        </div>
      );
    }

    if (type === "pdf") {
      return (
        <iframe
          src={url}
          title={name}
          className="h-[75vh] w-full rounded-lg border"
          style={{ backgroundColor: colors.surface, borderColor: colors.border }}
        />
      );
    }

    if (type === "text") {
      if (loadingText) {
        return (
          <div
            className="flex h-64 items-center justify-center"
            style={{ color: colors.muted }}
          >
            <FiLoader className="mr-2 animate-spin" size={18} />
            Loading preview...
          </div>
        );
      }

      if (textError) {
        return (
          <div
            className="rounded-lg p-6 text-sm"
            style={{ backgroundColor: colors.surface, color: colors.muted }}
          >
            {textError}
          </div>
        );
      }

      return (
        <pre
          className="max-h-[75vh] overflow-auto rounded-lg p-4 text-xs leading-5"
          style={{ backgroundColor: colors.surface, color: colors.text }}
        >
          {textContent}
        </pre>
      );
    }

    return null;
  };

  return (
    <Modal
      opened={open}
      onClose={onClose}
      title={title}
      size="80%"
      centered
      styles={{
        content: {
          backgroundColor: colors.surface,
          color: colors.text,
          border: `1px solid ${colors.border}`,
        },
        header: {
          backgroundColor: colors.surface,
          color: colors.text,
          borderBottom: `1px solid ${colors.border}`,
        },
        body: {
          backgroundColor: colors.surface,
          color: colors.text,
          paddingTop: 16,
        },
        title: {
          minWidth: 0,
          color: colors.text,
        },
        close: {
          color: colors.muted,
        },
        overlay: {
          backgroundColor: isDarkTheme
            ? "rgba(0, 0, 0, 0.72)"
            : "rgba(0, 0, 0, 0.45)",
        },
      }}
    >
      {renderContent()}
    </Modal>
  );
}
