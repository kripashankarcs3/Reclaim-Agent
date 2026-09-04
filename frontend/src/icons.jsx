/*
icons.jsx — chhota, consistent line-icon set (Feather-style: 24x24, stroke-based,
round caps/joins). Koi icon library dependency nahi — inline SVG, taaki bundle
chhota rahe aur look bilkul consistent ho. Har stage/status ka apna icon hai,
taaki timeline PADHNE mein aasaan lage, sirf text-scan na kare koi.
*/
const base = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

function Svg({ size = 18, children, className }) {
  return (
    <svg {...base} width={size} height={size} className={className} aria-hidden="true">
      {children}
    </svg>
  );
}

export const IconSearch = (p) => (
  <Svg {...p}><circle cx="11" cy="11" r="7" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></Svg>
);

export const IconActivity = (p) => (
  <Svg {...p}><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" /></Svg>
);

export const IconTarget = (p) => (
  <Svg {...p}><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="4.5" /><circle cx="12" cy="12" r="0.6" fill="currentColor" /></Svg>
);

export const IconShield = (p) => (
  <Svg {...p}><path d="M12 2 L20 6 V12 C20 17.5 16.4 20.7 12 22 C7.6 20.7 4 17.5 4 12 V6 Z" /></Svg>
);

export const IconShieldCheck = (p) => (
  <Svg {...p}><path d="M12 2 L20 6 V12 C20 17.5 16.4 20.7 12 22 C7.6 20.7 4 17.5 4 12 V6 Z" /><polyline points="9 12 11 14 15.5 9.5" /></Svg>
);

export const IconShieldAlert = (p) => (
  <Svg {...p}><path d="M12 2 L20 6 V12 C20 17.5 16.4 20.7 12 22 C7.6 20.7 4 17.5 4 12 V6 Z" /><line x1="12" y1="8" x2="12" y2="13" /><line x1="12" y1="16.3" x2="12" y2="16.4" /></Svg>
);

export const IconSend = (p) => (
  <Svg {...p}><polygon points="3 11 22 2 13 21 11 13 3 11" /></Svg>
);

export const IconBell = (p) => (
  <Svg {...p}><path d="M6 8a6 6 0 0 1 12 0c0 6 2.2 8 2.2 8H3.8S6 14 6 8Z" /><path d="M10.2 21a1.9 1.9 0 0 0 3.6 0" /></Svg>
);

export const IconFlag = (p) => (
  <Svg {...p}><line x1="4" y1="22" x2="4" y2="3" /><path d="M4 4c1-.8 2.4-1.2 4-1.2 3 0 3.6 2 6.4 2 1.4 0 2.6-.4 3.6-1.2v10c-1 .8-2.2 1.2-3.6 1.2-2.8 0-3.4-2-6.4-2-1.6 0-3 .4-4 1.2Z" /></Svg>
);

export const IconCornerDownRight = (p) => (
  <Svg {...p}><polyline points="15 10 20 15 15 20" /><path d="M4 4v7a4 4 0 0 0 4 4h12" /></Svg>
);

export const IconCheckCircle = (p) => (
  <Svg {...p}><path d="M22 11.1V12a10 10 0 1 1-5.9-9.1" /><polyline points="22 4 12 14.5 9 11.5" /></Svg>
);

export const IconClock = (p) => (
  <Svg {...p}><circle cx="12" cy="12" r="9.5" /><polyline points="12 7 12 12 15.5 14" /></Svg>
);

export const IconAlertTriangle = (p) => (
  <Svg {...p}><path d="M10.3 4.1 1.9 18a2 2 0 0 0 1.7 3h16.8a2 2 0 0 0 1.7-3L13.7 4.1a2 2 0 0 0-3.4 0Z" /><line x1="12" y1="9.5" x2="12" y2="13.5" /><line x1="12" y1="16.8" x2="12" y2="16.9" /></Svg>
);

export const IconWallet = (p) => (
  <Svg {...p}><path d="M3 7a2 2 0 0 1 2-2h13a1 1 0 0 1 1 1v3" /><path d="M3 7v11a2 2 0 0 0 2 2h14a1 1 0 0 0 1-1v-6a1 1 0 0 0-1-1h-4a2.5 2.5 0 0 1 0-5h4" /><circle cx="16" cy="14" r="0.6" fill="currentColor" /></Svg>
);

export const IconList = (p) => (
  <Svg {...p}><line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line x1="8" y1="18" x2="21" y2="18" /><line x1="3.5" y1="6" x2="3.51" y2="6" /><line x1="3.5" y1="12" x2="3.51" y2="12" /><line x1="3.5" y1="18" x2="3.51" y2="18" /></Svg>
);

export const IconSliders = (p) => (
  <Svg {...p}><line x1="4" y1="21" x2="4" y2="14" /><line x1="4" y1="10" x2="4" y2="3" /><line x1="12" y1="21" x2="12" y2="12" /><line x1="12" y1="8" x2="12" y2="3" /><line x1="20" y1="21" x2="20" y2="16" /><line x1="20" y1="12" x2="20" y2="3" /><line x1="1" y1="14" x2="7" y2="14" /><line x1="9" y1="8" x2="15" y2="8" /><line x1="17" y1="16" x2="23" y2="16" /></Svg>
);

export const IconZap = (p) => (
  <Svg {...p}><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" /></Svg>
);

export const IconArrowRight = (p) => (
  <Svg {...p}><line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" /></Svg>
);

export const IconGitBranch = (p) => (
  <Svg {...p}><circle cx="6" cy="5" r="2.2" /><circle cx="6" cy="19" r="2.2" /><circle cx="18" cy="9" r="2.2" /><path d="M6 7.2V17" /><path d="M6 7.2a8 8 0 0 0 8 7.8h2" /></Svg>
);

export const IconInfo = (p) => (
  <Svg {...p}><circle cx="12" cy="12" r="9.5" /><line x1="12" y1="11" x2="12" y2="16.5" /><line x1="12" y1="7.2" x2="12" y2="7.3" /></Svg>
);
