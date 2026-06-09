import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Shield, Mail, Lock, User, ArrowRight, Loader2, AlertCircle, CheckCircle } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";

export function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validateUsername = (v: string) => {
    if (v.length < 3) return "用户名至少 3 个字符";
    if (v.length > 64) return "用户名最多 64 个字符";
    if (!/^[a-zA-Z0-9_-]+$/.test(v)) return "用户名只能包含字母、数字、下划线和连字符";
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const nameErr = validateUsername(username);
    if (nameErr) { setError(nameErr); return; }
    if (!email.includes("@")) { setError("请输入有效的邮箱地址"); return; }
    if (password.length < 8) { setError("密码至少 8 位"); return; }
    if (password !== confirmPassword) { setError("两次输入的密码不一致"); return; }

    setLoading(true);
    try {
      await register(username.trim(), email.trim(), password, displayName.trim() || username.trim());
      navigate("/");
    } catch (err: any) {
      setError(err.message || "注册失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-16">
      <div className="max-w-md mx-auto">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center h-16 w-16 rounded-2xl bg-primary/10 mb-4">
            <Shield className="h-8 w-8 text-primary" />
          </div>
          <h1 className="text-2xl font-bold">注册 TruthTrace</h1>
          <p className="text-muted-foreground mt-2">创建你的溯源账号</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              {error}
            </div>
          )}

          <div>
            <label className="text-sm font-medium mb-1.5 block">
              用户名 <span className="text-red-500">*</span>
            </label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full h-11 pl-10 pr-4 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                placeholder="3-64 个字符"
                autoFocus
              />
            </div>
          </div>

          <div>
            <label className="text-sm font-medium mb-1.5 block">
              显示名称
            </label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full h-11 px-4 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
              placeholder="可选，默认使用用户名"
            />
          </div>

          <div>
            <label className="text-sm font-medium mb-1.5 block">
              邮箱 <span className="text-red-500">*</span>
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full h-11 pl-10 pr-4 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                placeholder="your@email.com"
              />
            </div>
          </div>

          <div>
            <label className="text-sm font-medium mb-1.5 block">
              密码 <span className="text-red-500">*</span>
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full h-11 pl-10 pr-4 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                placeholder="至少 8 位"
              />
            </div>
          </div>

          <div>
            <label className="text-sm font-medium mb-1.5 block">
              确认密码 <span className="text-red-500">*</span>
            </label>
            <div className="relative">
              <CheckCircle className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSubmit(e)}
                className="w-full h-11 pl-10 pr-4 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                placeholder="再次输入密码"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full h-11 rounded-lg bg-primary text-primary-foreground font-medium text-sm hover:bg-primary/90 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>
                注册 <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>
        </form>

        <p className="text-center text-sm text-muted-foreground mt-6">
          已有账号？{" "}
          <Link to="/login" className="text-primary font-medium hover:underline">
            立即登录
          </Link>
        </p>
      </div>
    </div>
  );
}
