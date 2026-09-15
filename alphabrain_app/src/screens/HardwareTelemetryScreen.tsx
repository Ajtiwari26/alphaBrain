import React, { useState, useEffect } from 'react';
import { HardwareTelemetry } from '../types';
import { mobileApi } from '../api/client';
import { Smartphone, Cpu, Battery, Gauge, Usb, CheckCircle2 } from 'lucide-react';

export const HardwareTelemetryScreen: React.FC = () => {
  const [telemetry, setTelemetry] = useState<HardwareTelemetry | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    mobileApi.getTelemetry().then((data) => {
      setTelemetry(data);
      setLoading(false);
    });
  }, []);

  if (loading || !telemetry) {
    return <div className="p-8 text-center text-muted font-mono text-xs">Querying host and USB telemetry...</div>;
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-card-border pb-4">
        <div>
          <span className="font-mono text-xs text-accent uppercase tracking-widest">10 // TELEMETRY</span>
          <h1 className="font-display text-2xl font-bold text-white tracking-tight mt-1">Hardware Sensors</h1>
        </div>
        <div className="flex items-center gap-1.5 font-mono text-xs text-emerald-400 bg-emerald-950 px-2 py-1 rounded border border-emerald-800">
          <Usb className="w-3.5 h-3.5" />
          <span>USB ATTACHED</span>
        </div>
      </div>

      {/* Target Device Highlight Card */}
      <div className="locomotive-card p-4 rounded-xl border border-accent/40 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Smartphone className="w-5 h-5 text-accent" />
            <div>
              <div className="font-display text-base font-bold text-white">{telemetry.usb_device_name}</div>
              <div className="font-mono text-xs text-muted">Serial: {telemetry.usb_device_serial}</div>
            </div>
          </div>
          <span className="font-mono text-xs px-2.5 py-1 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 font-semibold">
            READY
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2 pt-2 border-t border-card-border font-mono text-xs text-slate-300">
          <div>
            <span className="text-muted block text-[10px]">BATTERY</span>
            <span className="text-emerald-400 font-bold">{telemetry.battery_level_percent}% (Charging)</span>
          </div>
          <div>
            <span className="text-muted block text-[10px]">USB TRANSPORT</span>
            <span>Fastboot / ADB Mode</span>
          </div>
        </div>
      </div>

      {/* Host Metrics Card */}
      <div className="locomotive-card p-4 rounded-lg space-y-4">
        <span className="font-mono text-xs text-muted block">MACBOOK PRO HOST METRICS</span>

        {/* CPU Meter */}
        <div className="space-y-1 font-mono text-xs">
          <div className="flex justify-between text-slate-200">
            <span className="flex items-center gap-1.5"><Cpu className="w-3.5 h-3.5 text-accent" /> CPU Load</span>
            <span className="font-semibold">{telemetry.host_cpu_percent}%</span>
          </div>
          <div className="w-full bg-slate-900 rounded-full h-2 overflow-hidden border border-card-border">
            <div className="bg-accent h-full rounded-full transition-all duration-300" style={{ width: `${telemetry.host_cpu_percent}%` }} />
          </div>
        </div>

        {/* RAM Meter */}
        <div className="space-y-1 font-mono text-xs">
          <div className="flex justify-between text-slate-200">
            <span className="flex items-center gap-1.5"><Gauge className="w-3.5 h-3.5 text-accent-cyan" /> Memory Allocation</span>
            <span className="font-semibold">{telemetry.host_ram_used_gb} GB / {telemetry.host_ram_total_gb} GB ({telemetry.host_ram_percent}%)</span>
          </div>
          <div className="w-full bg-slate-900 rounded-full h-2 overflow-hidden border border-card-border">
            <div className="bg-accent-cyan h-full rounded-full transition-all duration-300" style={{ width: `${telemetry.host_ram_percent}%` }} />
          </div>
        </div>

        {/* Thermal Status */}
        <div className="flex items-center justify-between pt-2 border-t border-card-border font-mono text-xs">
          <span className="text-muted">THERMAL PRESSURE:</span>
          <span className="text-emerald-400 font-bold uppercase">{telemetry.thermal_pressure}</span>
        </div>
      </div>
    </div>
  );
};
