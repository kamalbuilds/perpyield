"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  type ReactNode,
} from "react";

export type NotificationType = "success" | "error" | "info" | "warning";

export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  timestamp: number;
  read: boolean;
  persistent: boolean;
  duration: number;
}

interface NotificationContextValue {
  notifications: Notification[];
  activeToasts: Notification[];
  addNotification: (
    type: NotificationType,
    title: string,
    message: string,
    options?: { persistent?: boolean; duration?: number }
  ) => string;
  dismissNotification: (id: string) => void;
  markAsRead: (id: string) => void;
  markAllAsRead: () => void;
  clearAll: () => void;
  unreadCount: number;
}

const NotificationContext = createContext<NotificationContextValue | null>(null);

const MAX_TOASTS = 5;
const DEFAULT_DURATION = 5000;

let idCounter = 0;
function nextId(): string {
  return `notif-${Date.now()}-${++idCounter}`;
}

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const addNotification = useCallback(
    (
      type: NotificationType,
      title: string,
      message: string,
      options?: { persistent?: boolean; duration?: number }
    ): string => {
      const id = nextId();
      const persistent = options?.persistent ?? false;
      const duration = options?.duration ?? DEFAULT_DURATION;

      const notif: Notification = {
        id,
        type,
        title,
        message,
        timestamp: Date.now(),
        read: false,
        persistent,
        duration,
      };

      setNotifications((prev) => {
        const next = [notif, ...prev];
        return next;
      });

      if (!persistent) {
        const timer = setTimeout(() => {
          setNotifications((prev) => prev.filter((n) => n.id !== id));
          timers.current.delete(id);
        }, duration);
        timers.current.set(id, timer);
      }

      return id;
    },
    []
  );

  const dismissNotification = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const markAsRead = useCallback((id: string) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    );
  }, []);

  const markAllAsRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }, []);

  const clearAll = useCallback(() => {
    timers.current.forEach((timer) => clearTimeout(timer));
    timers.current.clear();
    setNotifications([]);
  }, []);

  const activeToasts = notifications
    .filter((n) => Date.now() - n.timestamp < n.duration || n.persistent)
    .slice(0, MAX_TOASTS);

  const unreadCount = notifications.filter((n) => !n.read).length;

  return (
    <NotificationContext.Provider
      value={{
        notifications,
        activeToasts,
        addNotification,
        dismissNotification,
        markAsRead,
        markAllAsRead,
        clearAll,
        unreadCount,
      }}
    >
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotificationContext(): NotificationContextValue {
  const ctx = useContext(NotificationContext);
  if (!ctx) {
    throw new Error(
      "useNotificationContext must be used within NotificationProvider"
    );
  }
  return ctx;
}
