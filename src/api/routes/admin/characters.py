"""
角色管理 API。

GET  /admin/characters            列出所有可用角色
GET  /admin/characters/{id}       读取角色配置（原始 YAML 内容）
PUT  /admin/characters/{id}       更新角色配置（写回 YAML 文件）
POST /admin/characters/{id}/reload 重新加载角色到 ConversationService
"""
import os
from pathlib import Path
from typing import Any, Dict, List

import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ....character_defaults import (
    DEFAULT_CHARACTER_ENV,
    get_effective_default_character_id,
)
from ...service_registry import get_service, switch_character
from .config_mgr import _read_env_file, _write_env_file

router = APIRouter(prefix="/characters")

_CHARACTERS_DIR = Path("characters")


def _list_character_dirs() -> List[Path]:
    if not _CHARACTERS_DIR.exists():
        return []
    return sorted(
        p for p in _CHARACTERS_DIR.iterdir()
        if p.is_dir() and (p / "personality.yaml").exists()
    )


class CharacterSummary(BaseModel):
    id: str
    name: str
    version: str
    schema_version: str
    is_active: bool
    is_default_startup: bool


class CharacterDetail(BaseModel):
    id: str
    raw_yaml: str
    parsed: Dict[str, Any]
    raw_manifest: str = ""
    manifest: Dict[str, Any] = Field(default_factory=dict)


class UpdateCharacterRequest(BaseModel):
    raw_yaml: str


@router.get("", response_model=List[CharacterSummary])
async def list_characters(service=Depends(get_service)) -> List[CharacterSummary]:
    result = []
    default_character_id = get_effective_default_character_id()
    for char_dir in _list_character_dirs():
        yaml_path = char_dir / "personality.yaml"
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            data = {}
        result.append(
            CharacterSummary(
                id=char_dir.name,
                name=data.get("name", char_dir.name),
                version=data.get("version", ""),
                schema_version=str(data.get("schema_version", "1")),
                is_active=(char_dir.name == service.character_id),
                is_default_startup=(char_dir.name == default_character_id),
            )
        )
    return result


@router.get("/{character_id}", response_model=CharacterDetail)
async def get_character(character_id: str) -> CharacterDetail:
    yaml_path = _CHARACTERS_DIR / character_id / "personality.yaml"
    manifest_path = _CHARACTERS_DIR / character_id / "manifest.yaml"
    if not yaml_path.exists():
        raise HTTPException(status_code=404, detail=f"角色不存在: {character_id}")
    raw = yaml_path.read_text(encoding="utf-8")
    try:
        parsed = yaml.safe_load(raw) or {}
    except yaml.YAMLError as e:
        raise HTTPException(status_code=422, detail=f"YAML 解析失败: {e}")

    raw_manifest = ""
    manifest: Dict[str, Any] = {}
    if manifest_path.exists():
      raw_manifest = manifest_path.read_text(encoding="utf-8")
      try:
        manifest = yaml.safe_load(raw_manifest) or {}
      except yaml.YAMLError as e:
        raise HTTPException(status_code=422, detail=f"manifest 解析失败: {e}")

    return CharacterDetail(
        id=character_id,
        raw_yaml=raw,
        parsed=parsed,
        raw_manifest=raw_manifest,
        manifest=manifest,
    )


@router.put("/{character_id}", status_code=200)
async def update_character(character_id: str, body: UpdateCharacterRequest) -> Dict[str, str]:
    yaml_path = _CHARACTERS_DIR / character_id / "personality.yaml"
    if not yaml_path.exists():
        raise HTTPException(status_code=404, detail=f"角色不存在: {character_id}")
    # 先验证 YAML 合法性
    try:
        yaml.safe_load(body.raw_yaml)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=422, detail=f"YAML 格式错误: {e}")
    yaml_path.write_text(body.raw_yaml, encoding="utf-8")
    return {"status": "saved", "message": "配置已保存，需重新加载角色才能生效"}


@router.post("/{character_id}/reload", status_code=200)
async def reload_character(character_id: str) -> Dict[str, str]:
    """重新加载指定角色为当前活跃角色。"""
    try:
        char_id, char_name = await switch_character(character_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "ok", "character_id": char_id, "character_name": char_name}


@router.post("/{character_id}/set-default-startup", status_code=200)
async def set_default_startup_character(character_id: str) -> Dict[str, str]:
    yaml_path = _CHARACTERS_DIR / character_id / "personality.yaml"
    if not yaml_path.exists():
        raise HTTPException(status_code=404, detail=f"角色不存在: {character_id}")

    env_data = _read_env_file()
    env_data[DEFAULT_CHARACTER_ENV] = character_id
    _write_env_file(env_data)
    os.environ[DEFAULT_CHARACTER_ENV] = character_id

    return {
        "status": "ok",
        "default_character_id": character_id,
        "message": "默认启动角色已更新，重启 sidecar 后生效",
    }
