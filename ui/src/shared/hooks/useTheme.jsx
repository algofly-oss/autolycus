import { useLocalStorage } from "@mantine/hooks";

export default function useTheme() {
  const [colorScheme, setColorScheme] = useLocalStorage({
    key: "mantine-color-scheme",
    defaultValue: "dark",
    getInitialValueInEffect: true,
  });

  const toggleColorScheme = (value) => {
    if (typeof value !== "string") {
      value = null;
    }

    setColorScheme(value || (colorScheme === "dark" ? "light" : "dark"));
  };

  const isDarkTheme = colorScheme === "dark";
  const setDarkTheme = (value) => {
    setColorScheme(value ? "dark" : "light");
  };

  return { colorScheme, toggleColorScheme, isDarkTheme, setDarkTheme };
}
