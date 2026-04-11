(function () {
  const statusDot = document.getElementById("status_dot");
  const statusText = document.getElementById("status_text");
  const statusPageDot = document.getElementById("status_page_dot");
  const statusPageText = document.getElementById("status_page_text");
  const statusPageOutput = document.getElementById("status_page_output");
  const pageTitle = document.getElementById("current_page_title");
  const pageMeta = document.getElementById("current_page_meta");
  const droneportHeaderStatus = document.getElementById("droneport_header_status");
  const shell = document.getElementById("shell");
  const sidebarToggle = document.getElementById("sidebar_toggle");
  const menuLinks = Array.from(document.querySelectorAll("[data-page-target]"));
  const pages = Array.from(document.querySelectorAll(".page"));
  const pageHandlers = new Map();
  const eventHandlers = new Map();

  function setStatus(kind, text) {
    [statusDot, statusPageDot].forEach((node) => {
      if (!node) {
        return;
      }
      node.className = "status-dot";
      if (kind) {
        node.classList.add(kind);
      }
    });

    if (statusText) {
      statusText.textContent = text;
    }
    if (statusPageText) {
      statusPageText.textContent = text;
    }
  }

  function setOutputMessage(text) {
    if (statusPageOutput) {
      statusPageOutput.textContent = text;
    }
  }

  function safeStringify(data) {
    if (typeof data === "string") {
      return data;
    }
    return JSON.stringify(data, null, 2);
  }

  function displayJsonInBox(elementId, data) {
    const element = document.getElementById(elementId);
    if (!element) {
      return;
    }

    if (!data) {
      element.textContent = "Нет данных";
      return;
    }

    try {
      if (typeof data === "string") {
        try {
          element.textContent = JSON.stringify(JSON.parse(data), null, 2);
          return;
        } catch (error) {
          element.textContent = data;
          return;
        }
      }
      element.textContent = JSON.stringify(data, null, 2);
    } catch (error) {
      element.textContent = String(data);
    }
  }

  async function requestJson(url, options = {}) {
    const response = await fetch(url, {
      method: options.method || "POST",
      headers: options.body ? { "Content-Type": "application/json" } : {},
      body: options.body ? JSON.stringify(options.body) : undefined
    });

    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("text/html")) {
      throw new Error("Сервер вернул HTML вместо JSON. Возможно, произошла ошибка на сервере.");
    }

    const data = await response.json();
    return { response, data };
  }

  function registerPageHandler(pageId, handler) {
    if (!pageHandlers.has(pageId)) {
      pageHandlers.set(pageId, []);
    }
    pageHandlers.get(pageId).push(handler);
  }

  function triggerPageHandlers(pageId) {
    const handlers = pageHandlers.get(pageId) || [];
    handlers.forEach((handler) => handler());
  }

  function on(eventName, handler) {
    if (!eventHandlers.has(eventName)) {
      eventHandlers.set(eventName, []);
    }
    eventHandlers.get(eventName).push(handler);
  }

  function emit(eventName, payload) {
    const handlers = eventHandlers.get(eventName) || [];
    handlers.forEach((handler) => handler(payload));
  }

  function isPageActive(pageId) {
    return document.getElementById(pageId)?.classList.contains("active");
  }

  function syncPageMeta(activeLink) {
    if (!activeLink) {
      return;
    }
    if (pageTitle) {
      pageTitle.textContent = activeLink.dataset.pageTitle || activeLink.textContent.trim();
    }
    if (pageMeta) {
      pageMeta.textContent = activeLink.dataset.pageMeta || "";
    }
    if (droneportHeaderStatus) {
      droneportHeaderStatus.classList.toggle("is-hidden", activeLink.dataset.pageTarget !== "dronoport_page");
    }
  }

  function openPage(pageId) {
    pages.forEach((page) => {
      page.classList.toggle("active", page.id === pageId);
    });
    menuLinks.forEach((link) => {
      link.classList.toggle("active", link.dataset.pageTarget === pageId);
    });
    syncPageMeta(menuLinks.find((link) => link.dataset.pageTarget === pageId));
    triggerPageHandlers(pageId);
    emit("page:changed", { pageId });
  }

  function toggleSidebar() {
    shell?.classList.toggle("is-collapsed");
  }

  menuLinks.forEach((link) => {
    link.addEventListener("click", () => {
      openPage(link.dataset.pageTarget);
    });
  });

  sidebarToggle?.addEventListener("click", toggleSidebar);
  syncPageMeta(menuLinks.find((link) => link.classList.contains("active")));

  window.WebUI = {
    openPage,
    setStatus,
    setOutputMessage,
    safeStringify,
    displayJsonInBox,
    requestJson,
    registerPageHandler,
    isPageActive,
    on,
    emit
  };
})();
