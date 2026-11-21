export default function GlobalLoading() {
  return (
    <div
      role="status"
      aria-live="polite"
      className="mx-auto max-w-6xl space-y-6 px-4 py-8 sm:px-6"
    >
      <div className="surface-solid h-36 animate-pulse rounded-3xl p-6" />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[1, 2, 3, 4].map((k) => (
          <div key={k} className="surface-solid h-28 animate-pulse rounded-2xl" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        <div className="surface-solid h-80 animate-pulse rounded-2xl lg:col-span-7" />
        <div className="surface-solid h-80 animate-pulse rounded-2xl lg:col-span-5" />
      </div>
      <span className="sr-only">กำลังโหลดข้อมูล...</span>
    </div>
  );
}
