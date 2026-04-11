(function () {
  const app = window.WebUI;
  const trackingMapElement = document.getElementById("tracking_map");
  if (!app || !trackingMapElement) {
    return;
  }

  const trackingState = {
    trackingDroneInput: document.getElementById("tracking_drone_id"),
    trackingStatusValue: document.getElementById("tracking_status_value"),
    trackingBatteryValue: document.getElementById("tracking_battery_value"),
    trackingLatValue: document.getElementById("tracking_lat_value"),
    trackingLonValue: document.getElementById("tracking_lon_value"),
    trackingAltValue: document.getElementById("tracking_alt_value"),
    trackingUpdatedValue: document.getElementById("tracking_updated_value"),
    trackingHint: document.getElementById("tracking_hint"),
    sitlMessageCount: document.getElementById("sitl_message_count"),
    sitlLastTopic: document.getElementById("sitl_last_topic"),
    sitlLastDrone: document.getElementById("sitl_last_drone"),
    sitlLastSeen: document.getElementById("sitl_last_seen"),
    sitlHint: document.getElementById("sitl_hint"),
    sitlMessagesBox: document.getElementById("sitl_messages_box")
  };

  const trackingMap = L.map("tracking_map", { zoomControl: true }).setView([55.751244, 37.618423], 14);
  const trackingLayer = L.layerGroup().addTo(trackingMap);
  const missionDroneInput = document.getElementById("drone_id");
  let telemetryPoll = null;
  let missionWatchPoll = null;
  let missionWatchDroneId = "";
  let trackingMarker = null;
  let trackingTrail = null;
  let trackingPositions = [];
  let missionFlightObserved = false;
  let landingRefreshSent = false;

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors"
  }).addTo(trackingMap);

  function syncDroneInputs() {
    const missionDroneId = (missionDroneInput?.value || "").trim();
    if (!trackingState.trackingDroneInput.dataset.userEdited) {
      trackingState.trackingDroneInput.value = missionDroneId;
    }
  }

  function stopTelemetryPolling() {
    if (telemetryPoll) {
      clearInterval(telemetryPoll);
      telemetryPoll = null;
    }
  }

  function stopMissionWatch() {
    if (missionWatchPoll) {
      clearInterval(missionWatchPoll);
      missionWatchPoll = null;
    }
    missionWatchDroneId = "";
  }

  function resetTrackingMap(message) {
    if (trackingMarker) {
      trackingLayer.removeLayer(trackingMarker);
      trackingMarker = null;
    }
    if (trackingTrail) {
      trackingLayer.removeLayer(trackingTrail);
      trackingTrail = null;
    }
    trackingPositions = [];
    if (message) {
      trackingState.trackingHint.textContent = message;
    }
  }

  function updateTrackingPanel(drone) {
    const position = drone?.last_position || {};
    trackingState.trackingStatusValue.textContent = drone?.status || "нет данных";
    trackingState.trackingBatteryValue.textContent = drone?.battery != null ? `${drone.battery}%` : "-";
    trackingState.trackingLatValue.textContent = position.latitude != null ? Number(position.latitude).toFixed(6) : "-";
    trackingState.trackingLonValue.textContent = position.longitude != null ? Number(position.longitude).toFixed(6) : "-";
    trackingState.trackingAltValue.textContent = position.altitude != null ? `${Number(position.altitude).toFixed(1)} м` : "-";
    trackingState.trackingUpdatedValue.textContent = drone?.updated_at || drone?.connected_at || "-";
  }

  function updateTrackingMap(drone) {
    const position = drone?.last_position;
    if (!position || position.latitude == null || position.longitude == null) {
      trackingState.trackingHint.textContent =
        "Телеметрия еще не содержит координат. Маркер появится после первого ответа от дрона.";
      return;
    }

    const latLng = [position.latitude, position.longitude];
    trackingState.trackingHint.textContent =
      "Карта показывает последнюю сохраненную позицию дрона и накопленный трек за текущую сессию.";

    if (!trackingMarker) {
      trackingMarker = L.marker(latLng).addTo(trackingLayer);
      trackingMarker.bindTooltip("Дрон", { direction: "top" });
    } else {
      trackingMarker.setLatLng(latLng);
    }

    const last = trackingPositions[trackingPositions.length - 1];
    if (!last || last[0] !== latLng[0] || last[1] !== latLng[1]) {
      trackingPositions.push(latLng);
    }

    if (trackingTrail) {
      trackingLayer.removeLayer(trackingTrail);
    }
    trackingTrail = L.polyline(trackingPositions, {
      color: "#58a6ff",
      weight: 3,
      opacity: 0.88
    }).addTo(trackingLayer);
  }

  function summarizeSitlMessage(entry) {
    const payload = entry?.message?.payload || entry?.message || {};
    const droneId =
      payload?.drone_id ||
      payload?.data?.drone_id ||
      payload?.payload?.drone_id ||
      payload?.target?.drone_id ||
      "-";
    return {
      topic: entry?.topic || "-",
      droneId,
      receivedAt: entry?.received_at || "-",
      raw: entry?.message || {}
    };
  }

  function updateSitlPanel(snapshot) {
    const messages = Array.isArray(snapshot?.observed_sitl_messages) ? snapshot.observed_sitl_messages : [];
    const lastEntry = messages[messages.length - 1];
    const last = lastEntry ? summarizeSitlMessage(lastEntry) : null;

    trackingState.sitlMessageCount.textContent = String(messages.length);
    trackingState.sitlLastTopic.textContent = last?.topic || "-";
    trackingState.sitlLastDrone.textContent = last?.droneId || "-";
    trackingState.sitlLastSeen.textContent = last?.receivedAt || "-";

    if (!messages.length) {
      trackingState.sitlHint.textContent =
        "Пока ничего не замечено. После отправки HOME, команд или telemetry-запросов панель обновится.";
      trackingState.sitlMessagesBox.textContent = "Нет сообщений SITL";
      return;
    }

    trackingState.sitlHint.textContent =
      "Панель показывает последние сообщения по SITL-топикам, которые наблюдает demo-клиент.";
    const lines = messages.slice(-6).reverse().map((entry) => {
      const item = summarizeSitlMessage(entry);
      return `[${item.receivedAt}] ${item.topic} drone=${item.droneId}\n${JSON.stringify(item.raw, null, 2)}`;
    });
    trackingState.sitlMessagesBox.textContent = lines.join("\n\n");
  }

  async function refreshSitlPanel(droneId) {
    try {
      const { response, data } = await app.requestJson("/api/action/snapshot", {
        body: { drone_id: droneId || (trackingState.trackingDroneInput.value || "").trim() || "drone-demo-1" }
      });

      if (!response.ok || !data.ok) {
        trackingState.sitlHint.textContent = data.error || "Не удалось получить snapshot SITL.";
        return;
      }

      updateSitlPanel(data.result || {});
    } catch (error) {
      trackingState.sitlHint.textContent = String(error);
    }
  }

  function updatePortRefreshState(drone, droneId) {
    const position = drone?.last_position || {};
    const altitude = Number(position.altitude);
    const hasAltitude = Number.isFinite(altitude);
    const isAirborne = (hasAltitude && altitude > 1) || drone?.status === "busy";

    if (isAirborne) {
      missionFlightObserved = true;
      landingRefreshSent = false;
      return;
    }

    if (!missionFlightObserved || landingRefreshSent) {
      return;
    }

    const isLanded = !hasAltitude || altitude <= 1;
    if (!isLanded) {
      return;
    }

    landingRefreshSent = true;
    missionFlightObserved = false;
    app.emit("port-state:changed", {
      reason: "mission-landed",
      droneId: droneId || trackingState.trackingDroneInput.value
    });
    stopMissionWatch();
  }

  async function pollMissionWatchDrone() {
    if (!missionWatchDroneId) {
      stopMissionWatch();
      return;
    }

    try {
      const { response, data } = await app.requestJson("/api/action/drone-state", {
        body: { drone_id: missionWatchDroneId }
      });

      if (!response.ok || !data.ok) {
        return;
      }

      const drone = data?.result?.payload?.drone || data?.result?.drone;
      if (!drone) {
        return;
      }

      updatePortRefreshState(drone, missionWatchDroneId);
    } catch (error) {
      // Background watcher should stay silent; UI errors belong to explicit user actions.
    }
  }

  function startMissionWatch(droneId) {
    const normalizedDroneId = String(droneId || "").trim();
    if (!normalizedDroneId) {
      return;
    }

    stopMissionWatch();
    missionWatchDroneId = normalizedDroneId;
    missionFlightObserved = false;
    landingRefreshSent = false;
    pollMissionWatchDrone();
    missionWatchPoll = setInterval(pollMissionWatchDrone, 2000);
  }

  async function refreshTracking(options = {}) {
    const droneId = (trackingState.trackingDroneInput.value || "").trim();
    if (!droneId) {
      trackingState.trackingHint.textContent = "Укажите ID дрона для отслеживания.";
      updateTrackingPanel(null);
      updateSitlPanel({});
      return;
    }

    try {
      const { response, data } = await app.requestJson("/api/action/drone-state", {
        body: { drone_id: droneId }
      });

      if (!response.ok || !data.ok) {
        trackingState.trackingHint.textContent = data.error || "Не удалось получить состояние дрона.";
        updateTrackingPanel(null);
        return;
      }

      const drone = data?.result?.payload?.drone || data?.result?.drone;
      if (!drone) {
        resetTrackingMap(
          `DroneStore пока не знает дрон "${droneId}". Проверьте ID и убедитесь, что миссия уже назначена и запущена.`
        );
        updateTrackingPanel(null);
        return;
      }

      updateTrackingPanel(drone);
      updateTrackingMap(drone);
      updatePortRefreshState(drone, droneId);
      refreshSitlPanel(droneId);

      if (options.center && drone.last_position) {
        trackingMap.setView(
          [drone.last_position.latitude, drone.last_position.longitude],
          Math.max(trackingMap.getZoom(), 15)
        );
      }
    } catch (error) {
      trackingState.trackingHint.textContent = String(error);
      updateTrackingPanel(null);
      refreshSitlPanel(droneId);
    }
  }

  function startTelemetryPolling() {
    stopTelemetryPolling();
    telemetryPoll = setInterval(() => {
      if (app.isPageActive("tracking_page")) {
        refreshTracking();
      }
    }, 2000);
  }

  trackingState.trackingDroneInput.addEventListener("input", () => {
    trackingState.trackingDroneInput.dataset.userEdited = "1";
  });

  if (missionDroneInput) {
    missionDroneInput.addEventListener("input", syncDroneInputs);
  }

  document.getElementById("tracking_refresh_btn").addEventListener("click", () => {
    refreshTracking({ center: true });
  });

  document.getElementById("tracking_center_btn").addEventListener("click", () => {
    const last = trackingPositions[trackingPositions.length - 1];
    if (last) {
      trackingMap.setView(last, Math.max(trackingMap.getZoom(), 15));
    } else {
      refreshTracking({ center: true });
    }
  });

  app.registerPageHandler("tracking_page", () => {
    setTimeout(() => {
      trackingMap.invalidateSize();
      syncDroneInputs();
      refreshTracking();
    }, 0);
    startTelemetryPolling();
  });

  ["flight_page", "schemes_page", "security_page", "dronoport_page", "status_page", "help_page"].forEach(
    (pageId) => {
      app.registerPageHandler(pageId, stopTelemetryPolling);
    }
  );

  app.on("mission-flight-watch:start", (payload) => {
    startMissionWatch(payload?.droneId || missionDroneInput?.value || trackingState.trackingDroneInput.value);
  });

  syncDroneInputs();
  setTimeout(() => trackingMap.invalidateSize(), 0);
})();
