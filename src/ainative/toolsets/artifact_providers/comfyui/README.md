# ComfyUI Provider

ComfyUI is an Artifact Provider, not a host executor and not a transfer backend.

The Provider seam submits an artifact-generation request and returns an `ArtifactResult`. An Artifact Apply Workflow decides how the artifact is applied to Blender or UE5.
