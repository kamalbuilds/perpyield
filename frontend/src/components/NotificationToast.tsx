"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNotificationContext, type Notification } from "@/context/NotificationContext";

const typeConfig: Record<
  Notification["type"],
  { bg: string; border: string; icon: React.ReactNode; barColor: string }
> = {
  success: {
    bg: "from-accent-green/10 to-card-bg",
    border: "border-accent-green/30",
    barColor: "bg-accent-green",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#00ff88" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20 6L9 17l-5-5" />
      </svg>
    ),
  },
  error: {
    bg: "from-accent-red/10 to-card-bg",
    border: "border-accent-red/30",
    barColor: "bg-accent-red",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ff4444" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <path d="M15 9l-6 6M9 9l6 6" />
      </svg>
    ),
  },
  info: {
    bg: "from-blue-500/10 to-card-bg",
    border: "border-blue-500/30",
    barColor: "bg-blue-500",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <path d="M12 16v-4M12 8h.01" />
      </svg>
    ),
  },
  warning: {
    bg: "from-yellow-500/10 to-card-bg",
    border: "border-yellow-500/30",
    barColor: "bg-yellow-500",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#eab308" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
        <path d="M12 9v4M12 17h.01" />
      </svg>
    ),
  },
};

function ToastItem({
  notification,
  onDismiss,
}: {
  notification: Notification;
  onDismiss: (id: string) => void;
}) {
  const [progress, setProgress] = useState(100);
  const config = typeConfig[notification.type];

  useEffect(() => {
    if (notification.persistent) return;
    const duration = notification.duration;
    const start = Date.now();
    const interval = setInterval(() => {
      const elapsed = Date.now() - start;
      const pct = Math.max(0, ((duration - elapsed) / duration) * 100);
      setProgress(pct);
      if (pct <= 0) clearInterval(interval);
    }, 50);
    return () => clearInterval(interval);
  }, [notification.duration, notification.persistent]);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 80, scale: 0.95 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 80, scale: 0.95 }}
      transition={{ type: "spring", damping: 25, stiffness: 300 }}
      className={`relative w-80 rounded-xl border bg-gradient-to-br backdrop-blur-xl overflow-hidden shadow-2xl shadow-black/40 ${config.border} ${config.bg}`}
    >
      <div className="p-4">
        <div className="flex items-start gap-3">
          <div className="shrink-0 mt-0.5">{config.icon}</div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-foreground leading-tight">
              {notification.title}
            </p>
            <p className="text-xs text-muted mt-1 leading-relaxed line-clamp-2">
              {notification.message}
            </p>
          </div>
          <button
            onClick={() => onDismiss(notification.id)}
            className="shrink-0 p-1 rounded-md hover:bg-white/10 transition-colors text-muted hover:text-foreground"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>
      {!notification.persistent && (
        <div className="h-0.5 bg-white/5">
          <div
            className={`h-full ${config.barColor} transition-[width] duration-100 ease-linear`}
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
    </motion.div>
  );
}

export default function NotificationToast() {
  const { activeToasts, dismissNotification } = useNotificationContext();

  return (
    <div className="fixed top-16 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
      <AnimatePresence mode="popLayout">
        {activeToasts.map((n) => (
          <div key={n.id} className="pointer-events-auto">
            <ToastItem notification={n} onDismiss={dismissNotification} />
          </div>
        ))}
      </AnimatePresence>
    </div>
  );
}
