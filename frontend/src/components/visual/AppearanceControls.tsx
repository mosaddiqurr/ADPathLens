import { Moon, Sun } from "lucide-react";
import { useAppearance } from "../../features/appearance/AppearanceContext";

export function AppearanceControls() {
  const { theme, toggleTheme } = useAppearance();
  return (
    <div className="appearance-controls" aria-label="Appearance controls">
      <button
        className="appearance-button"
        type="button"
        onClick={toggleTheme}
        aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
        title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      >
        {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
      </button>
    </div>
  );
}
