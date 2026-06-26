export default function DashboardSkeleton() {
  return (
    <div className="flex-1 flex flex-col overflow-y-auto px-6 md:px-10 lg:px-12 pt-6 pb-8 animate-pulse">
      <div className="mb-8">
        <div className="h-8 w-48 bg-surface-container-high/30 rounded mb-2" />
        <div className="h-4 w-72 bg-surface-container-high/30 rounded" />
      </div>
      <div className="mb-6">
        <div className="h-20 w-full bg-surface-container-high/30 rounded-2xl" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-20 bg-surface-container-high/30 rounded-xl" />
        ))}
      </div>
      <div className="mb-8">
        <div className="h-3 w-36 bg-surface-container-high/30 rounded mb-3" />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {Array.from({ length: 2 }).map((_, i) => (
            <div key={i} className="h-20 bg-surface-container-high/30 rounded-xl" />
          ))}
        </div>
      </div>
      <div>
        <div className="h-3 w-36 bg-surface-container-high/30 rounded mb-3" />
        <div className="space-y-0">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-14 bg-surface-container-high/30 rounded-xl mb-1" />
          ))}
        </div>
      </div>
    </div>
  );
}
