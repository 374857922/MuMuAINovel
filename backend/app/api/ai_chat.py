from fastapi import APIRouter, Depends, HTTPException, Request, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import json

from app.database import get_db
from app.services.ai_service import AIService
from app.api.settings import get_user_ai_service
from app.utils.sse_response import create_sse_response
from app.logger import get_logger
from app.models.project import Project
from app.models.chapter import Chapter
from app.api.chapters import verify_project_access

router = APIRouter(prefix="/ai", tags=["AI助手"])
logger = get_logger(__name__)

class ChatRequest(BaseModel):
    project_id: str = Field(..., description="项目ID")
    chapter_id: Optional[str] = Field(None, description="当前章节ID")
    prompt: str = Field(..., description="用户输入的指令或问题")
    selected_text: Optional[str] = Field(None, description="用户在编辑器中选中的文本")
    context_text: Optional[str] = Field(None, description="编辑器中的上下文文本（如光标前后内容）")
    use_mcp: bool = Field(True, description="是否启用MCP工具增强")

@router.post("/chat", summary="AI写作助手对话")
async def chat_with_ai(
    request: Request,
    chat_req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user_ai_service: AIService = Depends(get_user_ai_service)
):
    """
    AI写作助手对话接口（支持流式响应）
    """
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")

    # 验证项目权限
    project = await verify_project_access(chat_req.project_id, user_id, db)
    
    # 获取章节信息（如果提供了chapter_id）
    chapter_info = ""
    if chat_req.chapter_id:
        result = await db.execute(select(Chapter).where(Chapter.id == chat_req.chapter_id))
        chapter = result.scalar_one_or_none()
        if chapter:
            chapter_info = f"当前章节：第{chapter.chapter_number}章 {chapter.title}\n"

    # 构建 System Prompt
    system_prompt = f"""你是一个专业的网文写作助手 (Copilot)。你的目标是辅助作者创作，提供灵感、润色文本或回答设定问题。

【项目信息】
书名：{project.title}
类型：{project.genre or '未设定'}
背景：{project.world_time_period or '未设定'} {project.world_location or '未设定'}

{chapter_info}

【重要规则】
1. 🎯 **精准执行**：只执行用户的具体指令。如果用户要求“润色”，就只输出润色后的段落，不要续写后续剧情。
2. 🚫 **严禁复读**：不要重复用户提供的【参考背景】内容。
3. ✂️ **范围控制**：如果提供了【待处理文本】，请仅对该文本进行操作。
4. 💡 **风格适配**：保持网文风格，生动、有画面感。
"""

    # 构建 User Prompt
    user_message = ""
    
    # 区分是否有选中文本
    if chat_req.selected_text:
        user_message += f"【待处理文本】\n{chat_req.selected_text}\n\n"
        # ⚠️ 如果有选中文本，不提供额外上下文，强制AI只处理选中部分
        # 移除了 context_text 的添加逻辑
    else:
        # 如果没有选中文本，上下文是续写的基础
        if chat_req.context_text:
            context_preview = chat_req.context_text[-2000:] if len(chat_req.context_text) > 2000 else chat_req.context_text
            user_message += f"【当前前文】\n...{context_preview}\n\n"
    
    user_message += f"【当前指令】\n{chat_req.prompt}"

    # 定义流式生成器
    async def event_generator():
        try:
            # 使用两阶段MCP生成（如果启用）
            # 这样可以让AI先查资料（如百科），再回答
            async for chunk in user_ai_service.generate_text_stream_with_mcp(
                prompt=user_message,
                user_id=user_id,
                db_session=db, # 注意：generate_text_stream_with_mcp 内部可能需要 db_session 来获取工具
                enable_mcp=chat_req.use_mcp,
                mcp_planning_prompt=None, # 使用默认规划提示
                system_prompt=system_prompt
            ):
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"
            
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            logger.error(f"AI Chat Error: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"

    return create_sse_response(event_generator())
