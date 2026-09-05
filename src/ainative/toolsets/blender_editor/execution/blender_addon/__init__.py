"""Installable Blender Add-on surface for AI Native operations."""

bl_info = {
    "name": "AI Native Asset Integration",
    "author": "AI Native Game Engine",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Object",
    "category": "Object",
}


def _bpy():
    import bpy  # type: ignore[import-not-found]

    return bpy


def _operator_class():
    bpy = _bpy()

    class AINATIVE_OT_execute(bpy.types.Operator):
        bl_idname = "ainative.execute_asset_operation"
        bl_label = "Execute AI Native Asset Operation"
        bl_options = {"REGISTER", "UNDO"}

        operation: bpy.props.StringProperty(name="Operation", default="inspect-active")
        parameters_json: bpy.props.StringProperty(name="Parameters JSON", default="{}", options={"HIDDEN"})

        def execute(self, context):
            import json

            from .operations import execute_operation

            result = execute_operation(self.operation, json.loads(self.parameters_json))
            if result.get("status") != "succeeded":
                self.report({"ERROR"}, "; ".join(result.get("errors", ("operation failed",))))
                return {"CANCELLED"}
            self.report({"INFO"}, "AI Native operation completed")
            return {"FINISHED"}

    return AINATIVE_OT_execute


def register():
    bpy = _bpy()
    cls = _operator_class()
    bpy.utils.register_class(cls)
    globals()["AINATIVE_OT_execute"] = cls


def unregister():
    bpy = _bpy()
    cls = globals().get("AINATIVE_OT_execute")
    if cls is not None:
        bpy.utils.unregister_class(cls)
        del globals()["AINATIVE_OT_execute"]
