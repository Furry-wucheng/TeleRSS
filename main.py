from fastapi import FastAPI
import uvicorn
from scheduler.scheduler import lifespan
from utils.config_manager import get_config

# 初始化应用配置
app_config = {
    "title": "AutoNotice API",
    "description": "自动化推文通知服务",
    "version": "0.1.0"
}

app = FastAPI(**app_config,lifespan=lifespan)

@app.get("/")
async def root():
    """根路径，返回应用基本信息和配置状态"""
    base_type = get_config("base", "type", fallback="unknown")
    return {
        "message": "AutoNotice服务正在运行",
        "base_type": base_type,
        "status": "healthy"
    }


@app.get("/hello/{name}")
async def say_hello(name: str):
    """问候端点"""
    return {"message": f"Hello {name}"}



if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8000)