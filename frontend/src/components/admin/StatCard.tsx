export function StatCard({ label, value, color }: { label: string; value: string; color: string }) {
  const bg: Record<string, string> = {
    blue: "bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-800",
    green: "bg-green-50 dark:bg-green-950/30 border-green-200 dark:border-green-800",
    purple: "bg-purple-50 dark:bg-purple-950/30 border-purple-200 dark:border-purple-800",
    red: "bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-800",
    yellow: "bg-yellow-50 dark:bg-yellow-950/30 border-yellow-200 dark:border-yellow-800",
  };
  return (
    <div className={`p-4 rounded-xl border ${bg[color] || bg.blue}`}>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}
