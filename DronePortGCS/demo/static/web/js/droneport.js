(function () {
  const app = window.WebUI;
  const container = document.getElementById("portMapContainer");
  if (!app || !container) {
    return;
  }

  let portStateDirty = false;
  let portsLoadedOnce = false;
  let healthLoadedOnce = false;

  function parsePortsData(data) {
    if (data?.payload?.ports) {
      data = data.payload.ports;
    }
    if (data?.result?.payload?.ports) {
      data = data.result.payload.ports;
    }

    const rawPorts = Array.isArray(data?.payload?.ports)
      ? data.payload.ports
      : Array.isArray(data)
        ? data
        : [];

    return rawPorts.map((port, index) => {
      const rawStatus = String(port.status || "").toLowerCase();
      const droneId = port.drone_id || port.drone?.id || "";
      const normalizedStatus = rawStatus === "free" || rawStatus === "available"
        ? "available"
        : "occupied";

      return {
        id: port.id || port.port_id || `port-${index + 1}`,
        status: normalizedStatus,
        drone: droneId
          ? {
              id: droneId,
              type: port.drone?.type || droneId
            }
          : port.drone || null,
        lat: port.lat,
        lon: port.lon
      };
    });
  }

  function updatePortStats(total, available, occupied) {
    document.getElementById("totalPorts").textContent = total;
    document.getElementById("availablePorts").textContent = available;
    document.getElementById("occupiedPorts").textContent = occupied;
  }

  function renderMapState(className, message) {
    container.className = "port-map-container";
    container.innerHTML = "";
    const state = document.createElement("div");
    state.className = className;
    state.textContent = message;
    container.appendChild(state);
  }

  function syncPortMapLayout(portCount) {
    container.className = "port-map-container";
    if (portCount <= 4) {
      container.classList.add("port-map-container--compact");
    }
  }

  function renderPortMap(portsData) {
    container.innerHTML = "";

    const ports = parsePortsData(portsData);
    if (ports.length === 0) {
      updatePortStats(0, 0, 0);
      renderMapState("port-map-empty", "Дронопорт вернул пустой список портов.");
      return;
    }

    syncPortMapLayout(ports.length);

    let availableCount = 0;
    let occupiedCount = 0;

    ports.forEach((port, index) => {
      const portElement = document.createElement("div");
      portElement.className = `port-item ${port.status}`;

      const statusIndicator = document.createElement("div");
      statusIndicator.className = `port-status-indicator ${port.status}`;
      portElement.appendChild(statusIndicator);

      if (port.status === "occupied") {
        occupiedCount += 1;
      } else if (port.status === "available") {
        availableCount += 1;
      }

      if (port.status === "occupied" && port.drone) {
        const droneRect = document.createElement("div");
        droneRect.className = "drone-rectangle";
        portElement.appendChild(droneRect);

        const droneTypeLabel = document.createElement("div");
        droneTypeLabel.className = "drone-type-label";
        droneTypeLabel.textContent = port.drone.type || "Unknown";
        portElement.appendChild(droneTypeLabel);
      }

      const portLabel = document.createElement("div");
      portLabel.className = "port-label";
      portLabel.textContent = `Порт ${port.id || index + 1}`;
      portElement.appendChild(portLabel);

      container.appendChild(portElement);
    });

    updatePortStats(ports.length, availableCount, occupiedCount);
  }

  async function loadDronePortStatus(button) {
    const healthText = document.getElementById("droneport_health_text");

    function setHealthState(kind, text) {
      healthText.className = "droneport-health-value";
      if (kind === "healthy") {
        healthText.classList.add("is-ok");
      } else if (kind === "degraded") {
        healthText.classList.add("is-warn");
      } else if (kind === "down") {
        healthText.classList.add("is-err");
      } else {
        healthText.classList.add("is-unknown");
      }
      healthText.textContent = text;
    }

    button.disabled = true;
    setHealthState("", "loading");

    try {
      const { response, data } = await app.requestJson("/api/action/drone-port-status");
      if (!response.ok || !data.ok) {
        setHealthState("unknown", "unknown");
        app.setStatus("err", "Ошибка статуса дронопорта");
        return;
      }

      const result = data.result || {};
      setHealthState(result.status || "down", result.status || "down");
      healthLoadedOnce = true;
      if (result.status === "healthy") {
        app.setStatus("ok", "DronePort healthy");
      } else if (result.status === "degraded") {
        app.setStatus("err", "DronePort degraded");
      } else {
        app.setStatus("err", "DronePort down");
      }
    } catch (error) {
      setHealthState("unknown", "unknown");
      app.setStatus("err", "Ошибка сети");
    } finally {
      button.disabled = false;
    }
  }

  async function loadPorts(button) {
    const output = document.getElementById("ports_status_display");
    if (button) {
      button.disabled = true;
    }
    if (output) {
      output.textContent = "Запрос статуса портов...";
    }
    renderMapState("port-map-loading", "Загрузка карты портов из Дронопорта...");

    try {
      const { response, data } = await app.requestJson("/api/action/ports-status");
      if (!response.ok || !data.ok) {
        if (output) {
          output.textContent = data.error || "Не удалось получить статус портов.";
        }
        updatePortStats(0, 0, 0);
        renderMapState("port-map-error", "Не удалось получить данные портов от Дронопорта.");
        app.setStatus("err", "Ошибка получения портов");
        return;
      }

      if (output) {
        app.displayJsonInBox("ports_status_display", data.result);
      }
      renderPortMap(data.result);
      portStateDirty = false;
      portsLoadedOnce = true;
      app.setStatus("ok", "Статус портов получен");
    } catch (error) {
      if (output) {
        output.textContent = String(error);
      }
      updatePortStats(0, 0, 0);
      renderMapState("port-map-error", "Ошибка сети при загрузке карты портов.");
      app.setStatus("err", "Ошибка сети");
    } finally {
      if (button) {
        button.disabled = false;
      }
    }
  }

  function markPortStateDirty() {
    portStateDirty = true;
    if (!app.isPageActive("dronoport_page")) {
      return;
    }
    loadPorts(document.getElementById("refresh_port_map_btn"));
  }

  const statusButton = document.getElementById("btn-droneport-status");
  const refreshMapButton = document.getElementById("refresh_port_map_btn");

  statusButton.addEventListener("click", () => loadDronePortStatus(statusButton));
  refreshMapButton.addEventListener("click", () => loadPorts(refreshMapButton));

  app.on("port-state:changed", markPortStateDirty);
  app.registerPageHandler("dronoport_page", () => {
    if (!healthLoadedOnce) {
      loadDronePortStatus(statusButton);
    }
    if (!portsLoadedOnce || portStateDirty) {
      loadPorts(refreshMapButton);
    }
  });
})();
