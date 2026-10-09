# Godot performance rules

Rules for Godot 4 projects in GDScript, grouped into the categories `godot.md` lists. Each rule names what to look for, why it costs, how to confirm it in the code, and the fix. A rule's cost is real only on a path that runs often: confirm the path is hot (every frame, every physics tick, per entity, per input event) before reporting, and say whether the cost is measured (profiler, monitor) or inferred.

## Frame loop

### godot/lookup-in-hot-path

- **Look for:** `$Path`, `get_node()`, `find_child()`, `get_tree().get_nodes_in_group()`, or `get_first_node_in_group()` inside `_process`, `_physics_process`, `_input`, or a loop over entities.
- **Why:** each call walks the tree or builds a new array on every frame for a result that rarely changes.
- **Confirm:** the call sits on a per-frame or per-entity path and its target does not change between calls.
- **Fix:** resolve once into a typed `@onready var` or a member set in `_ready()`; track group membership with signals or a registry the owner maintains.

### godot/idle-processing

- **Look for:** `_process` or `_physics_process` that returns early on most frames because it polls a flag, a timer, or another node's state.
- **Why:** defining the callback enables processing every frame for every instance, even when there is nothing to do.
- **Confirm:** the early-return condition is false for long stretches, and the change it waits for has a signal or a single setter.
- **Fix:** react to a signal or a `Timer`, or call `set_process(false)` while idle and re-enable it when work arrives.

### godot/wrong-tick

- **Look for:** moving physics bodies, `move_and_slide()`, or physics queries in `_process`; purely visual interpolation or UI updates in `_physics_process`.
- **Why:** physics in `_process` runs at the render rate, so behavior changes with frame rate; visuals in `_physics_process` update at the physics rate and stutter at high refresh rates.
- **Confirm:** the code's effect is physical (bodies, collisions) or visual (sprites, labels, cameras).
- **Fix:** physics in `_physics_process`, visuals in `_process`; enable physics interpolation for smooth visuals of physics-driven nodes.

## Allocation and data

### godot/per-frame-allocation

- **Look for:** new Arrays, Dictionaries, Strings (formatting, concatenation, `str()` of large values), or `Object.new()` created inside per-frame or per-entity code.
- **Why:** these are heap allocations and frees on every call. `Vector2`, `Vector3`, `Color`, `Rect2`, and similar small value types live inside the `Variant` and are cheap; `Transform2D`, `Transform3D`, `Basis`, `AABB`, and `Projection` use a pooled allocation.
- **Confirm:** the allocation happens on a hot path and its result is discarded or rebuilt identically each time.
- **Fix:** reuse a member container (`clear()` and refill), build strings only when the displayed value changes, and keep large numeric data in `PackedFloat32Array`, `PackedVector2Array`, and similar packed arrays.

### godot/untyped-hot-code

- **Look for:** untyped variables, parameters, and returns in hot functions.
- **Why:** with full static types the GDScript VM uses typed instructions and skips runtime `Variant` checks; untyped code takes the slower generic path.
- **Confirm:** the function is hot and its types are inferable or known.
- **Fix:** add types (`var count: int`, `:=` with a typed right-hand side, typed arrays such as `Array[Enemy]`).

### godot/string-keys-in-hot-path

- **Look for:** method, property, signal, or action names passed as `String` on hot paths through dynamic calls (`call()`, `get()`, `set()`, `has_method()`, `emit_signal()` on an untyped receiver) or built at runtime (`"attack_" + kind`).
- **Why:** a string literal passed to a statically resolved `StringName` parameter is converted when the script compiles, so `Input.is_action_pressed("jump")` costs nothing extra. The conversion and hashing happen on every call only when the receiver is untyped (a dynamic call) or the string is built at runtime.
- **Confirm:** the receiver's type is unknown at compile time, or the name is a non-constant `String`, and the call is hot.
- **Fix:** type the receiver and call the method directly, use typed signals, or precompute the names as `StringName` constants (`&"attack_fire"`).

## Resources and loading

### godot/load-in-hot-path

- **Look for:** `load()` or `ResourceLoader.load()` in per-frame code or per-spawn code.
- **Why:** repeated loads hit the resource cache but still resolve the path each call; the first load of a large resource blocks the main thread mid-game.
- **Confirm:** the path is constant or drawn from a small set, and the call runs repeatedly or during play.
- **Fix:** `preload()` into a constant for known paths, cache loaded resources by path, and use `ResourceLoader.load_threaded_request()` for large resources needed later.

## Rendering

### godot/material-per-instance

- **Look for:** `material_override = StandardMaterial3D.new()`, `material.duplicate()`, or per-instance shader parameters set by duplicating materials, for many instances of the same visual.
- **Why:** each unique material breaks sharing; draw calls cannot share state, and memory grows with instance count.
- **Confirm:** the instances differ only in values a shared material could take per instance.
- **Fix:** share one material and vary per-instance values with `instance uniform` shader parameters (`set_instance_shader_parameter()`), or with modulate and color where the node offers it. Instance uniforms need Godot 4.4+ in the Compatibility renderer and allow 16 per shader, scalars and vectors only. Every `Sprite3D` already creates its own mesh and material, so for sprites prefer `modulate`; instance uniforms apply only with a shared `material_override`.

### godot/repeated-meshes-not-multimeshed

- **Look for:** hundreds or more identical meshes or quads as separate `MeshInstance3D` or `Sprite3D` nodes (terrain tiles, foliage, crowds of identical props).
- **Why:** each node is its own draw call and its own scene-tree node. Only Forward+ auto-instances `MeshInstance3D` nodes sharing a mesh and an opaque or alpha-tested material; Mobile and Compatibility do not. `Sprite3D` creates its own mesh per node, so it is never auto-instanced.
- **Confirm:** the instances share a mesh and material and their count is large enough to matter on target hardware.
- **Fix:** a `MultiMeshInstance3D` (or `MultiMeshInstance2D`) with per-instance transforms and colors; for sprites, a quad mesh with a texture atlas. Keep individual nodes for instances that need their own logic or collision.

### godot/offscreen-work

- **Look for:** animation, particles, or per-frame logic that runs for entities far away or off screen.
- **Why:** work nobody sees still costs CPU and GPU time.
- **Confirm:** the entity's work is purely visual or can pause while unseen.
- **Fix:** `VisibleOnScreenEnabler2D/3D` to pause processing off screen, or `VisibleOnScreenNotifier2D/3D` signals; `visibility_range_end` on `GeometryInstance3D` to stop drawing distant detail.

## Physics

### godot/distance-polling

- **Look for:** per-frame loops comparing distances between many entities (`for a in units: for b in enemies:`), or many `RayCast3D` nodes kept only for occasional checks.
- **Why:** pairwise checks grow quadratically, and every enabled raycast node casts every physics frame.
- **Confirm:** the entity counts on the path and how often the result is needed.
- **Fix:** `Area3D`/`Area2D` overlap signals, a spatial grid the simulation already maintains, or on-demand `PhysicsDirectSpaceState3D.intersect_ray()` queries; keep collision layers and masks minimal so bodies test only what they must.

## Threading

### godot/main-thread-heavy-work

- **Look for:** long pure computations on the main thread during play: pathfinding over large maps, procedural generation, bulk data processing.
- **Why:** the frame cannot finish until the work does, so it hitches.
- **Confirm:** the work takes long enough to drop frames and does not touch the scene tree.
- **Fix:** run it with `WorkerThreadPool.add_task()` (or a `Thread`), touch only thread-safe APIs from the worker, and hand results back with `call_deferred()`. Keep the task ID and call `wait_for_task_completion()` once `is_task_completed()` is true, so the task's resources are released.

## Lifecycle

### godot/instantiate-churn

- **Look for:** many short-lived scenes created and freed every second (projectiles, hit effects, floating text) with `instantiate()` and `queue_free()`.
- **Why:** instancing builds a node subtree and adding it to the tree runs enter-tree work; GDScript has no garbage-collector pauses, so the cost is the instancing itself.
- **Confirm:** the spawn rate, and profiler time in instancing, before recommending a pool.
- **Fix:** pool and reuse instances (hide, disable processing, reset state) only when the profiler shows instancing cost; otherwise keep the simpler code.

### godot/connection-accumulation

- **Look for:** `connect()` calls in code that runs repeatedly (per frame, per refresh, per reuse of a pooled object), especially connecting lambdas.
- **Why:** each lambda is a new `Callable`, so the same handler connects again and runs once per connection; connecting a method twice, including a `.bind()` variant of it, is an error.
- **Confirm:** the connecting code can run more than once for the same emitter.
- **Fix:** connect once in `_ready()` or at creation, check `is_connected()` for method callables, or disconnect before reconnecting; use `CONNECT_ONE_SHOT` for one-time handlers.

### godot/await-after-free

- **Look for:** code after an `await` (on a timer, a tween, or a signal) that touches the node or other nodes that may be freed during the wait.
- **Why:** if the awaiting object is freed, the coroutine never resumes; if another node it holds is freed, the reference becomes invalid.
- **Confirm:** something can free the involved nodes while the wait is pending.
- **Fix:** check `is_instance_valid()` on the other node after the await, or move the follow-up into a signal handler the freed object's lifetime governs.
