/** ClaimReview JSON-LD 生成工具 */

const RATING_MAP: Record<string, string> = {
  true: "True",
  likely_true: "Mostly True",
  misleading: "Misleading",
  likely_false: "Mostly False",
  false: "False",
  unverifiable: "Unverifiable",
};

export function exportClaimReviewJSONLD(opts: {
  claimText: string;
  claimAuthor?: string;
  claimDate?: string;
  verdict: string;
  credibilityScore: number;
  reviewText?: string;
  reviewUrl?: string;
  publisherName?: string;
  publisherUrl?: string;
}): Record<string, any> {
  const rating = RATING_MAP[opts.verdict] || "Unverifiable";

  return {
    "@context": "https://schema.org",
    "@type": "ClaimReview",
    claimReviewed: (opts.claimText || "").slice(0, 500),
    author: {
      "@type": "Organization",
      name: opts.claimAuthor || "未知来源",
    },
    datePublished: opts.claimDate || new Date().toISOString(),
    reviewRating: {
      "@type": "Rating",
      ratingValue: ratingToNumeric(rating),
      alternateName: rating,
    },
    itemReviewed: {
      "@type": "Claim",
      author: {
        "@type": "Person",
        name: opts.claimAuthor || "未知来源",
      },
      datePublished: opts.claimDate,
    },
    url: opts.reviewUrl || "",
    publisher: {
      "@type": "Organization",
      name: opts.publisherName || "TruthTrace",
      url: opts.publisherUrl || "https://truthtrace.app",
    },
    reviewBody: (opts.reviewText || `经TruthTrace多引擎分析，该主张可信度评分为${opts.credibilityScore}/100，判定为${rating}。`).slice(0, 2000),
  };
}

export function ratingToNumeric(rating: string): number {
  const map: Record<string, number> = {
    True: 5, "Mostly True": 4, Mixture: 3,
    Misleading: 2, MissingContext: 2,
    "Mostly False": 1, False: 0,
    Unverifiable: -1, Satire: -1, Outdated: 1,
    TrueBut: 3, Edited: 1,
  };
  return map[rating] ?? -1;
}

export function generateJSONLDScript(jsonld: Record<string, any>): string {
  return JSON.stringify(jsonld, null, 2);
}
