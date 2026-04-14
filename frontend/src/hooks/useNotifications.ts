"use client";

import { useCallback } from "react";
import { useNotificationContext, type NotificationType } from "@/context/NotificationContext";

interface NotificationOptions {
  persistent?: boolean;
  duration?: number;
  playSound?: boolean;
}

const NOTIFICATION_SOUNDS: Record<string, string> = {
  success: "/sounds/success.mp3",
  error: "/sounds/error.mp3",
  warning: "/sounds/warning.mp3",
  info: "/sounds/info.mp3",
};

function playNotificationSound(type: NotificationType) {
  try {
    const audio = new Audio(NOTIFICATION_SOUNDS[type]);
    audio.volume = 0.3;
    audio.play().catch(() => {});
  } catch {}
}

export function useNotifications() {
  const { addNotification, dismissNotification, markAsRead, markAllAsRead, clearAll, notifications, unreadCount } =
    useNotificationContext();

  const notify = useCallback(
    (
      type: NotificationType,
      title: string,
      message: string,
      options?: NotificationOptions
    ) => {
      if (options?.playSound) {
        playNotificationSound(type);
      }
      return addNotification(type, title, message, {
        persistent: options?.persistent,
        duration: options?.duration,
      });
    },
    [addNotification]
  );

  const depositSuccess = useCallback(
    (amount: number) =>
      notify("success", "Deposit Successful", `$${amount.toFixed(2)} USDC deposited into vault`),
    [notify]
  );

  const depositFailed = useCallback(
    (error: string) =>
      notify("error", "Deposit Failed", error, { duration: 8000 }),
    [notify]
  );

  const withdrawalSuccess = useCallback(
    (shares: number) =>
      notify("success", "Withdrawal Successful", `${shares.toFixed(2)} shares redeemed`),
    [notify]
  );

  const withdrawalFailed = useCallback(
    (error: string) =>
      notify("error", "Withdrawal Failed", error, { duration: 8000 }),
    [notify]
  );

  const strategySwitched = useCallback(
    (name: string) =>
      notify("info", "Strategy Switched", `Now running: ${name}`),
    [notify]
  );

  const positionOpened = useCallback(
    (symbol: string, side: string) =>
      notify("info", "Position Opened", `${side.toUpperCase()} ${symbol} position opened`),
    [notify]
  );

  const positionClosed = useCallback(
    (symbol: string, pnl?: number) => {
      const pnlStr = pnl !== undefined ? ` (PnL: ${pnl >= 0 ? "+" : ""}$${pnl.toFixed(2)})` : "";
      notify("info", "Position Closed", `${symbol} position closed${pnlStr}`);
    },
    [notify]
  );

  const aiAdvisorAlert = useCallback(
    (message: string) =>
      notify("warning", "AI Advisor", message, { persistent: true, playSound: true }),
    [notify]
  );

  const fundingRateOpportunity = useCallback(
    (symbol: string, apy: number) =>
      notify("success", "High Funding Rate", `${symbol} at ${apy.toFixed(1)}% APY`, { duration: 10000, playSound: true }),
    [notify]
  );

  const liquidationWarning = useCallback(
    (symbol: string) =>
      notify("error", "Liquidation Risk", `${symbol} position approaching liquidation`, { persistent: true, playSound: true }),
    [notify]
  );

  const strategyRecommendation = useCallback(
    (strategyName: string) =>
      notify("info", "Strategy Recommendation", `AI suggests switching to ${strategyName}`, { duration: 10000 }),
    [notify]
  );

  const apiError = useCallback(
    (context: string, error: string) =>
      notify("error", `${context} Error`, error, { duration: 8000 }),
    [notify]
  );

  return {
    notify,
    dismissNotification,
    markAsRead,
    markAllAsRead,
    clearAll,
    notifications,
    unreadCount,
    depositSuccess,
    depositFailed,
    withdrawalSuccess,
    withdrawalFailed,
    strategySwitched,
    positionOpened,
    positionClosed,
    aiAdvisorAlert,
    fundingRateOpportunity,
    liquidationWarning,
    strategyRecommendation,
    apiError,
  };
}
