import React from "react";

export function NexusLogo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
      <rect x="8" y="16" width="32" height="32" rx="8" fill="url(#nexus-grad1)" fillOpacity="0.85" style={{ mixBlendMode: "multiply" }} />
      <rect x="24" y="16" width="32" height="32" rx="8" fill="url(#nexus-grad2)" fillOpacity="0.85" style={{ mixBlendMode: "multiply" }} />
      <circle cx="32" cy="32" r="6" fill="#FFFFFF" opacity="0.9" />
      <defs>
        <linearGradient id="nexus-grad1" x1="8" y1="16" x2="40" y2="48" gradientUnits="userSpaceOnUse">
          <stop stopColor="#1094D2" />
          <stop offset="1" stopColor="#6C35D4" />
        </linearGradient>
        <linearGradient id="nexus-grad2" x1="24" y1="16" x2="56" y2="48" gradientUnits="userSpaceOnUse">
          <stop stopColor="#C62287" />
          <stop offset="1" stopColor="#D83B01" />
        </linearGradient>
      </defs>
    </svg>
  );
}
