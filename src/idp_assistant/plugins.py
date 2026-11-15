"""Allowlisted plugin registry; model output can never execute arbitrary code."""
from __future__ import annotations
from typing import Any, Callable
from pydantic import BaseModel, Field
class PluginRequest(BaseModel):
    plugin: str
    payload: dict[str,Any]=Field(default_factory=dict)
class PluginResult(BaseModel):
    plugin: str
    ok: bool
    output: dict[str,Any]=Field(default_factory=dict)
    error: str|None=None
class PluginRegistry:
    def __init__(self): self._handlers:dict[str,Callable[[dict[str,Any]],dict[str,Any]]]={}
    def register(self,name:str,handler:Callable[[dict[str,Any]],dict[str,Any]])->None: self._handlers[name]=handler
    def execute(self,request:PluginRequest)->PluginResult:
        handler=self._handlers.get(request.plugin)
        if not handler: return PluginResult(plugin=request.plugin,ok=False,error="Plugin is not allowlisted.")
        try: return PluginResult(plugin=request.plugin,ok=True,output=handler(request.payload))
        except Exception as exc: return PluginResult(plugin=request.plugin,ok=False,error=str(exc))
