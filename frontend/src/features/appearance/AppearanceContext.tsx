/* The context and hook share the same appearance boundary. */
/* eslint-disable react-refresh/only-export-components */
import { MotionConfig } from "motion/react";
import {
  createContext,
  useContext,
  useLayoutEffect,
  useState,
  type ReactNode,
} from "react";

type Theme = "dark" | "light";
type Appearance = {
  theme: Theme;
  reduceMotion: boolean;
  toggleTheme: () => void;
  toggleMotion: () => void;
};
const AppearanceContext = createContext<Appearance>({
  theme: "dark",
  reduceMotion: false,
  toggleTheme: () => {},
  toggleMotion: () => {},
});

function stored(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function AppearanceProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() =>
    stored("adpathlens.theme") === "light" ? "light" : "dark",
  );
  const [reduceMotion, setReduceMotion] = useState(
    () => stored("adpathlens.reduce-motion") === "true",
  );
  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.motion = reduceMotion ? "reduced" : "full";
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", theme === "dark" ? "#101114" : "#f6f6f3");
    try {
      localStorage.setItem("adpathlens.theme", theme);
      localStorage.setItem("adpathlens.reduce-motion", String(reduceMotion));
    } catch {
      /* Appearance still works when browser storage is unavailable. */
    }
  }, [theme, reduceMotion]);
  return (
    <AppearanceContext.Provider
      value={{
        theme,
        reduceMotion,
        toggleTheme: () =>
          setTheme((current) => (current === "dark" ? "light" : "dark")),
        toggleMotion: () => setReduceMotion((current) => !current),
      }}
    >
      <MotionConfig reducedMotion={reduceMotion ? "always" : "never"}>
        {children}
      </MotionConfig>
    </AppearanceContext.Provider>
  );
}

export function useAppearance() {
  return useContext(AppearanceContext);
}
