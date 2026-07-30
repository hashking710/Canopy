import { useEffect, useRef, useState } from "react";

/**
 * A text field purpose-built for USB barcode/QR/RFID-wand scanners. Those devices are
 * keyboard-emulating HID peripherals — a scan just "types" the code followed by Enter
 * into whatever's focused, with zero driver or plugin code needed. Rather than guess
 * at "was that fast typing a scan or a human" with a timing heuristic (real risk of
 * false positives/negatives), this is a single-purpose field that starts focused on
 * mount — manual typing + Enter works exactly the same way as a fallback for a
 * damaged/unreadable tag. It deliberately does *not* refocus itself after a scan: what
 * should happen next (stay here for another scan, or move on to the next field) is the
 * caller's call, made from inside `onScan` — the field naturally keeps focus on its own
 * if the caller doesn't move it elsewhere.
 */
export function ScanInput({
  onScan,
  placeholder = "Scan or type a tag…",
}: {
  onScan: (code: string) => void;
  placeholder?: string;
}) {
  const [value, setValue] = useState("");
  const [flash, setFlash] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const submit = () => {
    const code = value.trim();
    if (!code) return;
    onScan(code);
    setValue("");
    setFlash(true);
    window.setTimeout(() => setFlash(false), 400);
  };

  return (
    <div className={`scan-input ${flash ? "scan-input-flash" : ""}`}>
      <svg className="scan-icon" viewBox="0 0 20 20" width="16" height="16" fill="none">
        <path
          d="M3 5v10M6 5v10M9 5v3M9 12v3M12 5v10M15 5v3M15 12v3M17 5v10"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
        />
      </svg>
      <input
        ref={inputRef}
        value={value}
        placeholder={placeholder}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            submit();
          }
        }}
      />
    </div>
  );
}
