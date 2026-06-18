import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import StatusBar from "./StatusBar";
import { useSystemStore } from "../../stores/system";
import { useServicesStore } from "../../stores/services";

beforeEach(() => {
  useSystemStore.setState({
    status: {
      indexed_files: 100,
      engine_ok: true,
      model: "Qwen3.5-2B",
      provider: "llamacpp",
      active_agent: "auto",
      ram_pressure: "ok",
      ram_total_gb: 8,
      ram_used_gb: 4.2,
      ram_available_gb: 3.8,
      cpu_percent: 45,
      queries_total: 50,
      avg_latency_ms: 200,
      p95_latency_ms: 500,
      tool_call_count: 10,
      memory_hits: 20,
      provider_fallbacks: 0,
    },
    health: null,
    fleetStatus: null,
    swapEvent: null,
    lastRefreshed: null,
    error: null,
    pollingInterval: null,
  });
  useServicesStore.setState({
    starting: false,
    stopping: false,
    servicesOff: false,
    error: null,
  });
});

describe("StatusBar", () => {
  it("renders Cerebro OS label", () => {
    render(<StatusBar />);
    expect(screen.getByText("Cerebro OS")).toBeInTheDocument();
  });

  it("renders RAM usage", () => {
    render(<StatusBar />);
    expect(screen.getByText(/RAM 4.2\/8.0GB/)).toBeInTheDocument();
  });

  it("renders CPU percentage", () => {
    render(<StatusBar />);
    expect(screen.getByText(/CPU 45%/)).toBeInTheDocument();
  });

  it("does not render CPU when 0%", () => {
    useSystemStore.setState({
      status: {
        indexed_files: 0,
        engine_ok: true,
        model: "",
        provider: "",
        active_agent: "auto",
        ram_pressure: "ok",
        ram_total_gb: 8,
        ram_used_gb: 0,
        ram_available_gb: 8,
        cpu_percent: 0,
        queries_total: 0,
        avg_latency_ms: 0,
        p95_latency_ms: 0,
        tool_call_count: 0,
        memory_hits: 0,
        provider_fallbacks: 0,
      },
    });
    render(<StatusBar />);
    expect(screen.queryByText(/CPU/)).not.toBeInTheDocument();
  });

  it("has system status aria label", () => {
    render(<StatusBar />);
    expect(screen.getByLabelText("System status")).toBeInTheDocument();
  });
});
