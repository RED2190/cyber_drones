(function () {
  const app = window.WebUI;
  const mapElement = document.getElementById("map");
  if (!app || !mapElement) {
    return;
  }

  const state = {
    metricDrone: document.getElementById("metric_drone"),
    metricMission: document.getElementById("metric_mission"),
    metricWaypoints: document.getElementById("metric_waypoints"),
    waypointList: document.getElementById("waypoint_list"),
    routeFields: document.getElementById("route_fields"),
    assignFields: document.getElementById("assign_fields"),
    routeActions: document.getElementById("route_actions"),
    assignActions: document.getElementById("assign_actions"),
    startActions: document.getElementById("start_actions"),
    afterStartActions: document.getElementById("after_start_actions"),
    flowHint: document.getElementById("flow_hint"),
    missionIdInput: document.getElementById("mission_id"),
    droneIdInput: document.getElementById("drone_id")
  };

  const defaultWaypoints = [
    { lat: 55.751244, lon: 37.618423, alt_m: 0.0 },
    { lat: 55.7509, lon: 37.6202, alt_m: 120.0 },
    { lat: 55.7524, lon: 37.622, alt_m: 120.0 }
  ];

  const map = L.map("map", { zoomControl: true }).setView([55.751244, 37.618423], 14);
  const routeLayer = L.layerGroup().addTo(map);
  let missionFlowStep = "submit";

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors"
  }).addTo(map);

  function syncMetrics() {
    state.metricDrone.textContent = missionFlowStep === "submit" ? "не задан" : (state.droneIdInput.value || "не задан");
    state.metricMission.textContent = state.missionIdInput.value || "не задана";
    state.metricWaypoints.textContent = String(state.waypointList.querySelectorAll(".waypoint-row").length || 0);
  }

  function setMissionFlow(step) {
    missionFlowStep = step;

    state.routeActions.classList.toggle("is-hidden", step !== "submit");
    state.assignActions.classList.toggle("is-hidden", step !== "assign");
    state.startActions.classList.toggle("is-hidden", step !== "start");
    state.afterStartActions.classList.toggle("is-hidden", step !== "after-start");

    state.routeFields.classList.toggle("is-hidden", step !== "submit");
    state.assignFields.classList.toggle("is-hidden", step === "submit" || step === "after-start");

    const routeLocked = step !== "submit";
    document.getElementById("add_waypoint_btn").disabled = routeLocked;
    state.waypointList.querySelectorAll("input, .waypoint-remove").forEach((element) => {
      element.disabled = routeLocked;
    });
    state.droneIdInput.readOnly = step !== "assign";

    if (step === "submit") {
      state.flowHint.textContent = "Шаг 1 из 4: настройте маршрут и отправьте миссию.";
    } else if (step === "assign") {
      state.flowHint.textContent = "Шаг 2 из 4: миссия создана. Назначьте ее на дрон.";
    } else if (step === "start") {
      state.flowHint.textContent = "Шаг 3 из 4: миссия назначена. Запустите ее, когда будете готовы.";
    } else if (step === "after-start") {
      state.flowHint.textContent = "Шаг 4 из 4: миссия запущена. Перейдите в раздел \"Дрон\", чтобы следить за телеметрией.";
    }

    syncMetrics();
  }

  function tryFillMissionId(data) {
    const missionId =
      data?.result?.payload?.mission_id ||
      data?.result?.payload?.mission?.mission_id ||
      data?.result?.mission?.payload?.mission?.mission_id ||
      data?.result?.mission?.payload?.mission_id ||
      data?.result?.payload?.mission?.mission_id;

    if (missionId && !state.missionIdInput.value) {
      state.missionIdInput.value = missionId;
      syncMetrics();
    }
  }

  function collectWaypoints(options = {}) {
    const rows = Array.from(state.waypointList.querySelectorAll(".waypoint-row"));
    const waypoints = rows.map((row, index) => {
      const lat = Number(row.querySelector(".waypoint-lat").value);
      const lon = Number(row.querySelector(".waypoint-lon").value);
      const altM = Number(row.querySelector(".waypoint-alt").value);

      if ([lat, lon, altM].some((value) => Number.isNaN(value))) {
        throw new Error(`Точка ${index + 1} содержит некорректные координаты`);
      }

      return { lat, lon, alt_m: altM };
    });

    if (!waypoints.length && !options.silent) {
      throw new Error("Нужна хотя бы одна точка маршрута");
    }

    return waypoints;
  }

  function updateMapFromWaypoints(waypoints) {
    routeLayer.clearLayers();
    if (!waypoints.length) {
      return;
    }

    const latLngs = waypoints.map((waypoint) => [waypoint.lat, waypoint.lon]);
    L.polyline(latLngs, { color: "#58a6ff", weight: 3, opacity: 0.9 }).addTo(routeLayer);

    waypoints.forEach((waypoint, index) => {
      const marker = L.marker([waypoint.lat, waypoint.lon], { draggable: true }).addTo(routeLayer);
      marker.bindTooltip(`Точка ${index + 1}<br>Высота ${waypoint.alt_m}`, { direction: "top" });
      marker.on("dragend", (event) => {
        if (missionFlowStep !== "submit") {
          return;
        }
        const point = event.target.getLatLng();
        const row = state.waypointList.querySelectorAll(".waypoint-row")[index];
        if (!row) {
          return;
        }
        row.querySelector(".waypoint-lat").value = point.lat.toFixed(6);
        row.querySelector(".waypoint-lon").value = point.lng.toFixed(6);
        refreshRoute();
      });
    });
  }

  function fitRoute() {
    const waypoints = collectWaypoints({ silent: true });
    if (!waypoints.length) {
      return;
    }
    const bounds = L.latLngBounds(waypoints.map((waypoint) => [waypoint.lat, waypoint.lon]));
    map.fitBounds(bounds.pad(0.2));
  }

  function refreshRoute(options = {}) {
    const waypoints = collectWaypoints({ silent: true });
    updateMapFromWaypoints(waypoints);
    syncMetrics();
    if (options.fit && waypoints.length) {
      fitRoute();
    }
  }

  function reindexWaypoints() {
    state.waypointList.querySelectorAll(".waypoint-row").forEach((row, index) => {
      row.querySelector(".waypoint-index").textContent = index + 1;
    });
  }

  function renderWaypoints(waypoints) {
    state.waypointList.innerHTML = "";
    waypoints.forEach((waypoint, index) => {
      const row = document.createElement("div");
      row.className = "waypoint-row";
      row.innerHTML = `
        <div class="waypoint-index">${index + 1}</div>
        <div class="field">
          <label>Широта</label>
          <input class="waypoint-lat" type="number" step="0.000001" value="${waypoint.lat}">
        </div>
        <div class="field">
          <label>Долгота</label>
          <input class="waypoint-lon" type="number" step="0.000001" value="${waypoint.lon}">
        </div>
        <div class="field">
          <label>Высота</label>
          <input class="waypoint-alt" type="number" step="0.1" value="${waypoint.alt_m}">
        </div>
        <button class="ghost waypoint-remove" type="button">Убрать</button>
      `;

      row.querySelector(".waypoint-remove").addEventListener("click", () => {
        if (state.waypointList.children.length <= 1) {
          app.setStatus("err", "Маршрут пуст");
          app.setOutputMessage("В маршруте должна остаться хотя бы одна точка.");
          return;
        }
        row.remove();
        reindexWaypoints();
        refreshRoute({ fit: true });
      });

      row.querySelectorAll("input").forEach((input) => {
        input.addEventListener("input", () => refreshRoute());
      });

      state.waypointList.appendChild(row);
    });
    refreshRoute();
  }

  function appendWaypoint(waypoint = { lat: 55.752, lon: 37.621, alt_m: 120.0 }) {
    const existing = collectWaypoints({ silent: true });
    existing.push(waypoint);
    renderWaypoints(existing);
    fitRoute();
  }

  async function callApi(action, options = {}) {
    const method = options.method || "POST";
    const label = options.label || action;
    const button = options.button;

    if (button) {
      button.disabled = true;
    }

    app.setStatus("", `Выполняется: ${label}`);
    app.setOutputMessage("Выполняю запрос...");

    try {
      const { response, data } = await app.requestJson(`/api/action/${action}`, {
        method,
        body: options.body
      });

      tryFillMissionId(data);

      if (!response.ok || !data.ok) {
        app.setStatus("err", `Ошибка: ${label}`);
        app.setOutputMessage(data.traceback || data.error || app.safeStringify(data));
        return;
      }

      if (action === "submit-task") {
        setMissionFlow("assign");
      } else if (action === "assign-task") {
        setMissionFlow("start");
      } else if (action === "start-task") {
        setMissionFlow("after-start");
        app.emit("mission-flight-watch:start", {
          droneId: state.droneIdInput.value
        });
        window.setTimeout(() => {
          app.emit("port-state:changed", {
            reason: "mission-started",
            droneId: state.droneIdInput.value
          });
        }, 1500);
      }

      app.setStatus("ok", `Готово: ${label}`);
      app.setOutputMessage(data.result_text || app.safeStringify(data.result));
    } catch (error) {
      app.setStatus("err", `Ошибка сети: ${label}`);
      app.setOutputMessage(String(error));
    } finally {
      if (button) {
        button.disabled = false;
      }
    }
  }

  document.getElementById("add_waypoint_btn").addEventListener("click", () => appendWaypoint());
  document.getElementById("fit_route_btn").addEventListener("click", fitRoute);
  document.getElementById("clear_route_btn").addEventListener("click", () => {
    renderWaypoints(defaultWaypoints);
    fitRoute();
  });

  document.getElementById("submit_task_btn").addEventListener("click", (event) => {
    try {
      const waypoints = collectWaypoints();
      callApi("submit-task", {
        label: "Отправить миссию",
        button: event.currentTarget,
        body: { waypoints }
      });
    } catch (error) {
      app.setStatus("err", "Некорректные точки");
      app.setOutputMessage(String(error));
    }
  });

  document.getElementById("assign_task_btn").addEventListener("click", (event) => {
    callApi("assign-task", {
      label: "Назначить миссию",
      button: event.currentTarget,
      body: {
        mission_id: state.missionIdInput.value,
        drone_id: state.droneIdInput.value
      }
    });
  });

  document.getElementById("start_task_btn").addEventListener("click", (event) => {
    callApi("start-task", {
      label: "Запустить миссию",
      button: event.currentTarget,
      body: {
        mission_id: state.missionIdInput.value,
        drone_id: state.droneIdInput.value
      }
    });
  });

  ["get_mission_btn", "get_mission_after_assign_btn"].forEach((id) => {
    document.getElementById(id).addEventListener("click", (event) => {
      callApi("mission", {
        label: "Получить миссию",
        button: event.currentTarget,
        body: { mission_id: state.missionIdInput.value }
      });
    });
  });

  document.getElementById("track_external_btn").addEventListener("click", () => {
    app.openPage("tracking_page");
    app.setStatus("", "Телеметрия дрона");
    app.setOutputMessage("Открыта страница телеметрии. Карта будет обновляться по мере поступления данных.");
  });

  document.getElementById("restart_flow_btn").addEventListener("click", () => {
    state.missionIdInput.value = "";
    state.droneIdInput.value = "";
    renderWaypoints(defaultWaypoints);
    setMissionFlow("submit");
    app.setStatus("", "Сценарий сброшен");
    app.setOutputMessage("Сценарий сброшен. Постройте новый маршрут и отправьте миссию снова.");
  });

  document.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", () => {
      callApi(button.dataset.action, {
        method: button.dataset.method || "POST",
        label: button.textContent.trim(),
        button
      });
    });
  });

  const refreshStatusButton = document.getElementById("refresh_status_btn");
  if (refreshStatusButton) {
    refreshStatusButton.addEventListener("click", (event) => {
      callApi("ps", {
        method: "GET",
        label: "Обновить состояние",
        button: event.currentTarget
      });
    });
  }

  map.on("click", (event) => {
    if (missionFlowStep !== "submit") {
      app.setStatus("err", "Маршрут зафиксирован");
      app.setOutputMessage(
        "Маршрут можно редактировать только до отправки миссии. Используйте кнопку \"Начать Сначала\", чтобы собрать новую миссию."
      );
      return;
    }
    appendWaypoint({
      lat: Number(event.latlng.lat.toFixed(6)),
      lon: Number(event.latlng.lng.toFixed(6)),
      alt_m: 120.0
    });
  });

  app.registerPageHandler("flight_page", () => {
    setTimeout(() => map.invalidateSize(), 0);
  });

  renderWaypoints(defaultWaypoints);
  setMissionFlow("submit");
  app.setOutputMessage("Панель готова. Начните с построения маршрута и отправки миссии.");
  setTimeout(() => {
    map.invalidateSize();
    fitRoute();
  }, 0);
})();
