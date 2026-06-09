import { useTranslation } from "react-i18next";
import { Languages } from "lucide-react";

const LANGUAGES: Record<string, string> = {
  "zh-CN": "中文",
  "en-US": "English",
};

export function LanguageSwitcher() {
  const { i18n } = useTranslation();
  const currentLang = i18n.language || "zh-CN";

  const toggle = () => {
    const next = currentLang === "zh-CN" ? "en-US" : "zh-CN";
    i18n.changeLanguage(next);
  };

  return (
    <button
      onClick={toggle}
      className="flex items-center gap-1.5 px-2 py-1.5 rounded-md text-sm text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
      title={LANGUAGES[currentLang] || currentLang}
      aria-label="Switch language"
    >
      <Languages className="h-4 w-4" />
      <span className="hidden sm:inline text-xs font-medium">
        {LANGUAGES[currentLang] || currentLang}
      </span>
    </button>
  );
}
