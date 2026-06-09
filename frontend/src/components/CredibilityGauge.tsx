import { cn } from "../lib/utils";

interface CredibilityGaugeProps {
  score: number;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function CredibilityGauge({ score, size = "md", className }: CredibilityGaugeProps) {
  const sizeMap = {
    sm: { container: "h-12 w-12", text: "text-sm", stroke: 2.5 },
    md: { container: "h-16 w-16", text: "text-lg", stroke: 3 },
    lg: { container: "h-24 w-24", text: "text-2xl", stroke: 3.5 },
  };

  const { container, text, stroke } = sizeMap[size];
  const radius = 20;
  const circumference = 2 * Math.PI * radius;
  const progress = (score / 100) * circumference;

  const color =
    score >= 70 ? "#16A34A" : score >= 40 ? "#CA8A04" : "#DC2626";
  const bgColor =
    score >= 70 ? "#DCFCE7" : score >= 40 ? "#FEF9C3" : "#FEE2E2";

  return (
    <div className={cn("credibility-gauge inline-flex items-center gap-3", className)}>
      <div className={cn("relative", container)}>
        <svg className="transform -rotate-90" viewBox="0 0 48 48">
          {/* Background circle */}
          <circle
            cx="24"
            cy="24"
            r={radius}
            fill="none"
            stroke={bgColor}
            strokeWidth={stroke * 1.5}
          />
          {/* Progress circle */}
          <circle
            cx="24"
            cy="24"
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeDasharray={circumference}
            strokeDashoffset={circumference - progress}
            strokeLinecap="round"
            className="transition-all duration-1000 ease-out"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className={cn("font-bold", text)} style={{ color }}>
            {score}
          </span>
        </div>
      </div>

      <div className="text-sm">
        <div className="font-medium">可信度</div>
        <div className="text-muted-foreground text-xs">
          {score >= 70 ? "较高" : score >= 40 ? "存疑" : "较低"}
        </div>
      </div>
    </div>
  );
}
