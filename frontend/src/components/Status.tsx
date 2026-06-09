import { Loader2, AlertCircle, PackageOpen, Search, Shield } from "lucide-react";
import { type ReactNode } from "react";
import { useTranslation } from "react-i18next";

interface StatusProps {
  className?: string;
  children?: ReactNode;
}

export function LoadingState({ className, children }: StatusProps) {
  const { t } = useTranslation();
  return (
    <div className={`flex flex-col items-center justify-center py-20 ${className || ""}`}>
      <Loader2 className="h-10 w-10 animate-spin text-primary mb-4" />
      <p className="text-sm text-muted-foreground">
        {children || t("common.loading")}
      </p>
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
  className,
}: {
  message: string;
  onRetry?: () => void;
  className?: string;
}) {
  const { t } = useTranslation();
  return (
    <div className={`flex flex-col items-center justify-center py-16 ${className || ""}`}>
      <div className="h-14 w-14 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center mb-4">
        <AlertCircle className="h-7 w-7 text-red-600 dark:text-red-400" />
      </div>
      <h3 className="text-lg font-medium mb-2">{t("common.error")}</h3>
      <p className="text-sm text-muted-foreground mb-4 max-w-sm text-center">
        {message}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          {t("common.retry")}
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: "search" | "package" | "shield";
  title: string;
  description: string;
  action?: ReactNode;
}) {
  const IconComponent =
    icon === "search" ? Search : icon === "shield" ? Shield : PackageOpen;

  return (
    <div className="flex flex-col items-center justify-center py-20">
      <div className="h-16 w-16 rounded-full bg-muted flex items-center justify-center mb-4">
        <IconComponent className="h-8 w-8 text-muted-foreground" />
      </div>
      <h3 className="text-lg font-medium mb-2">{title}</h3>
      <p className="text-sm text-muted-foreground mb-6 max-w-md text-center">
        {description}
      </p>
      {action}
    </div>
  );
}
