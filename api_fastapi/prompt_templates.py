"""
Prompt Templates API 路由
處理 AI 分析模板的 CRUD 操作
"""
import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from models import get_async_db_session, PromptTemplate, User
from api_fastapi.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


class PromptTemplateCreate(BaseModel):
    """創建提示模板的請求模型"""
    name: str
    description: Optional[str] = None
    prompt: str


class PromptTemplateUpdate(BaseModel):
    """更新提示模板的請求模型"""
    name: Optional[str] = None
    description: Optional[str] = None
    prompt: Optional[str] = None


class PromptTemplateResponse(BaseModel):
    """提示模板響應模型"""
    id: int
    name: str
    description: Optional[str]
    prompt: str
    is_system_template: bool
    is_user_default: bool
    user_id: Optional[str]
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True


@router.get("/", response_model=List[PromptTemplateResponse])
async def get_prompt_templates(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """
    獲取用戶可用的所有模板
    包括：系統模板 + 用戶自定義模板
    """
    logger.info(f"獲取模板列表請求 - 用戶: {current_user.username if current_user else 'Unknown'}")
    try:
        # 查詢系統模板或屬於當前用戶的模板
        query = select(PromptTemplate).where(
            or_(
                PromptTemplate.is_system_template == True,
                PromptTemplate.user_id == current_user.id
            )
        ).order_by(
            PromptTemplate.is_system_template.desc(),
            PromptTemplate.is_user_default.desc(),
            PromptTemplate.created_at.desc()
        )
        
        result = await db.execute(query)
        templates = result.scalars().all()
        
        return [
            PromptTemplateResponse(
                id=template.id,
                name=template.name,
                description=template.description,
                prompt=template.prompt,
                is_system_template=template.is_system_template,
                is_user_default=template.is_user_default,
                user_id=str(template.user_id) if template.user_id else None,
                created_at=template.created_at.isoformat(),
                updated_at=template.updated_at.isoformat()
            )
            for template in templates
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"獲取模板列表失敗: {str(e)}"
        )


@router.post("/", response_model=PromptTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt_template(
    template_data: PromptTemplateCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """創建新的提示模板"""
    try:
        # 檢查是否已經存在同名模板（用戶範圍內）
        existing_query = select(PromptTemplate).where(
            and_(
                PromptTemplate.user_id == current_user.id,
                PromptTemplate.name == template_data.name
            )
        )
        existing_result = await db.execute(existing_query)
        if existing_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="已存在同名的模板"
            )
        
        # 創建新模板
        new_template = PromptTemplate(
            name=template_data.name,
            description=template_data.description,
            prompt=template_data.prompt,
            is_system_template=False,
            is_user_default=False,
            user_id=current_user.id
        )
        
        db.add(new_template)
        await db.commit()
        await db.refresh(new_template)
        
        return PromptTemplateResponse(
            id=new_template.id,
            name=new_template.name,
            description=new_template.description,
            prompt=new_template.prompt,
            is_system_template=new_template.is_system_template,
            is_user_default=new_template.is_user_default,
            user_id=str(new_template.user_id) if new_template.user_id else None,
            created_at=new_template.created_at.isoformat(),
            updated_at=new_template.updated_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"創建模板失敗: {str(e)}"
        )


@router.put("/{template_id}", response_model=PromptTemplateResponse)
async def update_prompt_template(
    template_id: int,
    template_data: PromptTemplateUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """更新提示模板"""
    try:
        # 查詢模板
        query = select(PromptTemplate).where(PromptTemplate.id == template_id)
        result = await db.execute(query)
        template = result.scalar_one_or_none()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="模板不存在"
            )
        
        # 檢查權限：系統模板不能修改，只能修改自己的模板
        if template.is_system_template:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="系統模板不能修改"
            )
        
        if template.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="無權修改此模板"
            )
        
        # 更新模板
        if template_data.name is not None:
            # 檢查新名稱是否與其他模板衝突
            name_check_query = select(PromptTemplate).where(
                and_(
                    PromptTemplate.user_id == current_user.id,
                    PromptTemplate.name == template_data.name,
                    PromptTemplate.id != template_id
                )
            )
            name_check_result = await db.execute(name_check_query)
            if name_check_result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="已存在同名的模板"
                )
            template.name = template_data.name
            
        if template_data.description is not None:
            template.description = template_data.description
            
        if template_data.prompt is not None:
            template.prompt = template_data.prompt
        
        await db.commit()
        await db.refresh(template)
        
        return PromptTemplateResponse(
            id=template.id,
            name=template.name,
            description=template.description,
            prompt=template.prompt,
            is_system_template=template.is_system_template,
            is_user_default=template.is_user_default,
            user_id=str(template.user_id) if template.user_id else None,
            created_at=template.created_at.isoformat(),
            updated_at=template.updated_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新模板失敗: {str(e)}"
        )


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """刪除提示模板"""
    try:
        # 查詢模板
        query = select(PromptTemplate).where(PromptTemplate.id == template_id)
        result = await db.execute(query)
        template = result.scalar_one_or_none()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="模板不存在"
            )
        
        # 檢查權限：系統模板不能刪除，只能刪除自己的模板
        if template.is_system_template:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="系統模板不能刪除"
            )
        
        if template.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="無權刪除此模板"
            )
        
        # 如果這是用戶的默認模板，先取消默認狀態
        if template.is_user_default:
            template.is_user_default = False
            await db.commit()
        
        # 刪除模板
        await db.delete(template)
        await db.commit()
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"刪除模板失敗: {str(e)}"
        )


@router.put("/{template_id}/set-default", response_model=PromptTemplateResponse)
async def set_default_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """設置默認模板"""
    try:
        # 查詢模板
        query = select(PromptTemplate).where(PromptTemplate.id == template_id)
        result = await db.execute(query)
        template = result.scalar_one_or_none()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="模板不存在"
            )
        
        # 檢查權限：只能設置系統模板或自己的模板為默認
        if not template.is_system_template and template.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="無權設置此模板為默認"
            )
        
        # 取消當前用戶所有模板的默認狀態
        update_query = select(PromptTemplate).where(
            and_(
                PromptTemplate.user_id == current_user.id,
                PromptTemplate.is_user_default == True
            )
        )
        update_result = await db.execute(update_query)
        current_defaults = update_result.scalars().all()
        
        for default_template in current_defaults:
            default_template.is_user_default = False
        
        # 設置新的默認模板
        template.is_user_default = True
        
        await db.commit()
        await db.refresh(template)
        
        return PromptTemplateResponse(
            id=template.id,
            name=template.name,
            description=template.description,
            prompt=template.prompt,
            is_system_template=template.is_system_template,
            is_user_default=template.is_user_default,
            user_id=str(template.user_id) if template.user_id else None,
            created_at=template.created_at.isoformat(),
            updated_at=template.updated_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"設置默認模板失敗: {str(e)}"
        )


@router.get("/default", response_model=Optional[PromptTemplateResponse])
async def get_default_template(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
):
    """獲取用戶的默認模板"""
    try:
        # 首先查找用戶設置的默認模板
        user_default_query = select(PromptTemplate).where(
            and_(
                PromptTemplate.user_id == current_user.id,
                PromptTemplate.is_user_default == True
            )
        )
        user_default_result = await db.execute(user_default_query)
        user_default = user_default_result.scalar_one_or_none()
        
        if user_default:
            return PromptTemplateResponse(
                id=user_default.id,
                name=user_default.name,
                description=user_default.description,
                prompt=user_default.prompt,
                is_system_template=user_default.is_system_template,
                is_user_default=user_default.is_user_default,
                user_id=str(user_default.user_id) if user_default.user_id else None,
                created_at=user_default.created_at.isoformat(),
                updated_at=user_default.updated_at.isoformat()
            )
        
        # 如果沒有用戶默認，查找系統默認模板
        system_default_query = select(PromptTemplate).where(
            and_(
                PromptTemplate.is_system_template == True,
                PromptTemplate.is_user_default == True
            )
        )
        system_default_result = await db.execute(system_default_query)
        system_default = system_default_result.scalar_one_or_none()
        
        if system_default:
            return PromptTemplateResponse(
                id=system_default.id,
                name=system_default.name,
                description=system_default.description,
                prompt=system_default.prompt,
                is_system_template=system_default.is_system_template,
                is_user_default=system_default.is_user_default,
                user_id=str(system_default.user_id) if system_default.user_id else None,
                created_at=system_default.created_at.isoformat(),
                updated_at=system_default.updated_at.isoformat()
            )
        
        return None
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"獲取默認模板失敗: {str(e)}"
        )