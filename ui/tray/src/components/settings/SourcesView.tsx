import { useKnowledgeSync } from "../../hooks/useKnowledgeSync";
import { TYPE_LABEL } from "./SourceList";
import SourceList from "./SourceList";
import SourceForm from "./SourceForm";

export default function SourcesView() {
  const {
    loading,
    backendOk,
    syncing,
    showForm,
    form,
    formError,
    expandedId,
    filter,
    statusMessage,
    filtered,
    sources,
    setShowForm,
    setForm,
    setFormError,
    setExpandedId,
    setFilter,
    handleAddSource,
    handleRemove,
    handleSyncAll,
    handleSyncOne,
    handleExport,
    handleImport,
    formatTime,
    showMessage,
  } = useKnowledgeSync();

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-6 pt-5 pb-3 shrink-0">
        <div>
          <h1 className="text-[20px] font-bold text-on-surface">Knowledge Sources</h1>
          <p className="text-[11px] text-outline mt-0.5">
            Add links to RSS feeds, GitHub repos, or web pages
          </p>
        </div>
        <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold ${
          backendOk === null ? "text-outline" :
          backendOk ? "text-success-green bg-success-green/10" :
          "text-error bg-error/10"
        }`}>
          <div className={`w-2 h-2 rounded-full ${
            backendOk === null ? "bg-outline/50 animate-pulse" :
            backendOk ? "bg-success-green" : "bg-error"
          }`} />
          {backendOk === null ? "Connecting…" : backendOk ? "Connected" : "Offline"}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 pb-6 custom-scrollbar">
        {statusMessage && (
          <div className={`flex items-center gap-2 p-3 mb-4 rounded-[8px] text-[12px] font-medium ${
            statusMessage.ok ? "bg-success-green/10 text-success-green" : "bg-error/10 text-error"
          }`}>
            {statusMessage.ok ? (
              <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                <path d="M20 6L9 17l-5-5" />
              </svg>
            ) : (
              <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <circle cx="12" cy="12" r="10" />
                <path d="M12 8v4M12 16h.01" />
              </svg>
            )}
            {statusMessage.text}
            <button onClick={() => showMessage("", false)} className="ml-auto opacity-60 hover:opacity-100">
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        {/* Toolbar */}
        <div className="flex flex-wrap gap-2 mb-5">
          <button
            onClick={() => { setShowForm(!showForm); setFormError(null); }}
            className="flex items-center gap-1.5 px-4 py-2 rounded-[8px] text-[13px] font-semibold bg-primary-container text-on-surface hover:opacity-90 transition-opacity"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M12 5v14M5 12h14" />
            </svg>
            Add Link
          </button>

          <div className="flex gap-1 bg-surface-container-low rounded-[8px] p-0.5 border border-outline-variant/50">
            {(["all", "rss", "github", "web", "arxiv", "youtube", "pubmed"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1.5 rounded-[6px] text-[11px] font-semibold transition-colors ${
                  filter === f
                    ? "bg-surface-container text-on-surface"
                    : "text-outline hover:text-on-surface"
                }`}
              >
                {f === "all" ? "All" : TYPE_LABEL[f] || f}
              </button>
            ))}
          </div>

          <button
            onClick={() => void handleExport()}
            disabled={!backendOk}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-[8px] text-[12px] font-semibold transition-opacity ${
              backendOk
                ? "bg-surface-container-low border border-outline-variant text-outline hover:text-on-surface hover:bg-surface-container"
                : "bg-surface-container-low border border-outline-variant/30 text-outline/30 cursor-not-allowed"
            }`}
            title="Export sources"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" />
            </svg>
            Export
          </button>
          <button
            onClick={() => void handleImport()}
            disabled={!backendOk}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-[8px] text-[12px] font-semibold transition-opacity ${
              backendOk
                ? "bg-surface-container-low border border-outline-variant text-outline hover:text-on-surface hover:bg-surface-container"
                : "bg-surface-container-low border border-outline-variant/30 text-outline/30 cursor-not-allowed"
            }`}
            title="Import sources"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" />
            </svg>
            Import
          </button>

          <div className="flex-1" />

          <button
            onClick={() => void handleSyncAll()}
            disabled={syncing === "*" || !backendOk}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-[8px] text-[13px] font-semibold transition-opacity ${
              backendOk
                ? "bg-surface-container-low border border-outline-variant text-on-surface hover:bg-surface-container"
                : "bg-surface-container-low border border-outline-variant/30 text-outline/50 cursor-not-allowed"
            }`}
            title={!backendOk ? "Start the backend to sync" : "Sync all sources"}
          >
            {syncing === "*" ? (
              <span className="inline-block w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
            ) : (
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M21 12a9 9 0 11-9-9" />
                <path d="M21 3v6h-6" />
              </svg>
            )}
            Sync{!backendOk ? " (offline)" : ""}
          </button>
        </div>

        {showForm && (
          <SourceForm
            form={form}
            formError={formError}
            onChange={setForm}
            onSubmit={handleAddSource}
            onCancel={() => { setShowForm(false); setFormError(null); }}
          />
        )}

        <SourceList
          filtered={filtered}
          syncing={syncing}
          backendOk={backendOk}
          expandedId={expandedId}
          onSyncOne={handleSyncOne}
          onRemove={handleRemove}
          onExpand={setExpandedId}
          formatTime={formatTime}
          sources={sources}
          filter={filter}
          loading={loading}
        />
      </div>
    </div>
  );
}
