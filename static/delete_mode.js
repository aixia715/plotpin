// issue 16：首页「测量记录」的编辑/删除模式。
// 点「编辑」进入选择态——行不再跳转，点击即高亮选中；选完点「删除」二次确认后提交。
(function () {
  var form = document.getElementById('delete-form');
  var editBtn = document.getElementById('log-edit');
  if (!form || !editBtn) return; // 无记录时没有编辑入口

  var log = document.getElementById('log');
  var actions = document.getElementById('log-actions');
  var backBtn = document.getElementById('log-back');
  var delBtn = document.getElementById('log-del');
  var selN = document.getElementById('sel-n');
  var confirmEl = document.getElementById('confirm');
  var confirmN = document.getElementById('confirm-n');
  var confirmOk = document.getElementById('confirm-ok');
  var confirmCancel = document.getElementById('confirm-cancel');

  function rows() {
    return Array.prototype.slice.call(log.querySelectorAll('.row[data-id]'));
  }
  function selectedIds() {
    return rows()
      .filter(function (r) { return r.classList.contains('selected'); })
      .map(function (r) { return r.getAttribute('data-id'); });
  }
  function editing() {
    return log.classList.contains('editing');
  }
  function refresh() {
    var n = selectedIds().length;
    selN.textContent = n;
    delBtn.disabled = n === 0;
  }

  function enterEdit() {
    log.classList.add('editing');
    editBtn.hidden = true;
    editBtn.setAttribute('aria-pressed', 'true');
    actions.hidden = false;
    rows().forEach(function (r) { r.setAttribute('tabindex', '0'); });
    refresh();
  }
  function exitEdit() {
    log.classList.remove('editing');
    rows().forEach(function (r) {
      r.classList.remove('selected');
      r.setAttribute('aria-pressed', 'false');
      r.removeAttribute('tabindex');
    });
    editBtn.hidden = false;
    editBtn.setAttribute('aria-pressed', 'false');
    actions.hidden = true;
    refresh();
  }
  function toggleRow(r) {
    var on = r.classList.toggle('selected');
    r.setAttribute('aria-pressed', on ? 'true' : 'false');
    refresh();
  }

  editBtn.addEventListener('click', enterEdit);
  backBtn.addEventListener('click', exitEdit);

  rows().forEach(function (r) {
    r.setAttribute('role', 'button');
    r.setAttribute('aria-pressed', 'false');
    // 编辑态下点击整行＝选中/取消；标题链接的跳转由 CSS pointer-events 关闭。
    r.addEventListener('click', function () {
      if (editing()) toggleRow(r);
    });
    r.addEventListener('keydown', function (e) {
      if (!editing()) return;
      if (e.key === ' ' || e.key === 'Enter') {
        e.preventDefault();
        toggleRow(r);
      }
    });
  });

  function onEscape(e) {
    if (e.key === 'Escape') closeConfirm();
  }
  function openConfirm() {
    var n = selectedIds().length;
    if (n === 0) return;
    confirmN.textContent = n;
    confirmEl.hidden = false;
    confirmOk.focus();
    document.addEventListener('keydown', onEscape);
  }
  function closeConfirm() {
    confirmEl.hidden = true;
    document.removeEventListener('keydown', onEscape);
    delBtn.focus();
  }

  delBtn.addEventListener('click', openConfirm);
  confirmCancel.addEventListener('click', closeConfirm);
  confirmEl.addEventListener('click', function (e) {
    if (e.target === confirmEl) closeConfirm(); // 点遮罩空白处关闭
  });
  confirmOk.addEventListener('click', function () {
    // 提交前把选中 id 注入表单，交给 POST /charts/delete。
    selectedIds().forEach(function (id) {
      var input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'ids';
      input.value = id;
      form.appendChild(input);
    });
    form.submit();
  });
})();
