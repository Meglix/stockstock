"use client";

import { AnimatePresence, motion } from "motion/react";
import { Bell, BellOff, BellRing, CheckCheck, Clock3, PackageCheck, ShoppingBag, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { DemoNotification, useDemoStore } from "../context/DemoStoreContext";

const severityClass: Record<DemoNotification["severity"], string> = {
  info: "border-sky-300/20 bg-sky-400/10 text-sky-200",
  warning: "border-orange-300/25 bg-orange-400/12 text-orange-200",
  critical: "border-red-300/25 bg-red-400/12 text-red-200",
};

const typeAccentClass: Record<DemoNotification["type"], string> = {
  backorder: "border-amber-300/24 bg-amber-300/10 text-amber-100",
  "client-order": "border-orange-300/24 bg-orange-400/12 text-orange-100",
  "supplier-delivery": "border-sky-300/22 bg-sky-400/10 text-sky-100",
  market: "border-slate-300/16 bg-slate-300/8 text-slate-200",
};

const typeLabel: Record<DemoNotification["type"], string> = {
  backorder: "Backorder",
  "client-order": "Client",
  "supplier-delivery": "Supplier",
  market: "Market",
};

function NotificationIcon({ type }: { type: DemoNotification["type"] }) {
  if (type === "backorder") return <Clock3 size={16} />;
  if (type === "supplier-delivery") return <PackageCheck size={16} />;
  if (type === "client-order") return <ShoppingBag size={16} />;
  return <Bell size={16} />;
}

function timeAgo(value: string) {
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return "now";
  const diffSeconds = Math.max(0, Math.round((Date.now() - timestamp) / 1000));
  if (diffSeconds < 5) return "now";
  if (diffSeconds < 60) return `${diffSeconds}s ago`;
  const diffMinutes = Math.round(diffSeconds / 60);
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  return `${Math.round(diffMinutes / 60)}h ago`;
}

function NotificationRow({ notification, onOpen }: { notification: DemoNotification; onOpen: (notification: DemoNotification) => void }) {
  return (
    <motion.button
      layout
      initial={{ opacity: 0, y: -6, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, x: 24, scale: 0.97 }}
      transition={{ duration: 0.24, ease: "easeOut" }}
      onClick={() => onOpen(notification)}
      className={`group w-full rounded-xl border p-3 text-left transition hover:border-orange-300/28 hover:bg-orange-400/[0.055] ${
        notification.read
          ? "border-white/[0.07] bg-white/[0.025]"
          : notification.type === "supplier-delivery"
            ? "border-sky-300/18 bg-sky-400/[0.045]"
            : "border-orange-300/18 bg-orange-400/[0.06]"
      }`}
    >
      <div className="flex items-start gap-3">
        <span className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border ${typeAccentClass[notification.type] || severityClass[notification.severity]}`}>
          <NotificationIcon type={notification.type} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center justify-between gap-3">
            <span className="text-sm font-bold text-white">{notification.title}</span>
            {!notification.read ? <span className={`h-2 w-2 rounded-full ${notification.type === "supplier-delivery" ? "bg-sky-300" : "bg-orange-300"}`} /> : null}
          </span>
          <span className="mt-1 block text-sm leading-5 text-slate-400">{notification.message}</span>
          <span className="mt-3 flex items-center gap-2 text-xs text-slate-500">
            <Clock3 size={12} />
            {timeAgo(notification.createdAt)}
            <span className="rounded-full border border-white/[0.08] px-2 py-0.5 text-[0.66rem] uppercase text-slate-400">{typeLabel[notification.type]}</span>
          </span>
        </span>
      </div>
    </motion.button>
  );
}

export function NotificationCenter({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const { notifications, markAllNotificationsRead, markNotificationRead, notificationsMuted, toggleNotificationsMuted } = useDemoStore();

  const openNotification = (notification: DemoNotification) => {
    markNotificationRead(notification.id);
    router.push(notification.route);
    onClose();
  };

  return (
    <AnimatePresence>
      {open ? (
        <>
          <button aria-label="Close notifications" className="fixed inset-0 z-40 bg-black/35 backdrop-blur-[2px]" onClick={onClose} />
          <motion.aside
            initial={{ opacity: 0, y: -8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.98 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
            className="fixed right-4 top-[76px] z-50 w-[min(420px,calc(100vw-2rem))] overflow-hidden rounded-2xl border border-white/[0.09] bg-[#090b11]/96 shadow-[0_24px_80px_rgba(0,0,0,0.48)] backdrop-blur-xl"
          >
            <div className="flex items-start justify-between gap-4 border-b border-white/[0.08] p-4">
              <div>
                <p className="panel-eyebrow">Live operations</p>
                <h2 className="text-base font-black text-white">Notifications</h2>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={toggleNotificationsMuted}
                  className={`rounded-lg border p-2 transition ${
                    notificationsMuted
                      ? "border-sky-300/25 bg-sky-400/10 text-sky-100 hover:border-sky-200/45"
                      : "border-white/[0.08] bg-white/[0.035] text-slate-400 hover:border-orange-300/25 hover:text-orange-200"
                  }`}
                  aria-label={notificationsMuted ? "Unmute notification popups" : "Mute notification popups"}
                  title={notificationsMuted ? "Unmute popups" : "Mute popups"}
                >
                  {notificationsMuted ? <BellOff size={16} /> : <BellRing size={16} />}
                </button>
                <button
                  onClick={markAllNotificationsRead}
                  className="rounded-lg border border-white/[0.08] bg-white/[0.035] p-2 text-slate-400 transition hover:border-orange-300/25 hover:text-orange-200"
                  aria-label="Mark all notifications as read"
                >
                  <CheckCheck size={16} />
                </button>
                <button
                  onClick={onClose}
                  className="rounded-lg border border-white/[0.08] bg-white/[0.035] p-2 text-slate-400 transition hover:border-orange-300/25 hover:text-orange-200"
                  aria-label="Close notification center"
                >
                  <X size={16} />
                </button>
              </div>
            </div>
            <div className="max-h-[65vh] space-y-2 overflow-y-auto p-3 scrollbar-thin">
              {notifications.length ? (
                <AnimatePresence initial={false}>
                  {notifications.map((notification) => <NotificationRow key={notification.id} notification={notification} onOpen={openNotification} />)}
                </AnimatePresence>
              ) : (
                <div className="px-4 py-10 text-center text-sm text-slate-500">No notifications yet.</div>
              )}
            </div>
          </motion.aside>
        </>
      ) : null}
    </AnimatePresence>
  );
}

export function NotificationToasts() {
  const router = useRouter();
  const { visibleToasts, dismissToast, markNotificationRead, notificationsMuted } = useDemoStore();

  const openNotification = (notification: DemoNotification) => {
    markNotificationRead(notification.id);
    dismissToast(notification.id);
    router.push(notification.route);
  };

  if (notificationsMuted) return null;

  return (
    <div className="pointer-events-none fixed right-4 top-24 z-50 flex w-[min(390px,calc(100vw-2rem))] flex-col gap-3">
      <AnimatePresence initial={false}>
        {visibleToasts.map((notification) => (
          <motion.div
            key={notification.id}
            initial={{ opacity: 0, x: 28, scale: 0.97 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 28, scale: 0.97 }}
            transition={{ duration: 0.28, ease: "easeOut" }}
            className={`pointer-events-auto overflow-hidden rounded-xl border bg-[#0a0d13]/94 p-3 shadow-[0_18px_54px_rgba(0,0,0,0.44)] backdrop-blur-xl ${
              notification.type === "supplier-delivery" ? "border-sky-300/18" : "border-orange-300/18"
            }`}
          >
            <div className="flex items-start gap-3">
              <button
                onClick={() => openNotification(notification)}
                className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border ${typeAccentClass[notification.type] || severityClass[notification.severity]}`}
                aria-label="Open notification"
              >
                <NotificationIcon type={notification.type} />
              </button>
              <button className="min-w-0 flex-1 text-left" onClick={() => openNotification(notification)}>
                <p className="text-sm font-bold text-white">{notification.title}</p>
                <p className="mt-1 text-sm leading-5 text-slate-400">{notification.message}</p>
              </button>
              <button
                onClick={() => dismissToast(notification.id)}
                className="rounded-lg p-1.5 text-slate-500 transition hover:bg-white/[0.06] hover:text-slate-200"
                aria-label="Dismiss notification"
              >
                <X size={15} />
              </button>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
