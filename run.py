#!/usr/bin/env python
"""
AI Meeting Router - 本地多智能体讨论系统

启动此脚本运行项目。默认访问地址: http://127.0.0.1:8000
"""

if __name__ == "__main__":
    import uvicorn
    from app.main import app
    
    print("\n" + "=" * 60)
    print("AI Meeting Router - 启动中...")
    print("=" * 60)
    print("\n访问地址:")
    print("  - 主页:      http://127.0.0.1:8000/")
    print("  - 讨论:      http://127.0.0.1:8000/discuss")
    print("  - 配置:      http://127.0.0.1:8000/config")
    print("  - API 文档:  http://127.0.0.1:8000/docs")
    print("\n按 Ctrl+C 停止服务器\n")
    
    uvicorn.run(app, host="127.0.0.1", port=8000)
