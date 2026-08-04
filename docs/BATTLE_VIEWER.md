# INQ Final Shot — in-battle 3D viewer

The viewer opens after the player's vehicle is destroyed and inspects the real vehicle entity in the current arena.

Controls:

- move the mouse — orbit around the destroyed tank;
- mouse wheel — zoom;
- `Space` — reset camera;
- `V` or `Esc` — close and restore the standard battle camera.

Impact coordinates are captured from `Vehicle.showDamageFromShot` through `DamageFromShotDecoder.parseHitPoint`, transformed by the live vehicle part matrix, and projected into the battle overlay every frame.
