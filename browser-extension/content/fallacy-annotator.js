/**
 * Truth Lens Fallacy Annotator — 逻辑谬误实时标注器
 *
 * 理论支撑:
 *   - 结构指纹框架 (Germani, Spitale et al., 2026)
 *   - 逻辑基础型接种 > 技巧型接种 (JESP, 2025)
 *   - Skeptik browser fallacy annotator (ASU)
 *
 * 在网页上实时检测并标注逻辑谬误和操纵手法。
 * 不修改原始页面DOM结构，使用浮动覆盖层显示标注。
 */

(function() {
  "use strict";

  // ============================================================================
  // 检测模式库 (12种逻辑谬误 + 8种操纵手法)
  // ============================================================================

  const FALLACY_PATTERNS = {
    "false_cause": {
      name: "虚假因果",
      color: "#dc2626",
      bg: "rgba(220,38,38,0.08)",
      patterns: [
        /因为.{2,20}所以.{2,20}/g,
        /自从.{2,20}以来.{2,20}一直/g,
        /.{2,10}导致.{2,10}发生/g,
        /after.{2,30}(?:happened|occurred|started)/gi,
      ],
      desc: "将时间先后等同于因果关系",
      tip: "两件事先后发生 ≠ 前者导致后者。是否有其他因素？是否有对照实验？",
    },
    "false_dichotomy": {
      name: "虚假二分",
      color: "#ea580c",
      bg: "rgba(234,88,12,0.08)",
      patterns: [
        /要么.{2,10}要么.{2,10}/g,
        /不是.{2,8}就是.{2,8}/g,
        /if you.?re not with (?:us|me)/gi,
      ],
      desc: "将复杂问题简化为非黑即白",
      tip: "现实很少是非黑即白。有没有中间方案？有没有第三种可能？",
    },
    "slippery_slope": {
      name: "滑坡谬误",
      color: "#ca8a04",
      bg: "rgba(202,138,4,0.08)",
      patterns: [
        /如果.{2,15}(?:允许|放任|开始).{2,30}(?:下一步|然后|最后|最终).{2,30}/g,
        /if we (?:let|allow|start).{2,50}(?:next|then).{2,50}(?:eventually|finally)/gi,
      ],
      desc: "没有证据地推论一连串极端后果",
      tip: "每一步都需要独立验证。A→B→C的每一步概率可能是极低的。",
    },
    "hasty_generalization": {
      name: "草率概括",
      color: "#9333ea",
      bg: "rgba(147,51,234,0.08)",
      patterns: [
        /所有.{2,10}都.{2,10}/g,
        /从来没有.{2,10}/g,
        /every(?:one|body|thing|where)/gi,
        /(?:never|always|all|none)\s+(?:has|does|is|can|will)/gi,
      ],
      desc: "基于过少样本得出全局结论",
      tip: "'所有'、'从来没有'——这些全称量词需要非常强的证据。样本量多少？",
    },
    "appeal_to_emotion": {
      name: "诉诸情感",
      color: "#db2777",
      bg: "rgba(219,39,119,0.08)",
      patterns: [
        /你的.{2,6}(?:孩子|家人|父母|亲人)/g,
        /想想.{2,10}(?:可怜的|无助的|悲惨的)/g,
        /(?:your|our)\s*(?:children|kids|family|babies)/gi,
        /[！!]{3,}/g,
      ],
      desc: "用情感代替逻辑论证",
      tip: "情感诉求本身不是错的，但它不能替代证据。事实是什么？",
    },
    "straw_man": {
      name: "稻草人",
      color: "#0891b2",
      bg: "rgba(8,145,178,0.08)",
      patterns: [
        /所以.{2,5}(?:你是说|你认为|你相信)/g,
        /so (?:you.?re|you are) (?:saying|claiming)/gi,
      ],
      desc: "歪曲对方观点然后攻击这个歪曲版本",
      tip: "对方真的说了这个吗？还是被简化/极端化了？查原文。",
    },
    "appeal_to_authority": {
      name: "诉诸不当权威",
      color: "#7c3aed",
      bg: "rgba(124,58,237,0.08)",
      patterns: [
        /(?:scientists?|experts?|doctors?)\s*(?:say|agree|confirm)/gi,
        /(?:科学家|专家|医生)\s*(?:一致认为|都同意|证实)/g,
        /诺贝尔奖.{2,10}(?:说|证实)/g,
      ],
      desc: "引用权威但不提供该权威的资质或领域",
      tip: "权威是在自己的专业领域内说的吗？有具体姓名和出处吗？",
    },
    "red_herring": {
      name: "转移话题",
      color: "#059669",
      bg: "rgba(5,150,105,0.08)",
      patterns: [
        /(?:what about|whatabout).{0,30}\?/gi,
        /那.{2,10}呢？.{0,20}怎么不说/g,
      ],
      desc: "引入不相关话题转移注意力",
      tip: "这个问题和原话题有关吗？还是只是转移视线？",
    },
    "equivocation": {
      name: "偷换概念",
      color: "#d97706",
      bg: "rgba(217,119,6,0.08)",
      patterns: [
        /天然的.{2,6}就是安全的/g,
        /化学.{2,6}就是有害的/g,
        /natural\s*=\s*safe/gi,
        /chemical\s*=\s*toxic/gi,
      ],
      desc: "在不同含义间滑动同一词语",
      tip: "同一个词在不同语境下可能有完全不同的含义。'天然'不等于'安全'。",
    },
    "cherry_picking": {
      name: "选择性呈现",
      color: "#2563eb",
      bg: "rgba(37,99,235,0.08)",
      patterns: [
        /一项.{2,6}(?:研究|调查|实验).{2,15}(?:证明|证实|表明)/g,
        /唯一的(?:真相|解释|原因)/g,
      ],
      desc: "只选有利证据忽略相反证据",
      tip: "这是一项孤立研究还是业内共识？其他研究怎么说？",
    },
    "bandwagon": {
      name: "从众论证",
      color: "#4f46e5",
      bg: "rgba(79,70,229,0.08)",
      patterns: [
        /大家.{2,6}(?:都|都在|都说)/g,
        /(\d+)%的(?:人|网友|网民)/g,
        /全网(?:都在|疯传|热议)/g,
      ],
      desc: "以多数人相信来论证正确",
      tip: "'大家都信'不等于它是真的。历史上多数人相信过很多错误的事。",
    },
    "conspiracy": {
      name: "阴谋论框架",
      color: "#b91c1c",
      bg: "rgba(185,28,28,0.08)",
      patterns: [
        /他们.{2,6}(?:不想|不敢|不会)让.{2,4}知道/g,
        /(?:隐瞒|掩盖|封锁).{1,6}(?:真相|事实|消息)/g,
        /the (?:government|media|elites) (?:is|are) (?:hiding|covering)/gi,
      ],
      desc: "暗示有隐藏的恶意团体在操纵一切",
      tip: "真正的阴谋很难长期保密。有没有更简单的解释？证据链是否完整？",
    },
  };

  // ============================================================================
  // 页面扫描引擎
  // ============================================================================

  class FallacyScanner {
    constructor() {
      this.findings = [];
      this.annotated = new Set();
    }

    /**
     * 扫描页面文本内容，检测逻辑谬误
     */
    scan() {
      this.findings = [];

      // 扫描段落文本
      const paragraphs = document.querySelectorAll("p, li, blockquote, h1, h2, h3, h4, h5, h6, span.text, div.content, article p");

      paragraphs.forEach((el) => {
        // 跳过已标注、太短、或不可见的元素
        if (el.dataset.fallacyAnnotated) return;
        const text = el.textContent || el.innerText || "";
        if (text.length < 20) return;
        if (el.offsetParent === null) return; // 不可见

        const findings = this._scanElement(el, text);
        this.findings.push(...findings);
      });

      return this.findings;
    }

    _scanElement(el, text) {
      const found = [];

      for (const [key, info] of Object.entries(FALLACY_PATTERNS)) {
        for (const pattern of info.patterns) {
          // 重置 lastIndex
          pattern.lastIndex = 0;
          let match;
          while ((match = pattern.exec(text)) !== null) {
            const snippet = text.substring(
              Math.max(0, match.index - 20),
              Math.min(text.length, match.index + match[0].length + 20)
            );
            found.push({
              type: key,
              name: info.name,
              color: info.color,
              bg: info.bg,
              desc: info.desc,
              tip: info.tip,
              match: match[0],
              snippet: snippet,
              element: el,
              position: match.index,
              length: match[0].length,
            });
          }
        }
      }

      return found;
    }

    /**
     * 去重：同一段落中重复的谬误类型只保留置信度最高的
     */
    deduplicate(findings) {
      const byElement = {};
      findings.forEach((f) => {
        const key = f.element.outerHTML.substring(0, 100) + f.type;
        if (!byElement[key] || f.match.length > byElement[key].match.length) {
          byElement[key] = f;
        }
      });
      return Object.values(byElement);
    }
  }

  // ============================================================================
  // 标注渲染器 — 浮动覆盖层，不修改原始DOM
  // ============================================================================

  class FallacyRenderer {
    constructor() {
      this.overlayContainer = null;
      this.tooltips = [];
      this.active = false;
    }

    init() {
      if (this.overlayContainer) return;
      this.overlayContainer = document.createElement("div");
      this.overlayContainer.id = "truth-lens-fallacy-overlay";
      this.overlayContainer.style.cssText = `
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        pointer-events: none; z-index: 2147483646;
      `;
      document.body.appendChild(this.overlayContainer);
      this.active = true;
    }

    render(findings) {
      if (!this.active) return;
      this.clear();

      findings.forEach((f, i) => {
        try {
          const range = document.createRange();
          const textNode = this._findTextNode(f.element, f.snippet);
          if (!textNode) return;

          const rects = f.element.getBoundingClientRect();
          if (rects.top > window.innerHeight || rects.bottom < 0) return; // 不在视口

          // 创建彩色下划线高亮
          const highlight = document.createElement("div");
          highlight.className = "truth-lens-highlight";
          highlight.style.cssText = `
            position: absolute;
            left: ${rects.left + window.scrollX}px;
            top: ${rects.bottom + window.scrollY - 2}px;
            width: ${Math.min(rects.width, 600)}px;
            height: 3px;
            background: ${f.color};
            opacity: 0.7;
            border-radius: 0 0 2px 2px;
            pointer-events: auto;
            cursor: help;
            transition: opacity 0.2s, height 0.2s;
          `;

          highlight.addEventListener("mouseenter", () => this._showTooltip(f, rects));
          highlight.addEventListener("mouseleave", () => this._hideTooltips());
          highlight.addEventListener("click", (e) => {
            e.stopPropagation();
            this._showTooltip(f, rects, true);
          });

          highlight.title = `${f.name}: ${f.desc}`;
          this.overlayContainer.appendChild(highlight);
          this.tooltips.push(highlight);

          // 左侧边距标记
          const marker = document.createElement("div");
          marker.style.cssText = `
            position: absolute;
            left: ${Math.max(0, rects.left + window.scrollX - 8)}px;
            top: ${rects.top + window.scrollY}px;
            width: 4px;
            height: ${Math.min(rects.height, 80)}px;
            background: ${f.color};
            border-radius: 2px;
            opacity: 0.5;
            pointer-events: auto;
            cursor: help;
          `;
          this.overlayContainer.appendChild(marker);
          this.tooltips.push(marker);
        } catch (e) {
          // 忽略渲染错误，不中断整个扫描
        }
      });
    }

    _showTooltip(f, rects, pinned = false) {
      this._hideTooltips();

      const tooltip = document.createElement("div");
      tooltip.className = "truth-lens-tooltip" + (pinned ? " pinned" : "");
      tooltip.style.cssText = `
        position: fixed;
        left: ${Math.min(rects.left, window.innerWidth - 320)}px;
        top: ${Math.max(10, rects.top - 120)}px;
        width: 300px;
        background: #1a1a2e;
        color: #f1f5f9;
        border: 1px solid ${f.color};
        border-radius: 8px;
        padding: 12px;
        z-index: 2147483647;
        pointer-events: auto;
        font-family: system-ui, sans-serif;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
      `;

      tooltip.innerHTML = `
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
          <span style="font-size:16px">⚠️</span>
          <span style="font-weight:700;color:${f.color};font-size:14px">${f.name}</span>
        </div>
        <p style="font-size:12px;margin:0 0 6px 0;color:#94a3b8">${f.desc}</p>
        <div style="background:rgba(255,255,255,0.05);border-radius:4px;padding:8px;margin-bottom:6px">
          <code style="font-size:11px;color:#e2e8f0">"...${f.snippet}..."</code>
        </div>
        <div style="display:flex;align-items:start;gap:4px;padding:6px;background:rgba(${this._hexToRgb(f.color)},0.15);border-radius:4px">
          <span style="font-size:12px">💡</span>
          <span style="font-size:11px;color:#cbd5e1">${f.tip}</span>
        </div>
        <div style="font-size:10px;color:#64748b;margin-top:4px;text-align:right">
          Truth Lens · 逻辑谬误标注器
        </div>
      `;

      document.body.appendChild(tooltip);
      this._currentTooltip = tooltip;
    }

    _hideTooltips() {
      if (this._currentTooltip) {
        // 不自动关闭 pinned tooltip
        if (!this._currentTooltip.classList.contains("pinned")) {
          this._currentTooltip.remove();
          this._currentTooltip = null;
        }
      }
    }

    clear() {
      this.tooltips.forEach((el) => el.remove());
      this.tooltips = [];
      if (this._currentTooltip) {
        this._currentTooltip.remove();
        this._currentTooltip = null;
      }
    }

    destroy() {
      this.clear();
      if (this.overlayContainer) {
        this.overlayContainer.remove();
        this.overlayContainer = null;
      }
      this.active = false;
    }

    _findTextNode(el, snippet) {
      // 在元素内查找包含snippet的文本节点
      const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      let node;
      while ((node = walker.nextNode())) {
        if (node.textContent && node.textContent.includes(snippet.substring(5, snippet.length - 5))) {
          return node;
        }
      }
      return null;
    }

    _hexToRgb(hex) {
      const r = parseInt(hex.slice(1,3), 16);
      const g = parseInt(hex.slice(3,5), 16);
      const b = parseInt(hex.slice(5,7), 16);
      return `${r},${g},${b}`;
    }
  }

  // ============================================================================
  // 控制器
  // ============================================================================

  class FallacyAnnotator {
    constructor() {
      this.scanner = new FallacyScanner();
      this.renderer = new FallacyRenderer();
      this.scanning = false;
    }

    start() {
      if (this.scanning) return;
      this.scanning = true;
      this.renderer.init();

      // 初始扫描
      this._runScan();

      // 监听DOM变化（新加载内容）
      this._observer = new MutationObserver(() => {
        this._runScan();
      });
      this._observer.observe(document.body, {
        childList: true,
        subtree: true,
        characterData: false,
      });
    }

    stop() {
      this.scanning = false;
      if (this._observer) {
        this._observer.disconnect();
        this._observer = null;
      }
      this.renderer.destroy();
    }

    getStats() {
      const findings = this.scanner.findings;
      if (!findings.length) return { total: 0, types: {} };

      const types = {};
      findings.forEach((f) => {
        types[f.name] = (types[f.name] || 0) + 1;
      });

      return {
        total: findings.length,
        types: types,
      };
    }

    _runScan() {
      const raw = this.scanner.scan();
      const deduped = this.scanner.deduplicate(raw);
      this.renderer.render(deduped);
    }
  }

  // ============================================================================
  // 导出
  // ============================================================================

  window.TruthLensFallacyAnnotator = {
    FallacyScanner,
    FallacyRenderer,
    FallacyAnnotator,
    create: () => new FallacyAnnotator(),
  };
})();
