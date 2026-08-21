"use client";

import { usePathname, useRouter } from "next/navigation";
import { useCallback, useMemo, useState, type ReactNode } from "react";

import AppHeader from "@/components/home/AppHeader";
import BurgerDrawer from "@/components/home/BurgerDrawer";
import CreateActionSheet from "@/components/home/CreateActionSheet";
import FabButton from "@/components/home/FabButton";
import HomeTabNav from "@/components/home/HomeTabNav";
import NotificationFab from "@/components/home/NotificationFab";
import NotificationSheet from "@/components/home/NotificationSheet";
import { useActiveClinicRole } from "@/components/DoctorGate";
import { useSwipeTabs } from "@/hooks/useSwipeTabs";
import { activeHomeTabHref, homeTabHrefsForRole } from "@/lib/tabOrder";
import { lightHaptic } from "@/lib/haptics";

type Props = {
  children: ReactNode;
  title?: string;
  showFab?: boolean;
  showNotification?: boolean;
};

export default function HomeShell({
  children,
  title = "",
  showFab = true,
  showNotification = true,
}: Props) {
  const pathname = usePathname() || "";
  const router = useRouter();
  const role = useActiveClinicRole();
  const [menuOpen, setMenuOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);

  const hideChrome =
    pathname.startsWith("/home/calendar/new") ||
    pathname.startsWith("/home/calendar/event") ||
    pathname.startsWith("/home/patients/new") ||
    pathname === "/home/patient/" ||
    pathname.startsWith("/home/patient/?");

  const tabHrefs = useMemo(() => homeTabHrefsForRole(role), [role]);
  const activeHref = useMemo(
    () => activeHomeTabHref(pathname, tabHrefs),
    [pathname, tabHrefs],
  );

  const onSwipeTab = useCallback(
    (next: string) => {
      if (next === activeHref) return;
      lightHaptic();
      router.push(next);
    },
    [activeHref, router],
  );

  const swipe = useSwipeTabs({
    items: hideChrome ? [] : tabHrefs,
    active: activeHref,
    onChange: onSwipeTab,
  });

  const fabBottom = "bottom-[7.5rem]";
  const notifBottom = "bottom-[4.5rem]";

  return (
    <div className="pb-28" {...(hideChrome ? {} : swipe)}>
      {!hideChrome && title ? (
        <AppHeader
          onMenuClick={() => setMenuOpen(true)}
          title={title}
        />
      ) : null}
      {children}
      {!hideChrome && showFab && role !== "lab" ? (
        <FabButton
          className={fabBottom}
          onClick={() => setCreateOpen(true)}
        />
      ) : null}
      {!hideChrome && showNotification ? (
        <NotificationFab
          className={notifBottom}
          onClick={() => setNotifOpen(true)}
        />
      ) : null}
      {!hideChrome ? <HomeTabNav /> : null}
      <BurgerDrawer onClose={() => setMenuOpen(false)} open={menuOpen} />
      <CreateActionSheet onClose={() => setCreateOpen(false)} open={createOpen} />
      <NotificationSheet onClose={() => setNotifOpen(false)} open={notifOpen} />
    </div>
  );
}
