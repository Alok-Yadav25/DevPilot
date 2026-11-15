export function Logo() {
  return (
    <span className="brand premium-brand">
      <img
        className="brand-symbol"
        src="/devpilot-mark.svg"
        alt=""
        width="36"
        height="32"
      />
      <span>
        devpilot<span className="brand-period">.</span>
      </span>
    </span>
  );
}
export function CreatorCredit() {
  return (
    <span className="creator-credit">
      Made by{" "}
      <a
        href="https://github.com/Alok-Yadav25"
        target="_blank"
        rel="noopener noreferrer"
      >
        Alok Yadav<span aria-hidden="true"> ↗</span>
      </a>
    </span>
  );
}
