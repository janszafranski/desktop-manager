"use strict";

// Window-open "shudder" for KWin (Plasma) — the analogue of the Hyprland spring on
// the Caelestia/end4 sessions. KWin has no spring physics, but its animation engine
// speaks QEasingCurve, and OutBack overshoots the target = a fast open with a sharp
// bouncy stop. For a stronger multi-wobble shudder (closer to the Hyprland spring, but
// busier on big windows) swap SHUDDER_CURVE to QEasingCurve.OutElastic.
const SHUDDER_CURVE = QEasingCurve.OutBack;
const OPEN_FROM_SCALE = 0.7;      // start size (matches the Hyprland `popin 70%`)
const OPEN_DURATION_MS = 300;     // scaled by the global animation-speed slider

effects.windowAdded.connect(function (window) {
    // Only ordinary application windows — skip tooltips, menus, docks, notifications,
    // and anything already gone.
    if (!window || !window.normalWindow || window.deleted) {
        return;
    }
    // Don't animate windows that appear minimized/hidden.
    if (window.minimized) {
        return;
    }
    animate({
        window: window,
        duration: animationTime(OPEN_DURATION_MS),
        animations: [
            {
                type: Effect.Scale,
                curve: SHUDDER_CURVE,
                from: OPEN_FROM_SCALE
                // no `to` → animates up to the window's natural size (1.0)
            },
            {
                type: Effect.Opacity,
                curve: QEasingCurve.OutCubic,
                from: 0.0
            }
        ]
    });
});
