import { useState } from "react";

type SnapshotFooterProps = {
  assetId: string;
  shareToken: string;
};

export default function SnapshotFooter({ assetId, shareToken }: SnapshotFooterProps) {
  const [copied, setCopied] = useState(false);

  async function handleShare() {
    const url = `${window.location.origin}/snapshot/${assetId}?token=${shareToken}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  return (
    <footer className="snapshot-footer">
      <div className="snapshot-footer-brand">
        <span className="brand-mark">G</span>
        <span>GeoRisk Engine</span>
      </div>
      <div className="snapshot-footer-actions">
        <button type="button" className="button ghost compact" onClick={handleShare}>
          {copied ? "Link copied!" : "Share"}
        </button>
        <a className="button primary compact" href={`/?asset=${assetId}#demo`}>
          Open in platform
        </a>
      </div>
    </footer>
  );
}
