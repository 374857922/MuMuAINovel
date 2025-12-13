import asyncio
import os
import sys
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from dotenv import load_dotenv

# 添加路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# 显式加载当前目录下的 .env 文件
env_path = os.path.join(current_dir, ".env")
if os.path.exists(env_path):
    print(f"Loading .env from: {env_path}")
    load_dotenv(env_path)
else:
    # 尝试在父目录查找
    parent_env = os.path.join(parent_dir, ".env")
    if os.path.exists(parent_env):
        print(f"Loading .env from: {parent_env}")
        load_dotenv(parent_env)
    else:
        print(f"Warning: .env file not found at {env_path} or {parent_env}")

from app.config import settings

async def check_schema():
    print("="*50)
    print("数据库结构检查工具")
    print("="*50)

    # 尝试多个连接 URL
    urls_to_try = [
        # 1. 当前 settings 中的配置 (通常是 app 运行时用的)
        (settings.database_url, "Settings Config"),
        
        # 2. Docker Compose 默认配置 (本地开发常用)
        ("postgresql+asyncpg://mumuai:123456@localhost:5432/mumuai_novel", "Docker Default (123456)"),
        
        # 3. 旧版默认配置
        ("postgresql+asyncpg://mumuai:password@localhost:5432/mumuai_novel", "Old Default (password)")
    ]

    connected_engine = None
    
    for url, label in urls_to_try:
        # 隐藏密码打印
        safe_url = url
        if ":" in url and "@" in url:
            try:
                part1 = url.split("://")[1]
                user_pass, rest = part1.split("@")
                if ":" in user_pass:
                    u, p = user_pass.split(":")
                    safe_url = f"postgresql+asyncpg://{u}:****@{rest}"
            except:
                pass
        
        print(f"\n尝试连接 [{label}]: {safe_url}")
        
        try:
            engine = create_async_engine(url, echo=False)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                print("✅ 连接成功！")
                connected_engine = engine
                break # 连接成功，跳出循环
        except Exception as e:
            print(f"❌ 连接失败: {str(e).split(']')[0]}... (Connect call failed)")
            await engine.dispose()
    
    if not connected_engine:
        print("\n❌ 所有连接尝试均失败。请检查：")
        print("1. 数据库服务是否启动？(docker ps)")
        print("2. 端口 5432 是否映射到本机？")
        print("3. 用户名/密码是否正确？")
        return

    # 检查表结构
    try:
        async with connected_engine.connect() as conn:
            print("\n正在检查 entity_snapshots 表...")
            try:
                # PostgreSQL
                result = await conn.execute(text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = 'entity_snapshots';"
                ))
                columns = [row[0] for row in result.fetchall()]
            except:
                # SQLite fallback
                result = await conn.execute(text("PRAGMA table_info(entity_snapshots);"))
                columns = [row[1] for row in result.fetchall()]
            
            print(f"当前字段列表: {columns}")
            
            missing = []
            if 'layer' not in columns:
                missing.append('layer')
            if 'source_type' not in columns:
                missing.append('source_type')
                
            if missing:
                print(f"\n❌ 严重警告: 缺少字段 {missing}")
                print("请务必执行 update_entity_layers.sql 脚本！")
                print("\n你可以使用以下命令手动修复(在数据库工具中):")
                print("ALTER TABLE entity_snapshots ADD COLUMN layer VARCHAR(50) DEFAULT 'Intrinsic';")
                print("ALTER TABLE entity_snapshots ADD COLUMN source_type VARCHAR(50) DEFAULT 'Narrator';")
            else:
                print("\n✅ 完美！数据库表结构已更新，包含 layer 和 source_type 字段。")
                
    finally:
        await connected_engine.dispose()

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(check_schema())