import { useEffect } from "react";
import { Loader2 } from "lucide-react";
import { useApi } from "../../hooks/useApi";

export function RulesTab() {
  const { data, loading, request } = useApi<any>();
  useEffect(() => { request("/api/system/evolution/rule-history"); }, []);

  const history = data?.history || [];
  const versions = data?.current_versions || {};

  return (
    <div>
      <div className="mb-4 p-4 rounded-xl border bg-card">
        <h3 className="text-sm font-semibold mb-2">模块版本</h3>
        <div className="grid grid-cols-3 gap-2 text-xs">
          {Object.entries(versions).map(([k, v]) => (
            <div key={k} className="p-2 rounded bg-muted/50"><strong>{k}:</strong> v{v as string}</div>
          ))}
        </div>
      </div>
      <div className="space-y-2">
        {history.slice(0, 30).map((h: any, i: number) => (
          <div key={i} className="p-3 rounded-lg border bg-card text-xs">
            <div className="flex items-center justify-between">
              <span className="font-semibold">{h.module}.{h.rule_id} → v{h.version}</span>
              <span className="text-muted-foreground">{h.at}</span>
            </div>
            <p className="mt-1">{h.reason}</p>
            <p className="text-muted-foreground">by {h.changed_by}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
