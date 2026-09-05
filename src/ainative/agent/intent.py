from __future__ import annotations

from dataclasses import dataclass

from ainative.orchestration.contracts.task import (
    BlenderCallSurface,
    TaskContract,
    TaskRoute,
    TransferBackendKind,
)


class IntentInterpreter:
    """Protocol-like base for an LLM-backed or deterministic interpreter."""

    def interpret(self, prompt: str, task_id: str) -> TaskContract:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class HeuristicIntentInterpreter(IntentInterpreter):
    """Small deterministic fallback used when the Agent has no LLM executor."""

    def interpret(self, prompt: str, task_id: str) -> TaskContract:
        text = prompt.lower()
        explicit_transfer = any(word in text for word in (
            "回到原", "传回", "传到 unreal", "拿到 blender", "拿到 ue5", "跨主机", "往返",
            "roundtrip", "cross-host", "direct transfer", "assetsbridge", "bridge", "直接导出",
            "导入 ue5", "导入 unreal",
        ))
        native_object = any(word in text for word in ("actor", "物体", "对象", "场景", "关卡", "level", "location", "位置", "旋转", "transform", "scale", "缩放"))
        ue5_host = any(word in text for word in ("ue5", "unreal", "actor", "关卡", "level"))
        blender_host = any(word in text for word in ("blender", "scene", "模型", "mesh"))
        cross_host = explicit_transfer and not (native_object and not any(word in text for word in ("blender", "拿到", "传回", "往返", "roundtrip", "cross-host", "assetsbridge", "bridge")))
        artifact = any(word in text for word in ("comfyui", "生成纹理", "生成图", "artifact", "生成资产"))
        level_template = any(word in text for word in (
            "默认关卡",
            "默认光照",
            "default level",
            "default lighting",
            "template_default",
            "template default",
            "new level",
            "新建关卡",
            "创建关卡",
        ))
        route = TaskRoute.ARTIFACT_PIPELINE if artifact else (TaskRoute.ASSET_TRANSFER if cross_host else TaskRoute.HOST_OPERATION)
        profile = "headless_batch" if any(word in text for word in ("批处理", "后台", "headless")) else ("interactive" if any(word in text for word in ("交互", "当前 selection", "当前 scene")) else "default")
        preserve = set()
        if any(word in text for word in ("原资产", "资产身份", "asset path", "object id")):
            preserve.add("asset_identity")
        if any(word in text for word in ("材质槽", "material slot")):
            preserve.add("material_slots")
        if any(word in text for word in ("transform", "位置", "旋转", "缩放")):
            preserve.add("transform")
        if any(word in text for word in ("骨架", "skeleton")):
            preserve.add("skeleton")
        if any(word in text for word in ("形态", "morph", "shape key")):
            preserve.add("morph_targets")
        acceptable = set()
        if any(word in text for word in ("允许损失", "新文件", "只要文件", "不需要原资产")):
            acceptable.update(preserve)
        backend = None
        if any(word in text for word in ("assetsbridge", "bridge", "桥接")):
            backend = TransferBackendKind.ASSETSBRIDGE
        if any(word in text for word in ("绕过 bridge", "direct transfer", "直接导出", "glb", "fbx", "usd")):
            backend = TransferBackendKind.DIRECT
        surface = BlenderCallSurface.CLI_PYTHON if profile == "headless_batch" else (BlenderCallSurface.ADDON if profile == "interactive" else None)

        source_context: dict[str, str] = {}
        target_context: dict[str, str] = {}
        metadata: dict[str, str] = {}
        if route is TaskRoute.ASSET_TRANSFER:
            source_context["app"] = "ue5" if ue5_host else "blender"
            target_context["app"] = "ue5" if ue5_host else "blender"
            metadata["edit_app"] = "blender"
        elif route is TaskRoute.HOST_OPERATION:
            host_app = "ue5" if ue5_host and not blender_host else "blender"
            target_context["app"] = host_app
            if host_app == "ue5":
                if level_template:
                    metadata["operation"] = "create_level_from_template"
                    metadata["read_operation"] = "inspect_level"
                elif any(word in text for word in ("移动", "move", "设置", "set", "位置", "location", "transform", "旋转", "rotation", "缩放", "scale")):
                    metadata["operation"] = "set-actor-transform"
                else:
                    metadata["operation"] = "inspect"
                if any(word in text for word in ("保存", "save", "写回", "publish")) and not level_template:
                    metadata["publish_operation"] = "save-level"
            else:
                metadata["operation"] = "modify"
        return TaskContract(
            task_id=task_id,
            objective=prompt,
            route=route,
            profile=profile,
            direction="ue5_to_blender_to_ue5" if cross_host else "none",
            preserve_relations=frozenset(preserve),
            acceptable_loss=frozenset(acceptable),
            preferred_backend=backend,
            preferred_call_surface=surface,
            source_context=source_context,
            target_context=target_context,
            metadata=metadata,
        )
