import { FaMoon } from "react-icons/fa";
import { FiSun } from "react-icons/fi";
import { motion } from "framer-motion";
import useTheme from "@/shared/hooks/useTheme";

export default function DarkThemeToggle() {
  const theme = useTheme();

  return (
    <div className="flex bg-zinc-200 dark:bg-zinc-900 p-4 rounded-lg text-sm mt-2 justify-center">
      <div
        className="flex space-x-4 py-2 px-3 items-center border-2 border-zinc-300 dark:border-neutral-700 bg-zinc-100 dark:bg-black rounded-full cursor-pointer"
        onClick={() => theme.toggleColorScheme()}
      >
        <FiSun />
        <motion.div
          animate={{ x: theme.isDarkTheme ? 9 : -22 }}
          transition={{
            type: "spring",
            stiffness: 700,
            damping: 40,
          }}
          className="absolute w-6 h-6 rounded-full bg-yellow-300 dark:bg-blue-700"
        />
        <FaMoon />
      </div>
    </div>
  );
}
