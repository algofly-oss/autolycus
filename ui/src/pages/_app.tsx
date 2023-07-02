import "@/styles/globals.css";
import Head from "next/head";
import { AppProps } from "next/app";
import { Provider } from "react-redux";
import {
  MantineProvider,
  ColorSchemeProvider,
  ColorScheme,
} from "@mantine/core";
import { useHotkeys, useLocalStorage } from "@mantine/hooks";
import store from "../redux/store";
import { socket, SocketContext } from "../shared/contexts/socket";
import toast, { Toaster } from "react-hot-toast";

export default function App({ Component, pageProps }: AppProps) {
  const [colorScheme, setColorScheme] = useLocalStorage<ColorScheme>({
    key: "mantine-color-scheme",
    defaultValue: "dark",
    getInitialValueInEffect: true,
  });
  const toggleColorScheme = (value?: ColorScheme) =>
    setColorScheme(value || (colorScheme === "dark" ? "light" : "dark"));
  useHotkeys([["mod+J", () => toggleColorScheme()]]);

  return (
    <div className={colorScheme}>
      <Toaster />
      <Head>
        <title>Autolycus</title>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" />
        <link rel="manifest" href="/manifest.json" />
        <meta
          name="description"
          content="stream torrent files from hosted web servers remotely."
        />
        <meta name="theme-color" content="black" />
      </Head>
      <Provider store={store}>
        <ColorSchemeProvider
          colorScheme={colorScheme}
          toggleColorScheme={toggleColorScheme}
        >
          <MantineProvider
            withNormalizeCSS
            withGlobalStyles
            theme={{ colorScheme }}
          >
            <SocketContext.Provider value={socket}>
              <Component {...pageProps} />
            </SocketContext.Provider>
          </MantineProvider>
        </ColorSchemeProvider>
      </Provider>
    </div>
  );
}
