"use client";
import { useState } from "react";

const API = "http://localhost:8000";

export default function Home() {
  // Для проверки дрона
  const [serial, setSerial] = useState("");
  const [droneResult, setDroneResult] = useState<any>(null);
  const [droneLoading, setDroneLoading] = useState(false);

  // Для проверки прошивки
  const [droneType, setDroneType] = useState("");
  const [fwVersion, setFwVersion] = useState("");
  const [fwResult, setFwResult] = useState<any>(null);
  const [fwLoading, setFwLoading] = useState(false);

  const checkDrone = async () => {
    if (!serial.trim()) return;
    setDroneLoading(true);
    try {
      const res = await fetch(`${API}/certificate/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          check_type: "drone",
          serial_number: serial,
        }),
      });
      const data = await res.json();
      setDroneResult(data);
    } catch (err: any) {
      setDroneResult({ error: err.message });
    } finally {
      setDroneLoading(false);
    }
  };

  const checkFirmware = async () => {
    if (!droneType.trim() || !fwVersion.trim()) return;
    setFwLoading(true);
    try {
      const res = await fetch(`${API}/certificate/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          check_type: "firmware",
          drone_type: droneType,
          firmware_version: fwVersion,
        }),
      });
      const data = await res.json();
      setFwResult(data);
    } catch (err: any) {
      setFwResult({ error: err.message });
    } finally {
      setFwLoading(false);
    }
  };

  return (
    <main style={{ padding: "2rem", fontFamily: "monospace", maxWidth: 700, margin: "0 auto" }}>
      <h1>Регулятор — проверка сертификатов</h1>

      {/* Блок проверки дрона */}
      <div style={{ border: "1px solid #ccc", padding: "1rem", marginBottom: "2rem", borderRadius: 8 }}>
        <h2>Проверка сертификата дрона</h2>
        <input
          type="text"
          placeholder="Серийный номер (например, SN-001)"
          value={serial}
          onChange={(e) => setSerial(e.target.value)}
          style={{ width: "100%", padding: "0.5rem", marginBottom: "0.5rem" }}
        />
        <button onClick={checkDrone} disabled={droneLoading}>
          {droneLoading ? "Проверка..." : "Проверить"}
        </button>
        {droneResult && (
          <pre style={{ background: "#f4f4f4", padding: "0.5rem", marginTop: "1rem", overflow: "auto" }}>
            {JSON.stringify(droneResult, null, 2)}
          </pre>
        )}
      </div>

      {/* Блок проверки прошивки */}
      <div style={{ border: "1px solid #ccc", padding: "1rem", borderRadius: 8 }}>
        <h2>Проверка сертификата прошивки</h2>
        <input
          type="text"
          placeholder="Тип дрона (например, quad)"
          value={droneType}
          onChange={(e) => setDroneType(e.target.value)}
          style={{ width: "100%", padding: "0.5rem", marginBottom: "0.5rem" }}
        />
        <input
          type="text"
          placeholder="Версия прошивки (например, 1.0.0)"
          value={fwVersion}
          onChange={(e) => setFwVersion(e.target.value)}
          style={{ width: "100%", padding: "0.5rem", marginBottom: "0.5rem" }}
        />
        <button onClick={checkFirmware} disabled={fwLoading}>
          {fwLoading ? "Проверка..." : "Проверить"}
        </button>
        {fwResult && (
          <pre style={{ background: "#f4f4f4", padding: "0.5rem", marginTop: "1rem", overflow: "auto" }}>
            {JSON.stringify(fwResult, null, 2)}
          </pre>
        )}
      </div>
    </main>
  );
}
