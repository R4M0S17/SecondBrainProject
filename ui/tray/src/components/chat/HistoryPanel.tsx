import { useEffect } from "react";
import { useHistoryStore } from "../../stores/history";

export default function HistoryPanel() {
  const {
    conversations,
    activeConvId,
    activeConv,
    isLoading,
    loadList,
    loadConversation,
    setActiveConvId,
  } = useHistoryStore();

  useEffect(() => {
    void loadList();
  }, [loadList]);

  return (
    <div className="flex h-full overflow-hidden">
      {/* Sidebar — conversation list */}
      <div className="w-56 shrink-0 border-r border-[#242736] flex flex-col overflow-hidden">
        <div className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-[#8b8fa8]">
          History
        </div>
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          {isLoading && conversations.length === 0 && (
            <p className="px-3 py-2 text-[13px] text-[#8b8fa8]">Loading…</p>
          )}
          {!isLoading && conversations.length === 0 && (
            <p className="px-3 py-2 text-[13px] text-[#8b8fa8]">No past conversations.</p>
          )}
          {conversations.map((conv) => (
            <button
              key={conv.conv_id}
              onClick={() => void loadConversation(conv.conv_id)}
              className={`w-full text-left px-3 py-2 border-b border-[#1a1921] transition-colors hover:bg-[#242736] ${
                activeConvId === conv.conv_id ? "bg-[#242736]" : ""
              }`}
            >
              <p className="text-[13px] text-[#e5e0ed] truncate">
                {conv.first_user_message || "Empty conversation"}
              </p>
              <p className="text-[11px] text-[#8b8fa8] mt-0.5">
                {conv.agent_id} · {conv.message_count} msgs
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Main area — conversation detail */}
      <div className="flex-1 overflow-y-auto custom-scrollbar px-4 py-3">
        {!activeConv && !isLoading && (
          <p className="text-[13px] text-[#8b8fa8]">Select a conversation to view.</p>
        )}
        {isLoading && activeConvId && (
          <p className="text-[13px] text-[#8b8fa8]">Loading…</p>
        )}
        {activeConv && (
          <>
            <div className="flex items-center justify-between mb-3">
              <span className="text-[11px] text-[#8b8fa8]">
                {activeConv.agent_id} · {activeConv.messages.length} messages
              </span>
              <button
                onClick={() => setActiveConvId(null)}
                className="text-[11px] text-[#8b8fa8] hover:text-[#e5e0ed] transition-colors"
              >
                Close
              </button>
            </div>
            <div className="flex flex-col gap-2">
              {activeConv.messages.map((msg, i) => (
                <div
                  key={i}
                  className={`flex flex-col gap-0.5 ${
                    msg.role === "user" ? "items-end" : "items-start"
                  }`}
                >
                  <span className="text-[11px] text-[#8b8fa8]">
                    {msg.role === "user" ? "You" : "Cerebro"}
                  </span>
                  <div
                    className={`max-w-[80%] rounded px-3 py-2 text-[13px] leading-relaxed whitespace-pre-wrap ${
                      msg.role === "user"
                        ? "bg-[#2e2d3a] text-[#e5e0ed]"
                        : "bg-[#1a1921] text-[#e5e0ed]"
                    }`}
                  >
                    {msg.content}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
