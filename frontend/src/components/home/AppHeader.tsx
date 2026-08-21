"use client";

type Props = {
  title: string;
  onMenuClick?: () => void;
  /** When false, hide the burger menu (e.g. patient card with back only). */
  showMenu?: boolean;
  /** Optional left-side control shown after the menu (e.g. back on nested screens). */
  leading?: React.ReactNode;
  trailing?: React.ReactNode;
};

export default function AppHeader({
  title,
  onMenuClick,
  showMenu = true,
  leading,
  trailing,
}: Props) {
  return (
    <header className="sticky top-0 z-10 -mx-4 mb-4 flex items-center gap-3 border-b border-slate-100 bg-white/95 px-4 py-3 backdrop-blur dark:border-slate-800 dark:bg-slate-950/95 sm:-mx-6 sm:px-6">
      {showMenu ? (
        <button
          aria-label="Menu"
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-800 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
          onClick={onMenuClick}
          type="button"
        >
          <span className="text-lg leading-none">≡</span>
        </button>
      ) : null}
      {leading ? <div className="shrink-0">{leading}</div> : null}
      <h1 className="min-w-0 flex-1 truncate text-lg font-semibold text-slate-900 dark:text-slate-100">
        {title}
      </h1>
      {trailing ? <div className="shrink-0">{trailing}</div> : null}
    </header>
  );
}
