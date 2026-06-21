from fastapi import FastAPI

app = FastAPI(title="PlotPin")


def get_storage():  # 占位,Task 5 起返回真正的 Storage,测试用依赖覆盖
    raise NotImplementedError


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
