import toast, { Toaster } from "react-hot-toast";
import { useMediaQuery } from "@mantine/hooks";
import useTheme from "./useTheme";

export default function useToast() {
  const isMobile = useMediaQuery("(max-width: 755px)");
  const theme = useTheme();

  const defaultConfig = {
    style: {
      background: theme.isDarkTheme ? "#333" : "#fff",
      color: theme.isDarkTheme ? "#fff" : "#333",
      fontSize: isMobile ? "0.75rem" : "0.875rem",
      wordWrap: "true"
    },
  };

  const success = (msg) => toast.success(msg, defaultConfig);
  const error = (msg) => toast.error(msg, defaultConfig);

  return { success, error, Toaster, defaultConfig };
}
