from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from pydantic import BaseModel, Field
import re

from app.database import get_db
from app.models.term import Term
from app.api.chapters import verify_project_access # 复用项目权限验证
from app.logger import get_logger

router = APIRouter(prefix="/terms", tags=["百科词条管理"])
logger = get_logger(__name__)

# Pydantic Schemas
class TermCreate(BaseModel):
    project_id: str = Field(..., description="所属项目ID")
    name: str = Field(..., max_length=200, description="词条名称")
    description: Optional[str] = Field(None, description="词条详细描述")

class TermUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200, description="词条名称")
    description: Optional[str] = Field(None, description="词条详细描述")

class TermResponse(BaseModel):
    id: str
    project_id: str
    name: str
    description: Optional[str] = None
    created_by: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True

class TermListResponse(BaseModel):
    total: int
    items: List[TermResponse]

class AutoIdentifyRequest(BaseModel):
    content: str = Field(..., description="需要识别的文本内容")

class AutoIdentifyResponse(BaseModel):
    content: str
    identified_terms: List[str]
    count: int

# API Endpoints
@router.post("", response_model=TermResponse, summary="创建新词条")
async def create_term(
    term_create: TermCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")
    
    # 验证项目访问权限
    await verify_project_access(term_create.project_id, user_id, db)

    # 检查词条名称是否已存在于该项目下
    existing_term_result = await db.execute(
        select(Term).where(
            Term.project_id == term_create.project_id,
            Term.name == term_create.name
        )
    )
    if existing_term_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该项目下已存在同名词条")
    
    db_term = Term(
        project_id=term_create.project_id,
        name=term_create.name,
        description=term_create.description,
        created_by=user_id
    )
    db.add(db_term)
    await db.commit()
    await db.refresh(db_term)
    logger.info(f"词条创建成功: id={db_term.id}, name='{db_term.name}', project_id={db_term.project_id}")
    return db_term

@router.get("/project/{project_id}", response_model=TermListResponse, summary="获取项目所有词条")
async def get_project_terms(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000) # 限制单次获取数量，防止过大
):
    user_id = getattr(request.state, 'user_id', None)
    # 验证项目访问权限
    await verify_project_access(project_id, user_id, db)

    count_result = await db.execute(
        select(func.count(Term.id)).where(Term.project_id == project_id)
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(Term)
        .where(Term.project_id == project_id)
        .order_by(Term.name) # 按名称排序
        .offset(skip)
        .limit(limit)
    )
    terms = result.scalars().all()
    
    return TermListResponse(total=total, items=terms)

@router.get("/{term_id}", response_model=TermResponse, summary="获取单个词条详情")
async def get_term(
    term_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Term).where(Term.id == term_id))
    term = result.scalar_one_or_none()

    if not term:
        raise HTTPException(status_code=404, detail="词条不存在")
    
    user_id = getattr(request.state, 'user_id', None)
    # 验证项目访问权限
    await verify_project_access(term.project_id, user_id, db)
    
    return term

@router.put("/{term_id}", response_model=TermResponse, summary="更新词条")
async def update_term(
    term_id: str,
    term_update: TermUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Term).where(Term.id == term_id))
    term = result.scalar_one_or_none()

    if not term:
        raise HTTPException(status_code=404, detail="词条不存在")
    
    user_id = getattr(request.state, 'user_id', None)
    # 验证项目访问权限
    await verify_project_access(term.project_id, user_id, db)

    update_data = term_update.model_dump(exclude_unset=True)
    if "name" in update_data and update_data["name"] != term.name:
        # 如果名称更新，检查新名称是否已存在于该项目下
        existing_term_result = await db.execute(
            select(Term).where(
                Term.project_id == term.project_id,
                Term.name == update_data["name"]
            )
        )
        if existing_term_result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="该项目下已存在同名词条")

    for field, value in update_data.items():
        setattr(term, field, value)
    
    await db.commit()
    await db.refresh(term)
    logger.info(f"词条更新成功: id={term.id}, name='{term.name}'")
    return term

@router.delete("/{term_id}", summary="删除词条")
async def delete_term(
    term_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Term).where(Term.id == term_id))
    term = result.scalar_one_or_none()

    if not term:
        raise HTTPException(status_code=404, detail="词条不存在")
    
    user_id = getattr(request.state, 'user_id', None)
    # 验证项目访问权限
    await verify_project_access(term.project_id, user_id, db)

    await db.delete(term)
    await db.commit()
    logger.info(f"词条删除成功: id={term.id}, name='{term.name}'")
    return {"message": "词条删除成功"}

@router.post("/project/{project_id}/auto-identify", response_model=AutoIdentifyResponse, summary="自动识别并关联词条")
async def auto_identify_terms(
    project_id: str,
    identify_request: AutoIdentifyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    自动识别文本中的词条，并将其替换为 [[词条名称]] 格式
    """
    user_id = getattr(request.state, 'user_id', None)
    await verify_project_access(project_id, user_id, db)
    
    # 1. 获取项目所有词条
    result = await db.execute(
        select(Term).where(Term.project_id == project_id)
    )
    terms = result.scalars().all()
    
    if not terms:
        return AutoIdentifyResponse(
            content=identify_request.content,
            identified_terms=[],
            count=0
        )
    
    # 2. 按长度降序排序（优先匹配长词，如"虚空之剑"优先于"虚空"）
    sorted_terms = sorted(terms, key=lambda t: len(t.name), reverse=True)
    
    content = identify_request.content
    identified_terms = set()
    count = 0
    
    # 3. 遍历替换
    # 策略：先保护已有的 [[...]] 链接，避免重复替换
    existing_links = []
    def protect_link(match):
        existing_links.append(match.group(0))
        return f"__LINK_PLACEHOLDER_{len(existing_links)-1}__"
    
    # 保护已有的 [[wiki links]]
    protected_content = re.sub(r'\[\[.*?\]\]', protect_link, content)
    
    # 对每个词条进行替换
    for term in sorted_terms:
        # 使用 regex 转义
        pattern = re.escape(term.name)
        
        # 简单替换：不区分单词边界（中文），如果需要单词边界可以使用 r'\b' + pattern + r'\b'
        # 这里为了支持中文，直接匹配
        
        def replace_term(match):
            nonlocal count
            identified_terms.add(term.name)
            count += 1
            return f"[[{term.name}]]"
            
        # 替换逻辑
        protected_content, n = re.subn(pattern, replace_term, protected_content)
        
    # 4. 还原已有的链接
    def restore_link(match):
        index = int(match.group(1))
        return existing_links[index]
        
    final_content = re.sub(r'__LINK_PLACEHOLDER_(\d+)__', restore_link, protected_content)
    
    return AutoIdentifyResponse(
        content=final_content,
        identified_terms=list(identified_terms),
        count=count
    )
