// 选好文件后再展开配置区(纯客户端 UX,不改变提交逻辑)
const fileInput = document.getElementById("file");
const config = document.getElementById("config");
const fileLabel = document.getElementById("file-label");

if (fileInput && config) {
  fileInput.addEventListener("change", () => {
    config.hidden = !fileInput.files.length;
    if (fileInput.files.length && fileLabel) {
      fileLabel.textContent = "▤ " + fileInput.files[0].name;
    }
  });

  // 点击 intake 区域触发文件选择
  const intake = document.querySelector(".intake");
  if (intake) {
    intake.addEventListener("click", (e) => {
      if (e.target !== fileInput) {
        fileInput.click();
      }
    });
  }
}
