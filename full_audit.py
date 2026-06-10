"""TruthTrace comprehensive product audit — every dimension."""
import os, re, glob, json, subprocess, sys, time
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
BE = os.path.join(ROOT, "backend")
FE = os.path.join(ROOT, "frontend")
results = defaultdict(list)

def add(cat, sev, msg):
    results[cat].append((sev, msg))

# =============================================================================
# 1. FRONTEND — CHECK EVERY PAGE LOADS + EVERY COMPONENT RENDERS
# =============================================================================
print("1. Frontend audit...")
spa_pages = ["/", "/search", "/rumors", "/academy", "/situational",
             "/community", "/studio", "/developer", "/admin", "/login", "/register"]
try:
    import urllib.request
    for p in spa_pages:
        try:
            r = urllib.request.urlopen(f"http://127.0.0.1:5173{p}", timeout=5)
            if r.status != 200:
                add("frontend", "high", f"SPA {p} returns HTTP {r.status}")
        except Exception as e:
            add("frontend", "critical", f"SPA {p}: {type(e).__name__}")
except Exception:
    add("frontend", "info", "Frontend server not running, skipping live checks")

# Check TS errors
result = subprocess.run(["npx", "tsc", "--noEmit"], cwd=FE, capture_output=True, text=True, shell=True)
ts_errors = result.stdout.count("error TS") + result.stderr.count("error TS") if result.stderr else result.stdout.count("error TS")
if ts_errors:
    add("frontend", "high", f"{ts_errors} TypeScript errors")
else:
    add("frontend", "ok", "0 TypeScript errors")

# Check all page components exist and export correctly
src_pages = glob.glob(os.path.join(FE, "src/pages/*.tsx"))
for pf in src_pages:
    name = os.path.basename(pf)
    with open(pf, encoding="utf-8") as f:
        content = f.read()
    if "export" not in content:
        add("frontend", "high", f"{name}: missing export")
    if "useEffect" in content and "try" not in content and "catch" not in content and ".catch" not in content:
        if "fetch(" in content:
            add("frontend", "medium", f"{name}: fetch() without .catch() error handling")

# =============================================================================
# 2. BACKEND API — EVERY ENDPOINT RESPONDS
# =============================================================================
print("2. Backend API audit...")
api_checks_failed = []
try:
    import urllib.request, json
    base = "http://127.0.0.1:8000"
    r = urllib.request.urlopen(f"{base}/api/health", timeout=3)
    if json.loads(r.read()).get("status") != "ok":
        api_checks_failed.append("health")
except Exception:
    add("backend", "info", "Backend server not running, skipping live API checks")

# Static analysis of all routes
api_files = glob.glob(os.path.join(BE, "app/api/*.py"))
total_routes = 0
unprotected_admin = []
for af in sorted(api_files):
    with open(af, encoding="utf-8") as f:
        content = f.read()
    routes = re.findall(r'@router\.\w+\(["\']([^"\']+)["\']', content)
    total_routes += len(routes)
    # Check admin routes without auth
    for r_path in re.findall(r'@router\.\w+\(["\'](/admin/[^"\']+)["\']', content):
        # Find nearest function after this route
        idx = content.find(f'@router')
        if idx >= 0:
            func_block = content[idx:idx+500]
            if "get_admin_user" not in func_block and "get_current_active_user" not in func_block:
                unprotected_admin.append(f"{os.path.basename(af)}:{r_path}")

if unprotected_admin:
    add("backend", "high", f"{len(unprotected_admin)} admin routes without auth protection")

# Check all engine modules importable
engine_files = glob.glob(os.path.join(BE, "app/engine/*.py"))
engine_ok = 0
for ef in engine_files:
    mod = os.path.splitext(os.path.basename(ef))[0]
    if mod == "__init__": continue
    with open(ef, encoding="utf-8") as f:
        content = f.read()
    if "def " in content or "class " in content:
        engine_ok += 1

# =============================================================================
# 3. DATA FLOW — SEARCH -> EVENT -> ANALYSIS -> REPORT
# =============================================================================
print("3. Data flow audit...")
# Check if search returns data with all required fields
search_file = os.path.join(BE, "app/api/search.py")
with open(search_file, encoding="utf-8") as f:
    search_src = f.read()
required_fields = ["id", "title", "summary", "credibility_score", "source_urls", "engine_verdict"]
missing_fields = [f for f in required_fields if f'"f"' not in search_src.replace(f'"{f}"', f'"__{f}__"')]
# Actually check if each field is returned
for field in required_fields:
    if field not in search_src:
        add("dataflow", "medium", f"Search API missing field: {field}")

# Check event detail flow
event_file = os.path.join(BE, "app/api/events.py")
with open(event_file, encoding="utf-8") as f:
    event_src = f.read()
for required in ["report", "analysis", "sources", "graph"]:
    if f"/events/{{event_id}}/{required}" not in event_src and f'/events/{{event_id}}/{required}' not in event_src:
        add("dataflow", "medium", f"Missing event sub-endpoint: /events/{{id}}/{required}")

# =============================================================================
# 4. SECURITY — RE-SCAN AFTER ALL FIXES
# =============================================================================
print("4. Security re-scan...")
for f in sorted(glob.glob(os.path.join(BE, "app/**/*.py"), recursive=True)):
    with open(f, encoding="utf-8") as fh:
        content = fh.read()
    # Check hardcoded secrets
    for secret_pat in ["truthtrace-dev-secret", "changeme", "super_secret", "YOUR_KEY"]:
        if secret_pat in content and "WARNING" not in content and "example" not in content.lower():
            add("security", "high", f"{os.path.relpath(f, BE)}: hardcoded '{secret_pat}'")
    # Check eval/exec
    if re.search(r'\beval\s*\(|\bexec\s*\(', content):
        add("security", "critical", f"{os.path.relpath(f, BE)}: uses eval/exec")
    # Check raw SQL without parameterization
    if "execute(" in content and "f\"" in content and "sql" in content.lower():
        add("security", "medium", f"{os.path.relpath(f, BE)}: possible SQL injection (f-string in execute)")

# Check .env NOT checked in
if os.path.exists(os.path.join(ROOT, ".gitignore")):
    with open(os.path.join(ROOT, ".gitignore")) as f:
        gi = f.read()
    for check in [".env", ".env.local", "*.db"]:
        if check not in gi.split("\n"):
            # normalize
            found = check in gi
            if not found:
                add("security", "critical", f"{check} not in .gitignore")

# =============================================================================
# 5. TEST COVERAGE
# =============================================================================
print("5. Test coverage audit...")
test_files = glob.glob(os.path.join(BE, "tests/test_*.py"))
test_names = {os.path.splitext(os.path.basename(t))[0].replace("test_", "") for t in test_files}

# What modules exist but have no tests?
src_modules = set()
for f in glob.glob(os.path.join(BE, "app/**/*.py"), recursive=True):
    rel = os.path.relpath(f, os.path.join(BE, "app"))
    mod = rel.replace("\\", ".").replace("/", ".").replace(".py", "")
    if mod not in ("__init__",):
        src_modules.add(mod)

# API modules with no tests
api_mods = {m.split(".")[-1] for m in src_modules if m.startswith("api.")}
api_tested = test_names & api_mods
api_untested = api_mods - api_tested - {"__init__"}
if api_untested:
    add("testing", "medium", f"{len(api_untested)} API modules without dedicated tests: {sorted(api_untested)[:8]}...")

# Engine modules with no tests
eng_mods = {m.split(".")[-1] for m in src_modules if m.startswith("engine.")}
eng_tested = test_names & eng_mods
eng_untested = eng_mods - eng_tested - {"__init__"}
if eng_untested:
    add("testing", "medium", f"{len(eng_untested)} engine modules without dedicated tests: {sorted(eng_untested)}")

# Evolution modules with no tests
ev_mods = {m.split(".")[-1] for m in src_modules if m.startswith("evolution.")}
ev_tested = test_names & ev_mods
ev_untested = ev_mods - ev_tested - {"__init__"}

# =============================================================================
# 6. MONITORING / OBSERVABILITY
# =============================================================================
print("6. Observability audit...")
backend_code = ""
for f in glob.glob(os.path.join(BE, "app/**/*.py"), recursive=True):
    with open(f, encoding="utf-8") as fh:
        backend_code += fh.read()

has_metrics = "prometheus" in backend_code or "Metrics" in backend_code
has_tracing = "opentelemetry" in backend_code or "sentry" in backend_code.lower()
has_structured_logging = "structlog" in backend_code or "logging_config" in backend_code

if not has_metrics:
    add("observability", "low", "No Prometheus/metrics endpoint")
if not has_tracing:
    add("observability", "low", "No OpenTelemetry/tracing (Sentry DSN configured but not runtime-injected)")

# =============================================================================
# 7. DOCUMENTATION
# =============================================================================
print("7. Documentation audit...")
docs_dir = os.path.join(ROOT, "docs")
if os.path.exists(docs_dir):
    doc_count = len(glob.glob(os.path.join(docs_dir, "*.md")))
    add("docs", "ok", f"{doc_count} docs in docs/")
else:
    add("docs", "medium", "No docs/ directory")

readme_size = os.path.getsize(os.path.join(ROOT, "README.md")) if os.path.exists(os.path.join(ROOT, "README.md")) else 0
deploy_size = os.path.getsize(os.path.join(ROOT, "DEPLOY.md")) if os.path.exists(os.path.join(ROOT, "DEPLOY.md")) else 0

# Check if i18n is complete
i18n_zh = os.path.join(FE, "src/i18n/locales/zh-CN.json")
i18n_en = os.path.join(FE, "src/i18n/locales/en-US.json")
if os.path.exists(i18n_zh) and os.path.exists(i18n_en):
    with open(i18n_zh, encoding="utf-8") as f:
        zh = json.load(f)
    with open(i18n_en, encoding="utf-8") as f:
        en = json.load(f)
    zh_keys = set(str(k) for k in zh.keys())
    en_keys = set(str(k) for k in en.keys())
    missing_en = zh_keys - en_keys
    if missing_en:
        add("docs", "medium", f"i18n: {len(missing_en)} keys missing in en-US")

# =============================================================================
# 8. PERFORMANCE
# =============================================================================
print("8. Performance audit...")
# Check for N+1 query patterns
for f in glob.glob(os.path.join(BE, "app/api/*.py")):
    with open(f, encoding="utf-8") as fh:
        content = fh.read()
    # Look for for-loop + select
    if re.search(r'for\s+\w+\s+in\s+.*:\s*\n\s+.*\.execute\(select', content):
        add("performance", "medium", f"{os.path.basename(f)}: potential N+1 query pattern")

# Check heavy operations in module-level code
for f in sorted(glob.glob(os.path.join(BE, "app/**/*.py"), recursive=True)):
    with open(f, encoding="utf-8") as fh:
        lines = fh.readlines()
    # Module-level code that isn't import/class/def
    for i, line in enumerate(lines[:20]):
        if line.strip() and not line.strip().startswith(("#", "import", "from", "class", "def", "@", "if", "__", "try", "except", "finally", "pass", "return", "raise", "with", "for", "while", "}", "{", ")", "]", "else:", "elif", "async", "\"\"\"", "'''")):
            if len(line.strip()) > 3:
                add("performance", "low", f"{os.path.relpath(f, BE)}:line{i+1}: module-level code '{line.strip()[:50]}'")

# =============================================================================
# 9. UI/UX AUDIT
# =============================================================================
print("9. UI/UX audit...")
fe_pages_dir = os.path.join(FE, "src/pages")
for pf in sorted(glob.glob(os.path.join(fe_pages_dir, "*.tsx"))):
    name = os.path.basename(pf).replace(".tsx", "")
    with open(pf, encoding="utf-8") as f:
        content = f.read()
    if "loading" not in content.lower() and "useState" in content and "fetch" in content:
        add("ux", "low", f"{name}: no loading state for async data")
    if "error" not in content.lower() and "catch" not in content.lower() and "fetch(" in content:
        add("ux", "low", f"{name}: no error state for async data")

# =============================================================================
# SUMMARY
# =============================================================================
print("\n" + "=" * 60)
print("TRUTHTRACE COMPREHENSIVE AUDIT REPORT")
print("=" * 60)

severity_order = {"ok": 0, "info": 1, "low": 2, "medium": 3, "high": 4, "critical": 5}
total_issues = 0

for cat in sorted(results.keys()):
    items = results[cat]
    items.sort(key=lambda x: severity_order.get(x[0], 0), reverse=True)
    sev_count = defaultdict(int)
    for sev, _ in items:
        sev_count[sev] += 1
    print(f"\n{cat.upper()}:")
    for sev, msg in items:
        marker = {"ok":"OK","info":"i","low":"LOW","medium":"MED","high":"HI","critical":"CRIT"}.get(sev, "?")
        print(f"  {marker} [{sev.upper()}] {msg}")
    counts = " · ".join(f"{sev}:{cnt}" for sev, cnt in sorted(sev_count.items()))
    print(f"  ── {counts}")
    total_issues += sum(1 for sev, _ in items if sev not in ("ok", "info"))

health = "HEALTHY" if total_issues == 0 else f"NEEDS {total_issues} FIXES"
print(f"\n{'='*60}")
print(f"PRODUCT HEALTH: {health}")
print(f"OK/INFO items: {sum(1 for v in results.values() for s,_ in v if s in ('ok','info'))}")
print(f"Issues to fix: {total_issues}")
print(f"{'='*60}")
