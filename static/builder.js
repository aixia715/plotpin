// 读 CSV 首行表头 → 生成面板分配 UI → 提交前拼出 layout JSON。
// 无 JS / 读表头失败时优雅降级为「单面板、全部曲线」。
const fileInput = document.getElementById("file");
const config = document.getElementById("config");
const fileLabel = document.getElementById("file-label");
const builder = document.getElementById("builder");
const hint = document.getElementById("builder-hint");
const layoutField = document.getElementById("layout");
const form = document.getElementById("upload-form");

let columns = [];      // Y 列名（首行去掉第一列）
let panelCount = 1;

function readHeader(file) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => {
      const firstLine = String(reader.result).split(/\r?\n/)[0] || "";
      const cells = firstLine.split(",").map((s) => s.trim());
      resolve(cells.slice(1)); // 第一列是 X
    };
    reader.onerror = () => resolve([]);
    reader.readAsText(file.slice(0, 64 * 1024)); // 只读前 64KB 足够拿表头
  });
}

function render() {
  if (!columns.length) {
    builder.innerHTML = '<p class="hint">未能读取列名，将按单面板（全部曲线）生成。</p>';
    return;
  }
  let html = '<div class="panel-count">面板数：' +
    '<button type="button" class="pc-dec">−</button>' +
    '<span class="pc-val">' + panelCount + "</span>" +
    '<button type="button" class="pc-inc">+</button></div>';

  html += '<table class="assign"><thead><tr><th>曲线</th><th>分配</th></tr></thead><tbody>';
  for (const col of columns) {
    html += '<tr><td>' + escapeHtml(col) + '</td><td><select data-col="' + escapeHtml(col) + '">';
    for (let i = 0; i < panelCount; i++) {
      html += '<option value="' + i + '">面板' + (i + 1) + "</option>";
    }
    html += '<option value="hidden">不显示</option></select></td></tr>';
  }
  html += "</tbody></table>";

  html += '<div class="panel-cfgs">';
  for (let i = 0; i < panelCount; i++) {
    html += '<div class="panel-cfg" data-panel="' + i + '">' +
      '<div class="ax">面板' + (i + 1) + ' Y 轴</div>' +
      '<input type="text" class="p-title" placeholder="Y 轴标题">' +
      '<label><input type="checkbox" class="p-eng" checked> 工程计数法</label>' +
      '<label><input type="checkbox" class="p-log"> 对数坐标</label></div>';
  }
  html += "</div>";

  builder.innerHTML = html;
  builder.querySelector(".pc-dec").addEventListener("click", () => {
    if (panelCount > 1) { panelCount--; render(); }
  });
  builder.querySelector(".pc-inc").addEventListener("click", () => {
    panelCount++; render();
  });
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function buildLayout() {
  // 降级：无列名时单面板、全部曲线归面板 0
  if (!columns.length) {
    return { panels: [{ y_title: "Y", y_eng: true, y_log: false }], assign: {} };
  }
  const assign = {};
  builder.querySelectorAll("select[data-col]").forEach((sel) => {
    const v = sel.value;
    assign[sel.dataset.col] = v === "hidden" ? null : parseInt(v, 10);
  });
  const panels = [];
  builder.querySelectorAll(".panel-cfg").forEach((cfg) => {
    panels.push({
      y_title: cfg.querySelector(".p-title").value || "Y",
      y_eng: cfg.querySelector(".p-eng").checked,
      y_log: cfg.querySelector(".p-log").checked,
    });
  });
  return { panels, assign };
}

if (fileInput && config) {
  fileInput.addEventListener("change", async () => {
    config.hidden = !fileInput.files.length;
    if (fileInput.files.length) {
      if (fileLabel) fileLabel.textContent = "▤ " + fileInput.files[0].name;
      columns = await readHeader(fileInput.files[0]);
      panelCount = 1;
      render();
    }
  });

  const intake = document.querySelector(".intake");
  if (intake) {
    intake.addEventListener("click", (e) => {
      if (e.target.closest(".pick")) return;
      fileInput.click();
    });
  }
}

if (form) {
  form.addEventListener("submit", () => {
    layoutField.value = JSON.stringify(buildLayout());
  });
}
