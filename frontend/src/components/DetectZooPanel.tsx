/**
 * DetectZoo Bridge Admin Panel — Cross-platform rumor database sharing
 *
 * Manages import/export with external fact-checking databases:
 * Google Fact Check Tools, IFCN, Snopes, PolitiFact, FullFact, Japan FCC
 */
import { useState, useEffect, useRef } from "react";
import {
  Database, Download, Upload, Search, RefreshCw, Globe,
  Link2, Trash2, ExternalLink, AlertCircle, CheckCircle2,
  Loader2, ArrowRightLeft,
} from "lucide-react";

interface ExternalRegistry {
  [key: string]: {
    name: string;
    api_base?: string;
    url?: string;
    format: string;
    requires_key: boolean;
    status: string;
  };
}

interface BridgeEntry {
  entry_id: string;
  claim_text?: string;
  verdict?: string;
  credibility_score?: number;
  source?: string;
  review_url?: string;
  claim?: { claim_text?: string; claim_language?: string; claim_urls?: string[] };
  created_at?: string;
}

interface DetectZooData {
  registry?: ExternalRegistry;
  bridge_stats?: { stored_entries: number; imports: number; exports: number };
  entries?: BridgeEntry[];
  total?: number;
}

const API = `${(import.meta as any).env?.VITE_API_BASE_URL || ""}/api/detectzoo`;

export function DetectZooPanel() {
  const [data, setData] = useState<DetectZooData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchQ, setSearchQ] = useState("");
  const [searchResults, setSearchResults] = useState<BridgeEntry[]>([]);
  const [searching, setSearching] = useState(false);
  const [importText, setImportText] = useState("");
  const [importing, setImporting] = useState(false);
  const [exportIds, setExportIds] = useState("");
  const [exporting, setExporting] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    loadRegistry();
  }, []);

  const loadRegistry = async () => {
    try {
      const res = await fetch(`${API}/registry`);
      if (res.ok) setData(await res.json());
      setError("");
    } catch (e: any) {
      setError(e.message);
    }
    setLoading(false);
  };

  const loadEntries = async () => {
    try {
      const res = await fetch(`${API}/entries?limit=100`);
      if (res.ok) {
        const d = await res.json();
        setData((prev) => prev ? { ...prev, entries: d.entries, total: d.total } : d);
      }
    } catch {}
  };

  const handleSearch = async () => {
    if (!searchQ || searchQ.length < 2) return;
    setSearching(true);
    try {
      const res = await fetch(`${API}/search?q=${encodeURIComponent(searchQ)}&include_external=true`);
      if (res.ok) {
        const d = await res.json();
        setSearchResults(d.results || []);
      }
    } catch {}
    setSearching(false);
  };

  const handleImport = async () => {
    if (!importText) return;
    setImporting(true);
    try {
      const entry = JSON.parse(importText);
      const res = await fetch(`${API}/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(entry),
      });
      if (res.ok) {
        const d = await res.json();
        setMessage(`导入成功: ${d.entry_id}`);
        setImportText("");
        loadRegistry();
        loadEntries();
      } else {
        setMessage("导入失败: " + (await res.text()));
      }
    } catch (e: any) {
      setMessage("导入错误: " + e.message);
    }
    setImporting(false);
  };

  const handleExport = async () => {
    const ids = exportIds.split(",").map((s) => s.trim()).filter(Boolean);
    if (!ids.length) return;
    setExporting(true);
    try {
      const res = await fetch(`${API}/export-batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(ids),
      });
      if (res.ok) {
        const d = await res.json();
        setMessage(`导出成功: ${d.exported} 条记录`);
        loadRegistry();
        loadEntries();
      }
    } catch (e: any) {
      setMessage("导出错误: " + e.message);
    }
    setExporting(false);
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-8 justify-center text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> 加载跨库桥接数据...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Stats cards */}
      <div className="grid grid-cols-4 gap-3">
        <StatCard icon={<Database size={16} />} label="存储条目" value={data?.bridge_stats?.stored_entries || 0} color="blue" />
        <StatCard icon={<Download size={16} />} label="导入次数" value={data?.bridge_stats?.imports || 0} color="green" />
        <StatCard icon={<Upload size={16} />} label="导出次数" value={data?.bridge_stats?.exports || 0} color="amber" />
        <StatCard icon={<Globe size={16} />} label="外部库" value={Object.keys(data?.registry || {}).length} color="purple" />
      </div>

      {/* Message */}
      {message && (
        <div className={`p-3 rounded-lg border text-xs flex items-center gap-2 ${message.startsWith("导入错误") || message.startsWith("导出错误") || message.startsWith("导入失败") ? "border-red-200 bg-red-50 text-red-700" : "border-green-200 bg-green-50 text-green-700"}`}>
          <CheckCircle2 className="h-3.5 w-3.5" />
          {message}
          <button onClick={() => setMessage("")} className="ml-auto text-muted-foreground hover:text-foreground">×</button>
        </div>
      )}

      {/* External registry */}
      <div className="rounded-xl border bg-card overflow-hidden">
        <div className="px-4 py-3 border-b bg-muted/20 flex items-center justify-between">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <Globe size={14} /> 外部谣言库注册表
          </h3>
          <button onClick={loadRegistry} className="p-1 rounded hover:bg-muted" title="刷新">
            <RefreshCw className="h-3.5 w-3.5 text-muted-foreground" />
          </button>
        </div>
        <div className="p-2">
          <div className="grid grid-cols-1 gap-1">
            {data?.registry && Object.entries(data.registry).map(([key, info]) => (
              <div key={key} className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-muted/30 transition-colors">
                <div className="flex items-center gap-2.5">
                  <div className={`w-2 h-2 rounded-full ${info.status === "available" ? "bg-green-500" : info.status === "external_crawl" ? "bg-amber-500" : "bg-gray-300"}`} />
                  <div>
                    <span className="text-xs font-medium">{info.name}</span>
                    <span className="text-[10px] text-muted-foreground ml-1.5">({info.format})</span>
                  </div>
                  {info.requires_key && <span className="text-[9px] px-1 py-0.5 rounded bg-amber-100 text-amber-700">需 API Key</span>}
                </div>
                <span className="text-[10px] text-muted-foreground">{key}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Import / Export */}
      <div className="grid grid-cols-2 gap-4">
        {/* Import */}
        <div className="rounded-xl border bg-card p-4 space-y-3">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <Download size={14} /> 导入 DetectZoo JSON
          </h3>
          <textarea
            value={importText}
            onChange={(e) => setImportText(e.target.value)}
            placeholder='粘贴 DetectZoo 格式 JSON:&#10;{"entry_id":"...","schema_version":"1.0","claim":{...},"verdict":{...}}'
            className="w-full h-28 px-3 py-2 rounded-lg border text-xs font-mono resize-y"
          />
          <button
            onClick={handleImport}
            disabled={importing || !importText}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {importing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
            导入
          </button>
        </div>

        {/* Export */}
        <div className="rounded-xl border bg-card p-4 space-y-3">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <Upload size={14} /> 批量导出
          </h3>
          <input
            type="text"
            value={exportIds}
            onChange={(e) => setExportIds(e.target.value)}
            placeholder="事件ID (逗号分隔): evt-1, evt-2"
            className="w-full px-3 py-2 rounded-lg border text-xs"
          />
          <button
            onClick={handleExport}
            disabled={exporting || !exportIds.trim()}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {exporting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
            导出
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="rounded-xl border bg-card overflow-hidden">
        <div className="px-4 py-3 border-b bg-muted/20">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <Search size={14} /> 跨库搜索
          </h3>
        </div>
        <div className="p-3">
          <div className="flex gap-2">
            <input
              type="text"
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="搜索谣言条目..."
              className="flex-1 px-3 py-2 rounded-lg border text-xs"
            />
            <button
              onClick={handleSearch}
              disabled={searching || searchQ.length < 2}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-xs font-medium disabled:opacity-50"
            >
              {searching ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
              搜索
            </button>
          </div>
          {searchResults.length > 0 && (
            <div className="mt-3 space-y-1 max-h-64 overflow-y-auto">
              {searchResults.map((r, i) => (
                <div key={i} className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-muted/30 text-xs">
                  <div>
                    <span className="font-medium">{r.claim_text?.slice(0, 80)}</span>
                    <span className="text-muted-foreground ml-2">{r.verdict}</span>
                  </div>
                  <span className="text-[10px] text-muted-foreground">{r.source || "bridge"}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Stored entries */}
      <div className="rounded-xl border bg-card overflow-hidden">
        <div className="px-4 py-3 border-b bg-muted/20 flex items-center justify-between">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <Database size={14} /> 桥接存储 ({data?.total || 0} 条)
          </h3>
          <button onClick={loadEntries} className="p-1 rounded hover:bg-muted" title="刷新">
            <RefreshCw className="h-3.5 w-3.5 text-muted-foreground" />
          </button>
        </div>
        <div className="max-h-64 overflow-y-auto">
          {data?.entries && data.entries.length > 0 ? (
            data.entries.slice(0, 20).map((entry) => {
              const verdictText = entry.verdict || entry.claim?.claim_text?.slice(0, 30) || "(无文本)";
              const finalVerdict = typeof entry.verdict === "string" ? entry.verdict : "pending";
              const score = typeof entry.credibility_score === "number" ? entry.credibility_score : entry.verdict && typeof entry.verdict === "object" ? (entry.verdict as any).credibility_score : 50;
              return (
                <div key={entry.entry_id} className="flex items-center justify-between px-4 py-2 border-b last:border-b-0 text-xs hover:bg-muted/20">
                  <div className="flex-1 min-w-0">
                    <p className="truncate font-medium">{entry.claim_text || entry.claim?.claim_text || "(无文本)"}</p>
                    <p className="text-[10px] text-muted-foreground">
                      {finalVerdict} · {entry.claim?.claim_language || "zh"} · {entry.created_at?.slice(0, 10)}
                    </p>
                  </div>
                  <div className="flex items-center gap-1.5 ml-2">
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold"
                      style={{
                        backgroundColor: finalVerdict === "false" ? "#fef2f2" : finalVerdict === "true" ? "#dcfce7" : "#f3f4f6",
                        color: finalVerdict === "false" ? "#dc2626" : finalVerdict === "true" ? "#16a34a" : "#6b7280",
                      }}
                    >
                      {typeof score === "number" ? score.toFixed(0) : "?"}/100
                    </span>
                  </div>
                </div>
              );
            })
          ) : (
            <div className="p-8 text-center text-sm text-muted-foreground">
              暂无条目。导入或导出谣言记录后将在此显示。
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({ icon, label, value, color }: {
  icon: React.ReactNode; label: string; value: number; color: string;
}) {
  const colors = {
    blue: "bg-blue-50 dark:bg-blue-950/20 border-blue-200 dark:border-blue-800 text-blue-700",
    green: "bg-green-50 dark:bg-green-950/20 border-green-200 dark:border-green-800 text-green-700",
    amber: "bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800 text-amber-700",
    purple: "bg-purple-50 dark:bg-purple-950/20 border-purple-200 dark:border-purple-800 text-purple-700",
  };
  return (
    <div className={`rounded-lg border p-3 ${colors[color as keyof typeof colors]}`}>
      <div className="flex items-center gap-1.5 mb-1 text-xs opacity-70">{icon}{label}</div>
      <div className="text-xl font-bold">{value}</div>
    </div>
  );
}
