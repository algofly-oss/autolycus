import usePwaUpdates from "@/shared/usePwaUpdates";
import {useRouter} from "next/router";
import "@/styles/globals.css";
import "@/styles/settings.css";
import "@/styles/cinema.css";
import "@videojs/react/video/neutral-skin.css";
import "@/styles/movie-player.css";
import Head from "next/head";
import { MediaProfilesProvider } from "@/shared/MediaProfiles";
import { AppProps } from "next/app";
import { useEffect, useRef } from "react";
import { Provider, useSelector } from "react-redux";
import {
  MantineProvider,
  ColorSchemeProvider,
  ColorScheme,
} from "@mantine/core";
import { useHotkeys, useLocalStorage } from "@mantine/hooks";
import store from "../redux/store";
import { authSelector } from "../redux/features/authSlice";
import { socket, SocketContext } from "../shared/contexts/socket";
import { Toaster } from "react-hot-toast";
import {
  PUBLIC_IP_REFRESH_INTERVAL_MS,
  syncCurrentSessionPublicIp,
} from "../shared/sessionPublicIp";

function SessionPublicIpReporter() {
  const user = useSelector(authSelector);
  const isReportingRef = useRef(false);

  useEffect(() => {
    if (!user?.username || typeof window === "undefined") return;

    const reportPublicIp = async ({ force = false } = {}) => {
      if (isReportingRef.current) return;

      isReportingRef.current = true;
      try {
        await syncCurrentSessionPublicIp({ username: user.username, force });
      } catch (error) {
      } finally {
        isReportingRef.current = false;
      }
    };

    reportPublicIp();
    const intervalId = window.setInterval(
      reportPublicIp,
      PUBLIC_IP_REFRESH_INTERVAL_MS
    );
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        reportPublicIp();
      }
    };
    const handleManualRefresh = () => {
      reportPublicIp({ force: true });
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener(
      "autolycus:session-public-ip-refresh",
      handleManualRefresh
    );

    return () => {
      window.clearInterval(intervalId);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener(
        "autolycus:session-public-ip-refresh",
        handleManualRefresh
      );
    };
  }, [user?.username]);

  return null;
}

export default function App({ Component, pageProps }: AppProps) {
  usePwaUpdates();
  const router=useRouter();
  useEffect(()=>{if(router.pathname==="/watch")socket.disconnect();else if(!socket.connected)socket.connect();},[router.pathname]);
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
        <link
          rel="icon"
          href="/icons/autolycus-icon.svg"
          type="image/svg+xml"
        />
        <link
          rel="apple-touch-icon"
          href="/icons/apple-touch-icon.png?v=2"
          sizes="180x180"
        />
        <link rel="manifest" href="/manifest.json" />
        <meta
          name="description"
          content="stream torrent files from hosted web servers remotely."
        />
        <meta name="theme-color" content="#000000" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
        <meta name="apple-mobile-web-app-title" content="Autolycus" />
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
              {router.pathname!=="/watch" && <SessionPublicIpReporter />}
              {router.pathname==="/watch" ? <Component {...pageProps}/> : <MediaProfilesProvider><Component {...pageProps} /></MediaProfilesProvider>}
            </SocketContext.Provider>
          </MantineProvider>
        </ColorSchemeProvider>
      </Provider>
    </div>
  );
}
