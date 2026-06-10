/**
 * 管理员后台 — 7Tab SPA
 * 组件已拆分为独立文件: components/admin/
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Shield, Activity, Bell, Wifi, Users, MessageSquare,
  Clock, Search, ArrowLeft, Layers,
} from "lucide-react";
import { OverviewTab } from "../components/admin/OverviewTab";
import { AnalysisTab } from "../components/admin/AnalysisTab";
import { AlertsTab } from "../components/admin/AlertsTab";
import { HealthTab } from "../components/admin/HealthTab";
import { UsersTab } from "../components/admin/UsersTab";
import { FeedbackTab } from "../components/admin/FeedbackTab";
import { RulesTab } from "../components/admin/RulesTab";
import { QualityTab } from "../components/admin/QualityTab";

const TABS = [
  { id: "overview", label: "概览", icon: Activity },
  { id: "analysis", label: "分析审查", icon: Search },
  { id: "alerts", label: "叙事告警", icon: Bell },
  { id: "quality", label: "质量仪表盘", icon: Layers },
  { id: "health", label: "系统健康", icon: Wifi },
  { id: "users", label: "用户管理", icon: Users },
  { id: "feedback", label: "反馈审核", icon: MessageSquare },
  { id: "rules", label: "规则历史", icon: Clock },
];

export function Admin() {
  const [tab, setTab] = useState("overview");

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Shield className="h-7 w-7 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">管理后台</h1>
            <p className="text-xs text-muted-foreground">系统管理、分析审查、用户管理</p>
          </div>
        </div>
        <Link to="/" className="text-sm text-primary hover:underline flex items-center gap-1"><ArrowLeft className="h-3.5 w-3.5" /> 返回首页</Link>
      </div>

      <div className="flex flex-wrap gap-1 mb-6 border-b pb-2 overflow-x-auto">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-t-lg text-xs font-medium transition-colors whitespace-nowrap ${tab === t.id ? "bg-primary/10 text-primary border-b-2 border-primary" : "text-muted-foreground hover:text-foreground"}`}>
            <t.icon className="h-3.5 w-3.5" />{t.label}
          </button>
        ))}
      </div>

      <div className="min-h-[500px]">
        {tab === "overview" && <OverviewTab />}
        {tab === "analysis" && <AnalysisTab />}
        {tab === "alerts" && <AlertsTab />}
        {tab === "health" && <HealthTab />}
        {tab === "quality" && <QualityTab />}
        {tab === "users" && <UsersTab />}
        {tab === "feedback" && <FeedbackTab />}
        {tab === "rules" && <RulesTab />}
      </div>
    </div>
  );
}
